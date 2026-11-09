"""Генератор JMeter test plan (jmeter/delivery-flow.jmx).
Один і той самий бізнес-потік вставляється у дві Thread Group:
  * main  — основне навантаження (baseline / load / фон для spike);
  * spike — додаткові користувачі, що з'являються із затримкою (тільки для spike).
Кількість потоків, рампа, тривалість і затримка задаються властивостями -J / файлами jmeter/*.properties.
"""
from xml.sax.saxutils import escape

def prop(name, key, val):
    return f'<stringProp name="{key}">{escape(val)}</stringProp>'

def http(name, method, path, body=None):
    body_xml = ""
    if body is not None:
        body_xml = f'''<boolProp name="HTTPSampler.postBodyRaw">true</boolProp>
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">
            <collectionProp name="Arguments.arguments">
              <elementProp name="" elementType="HTTPArgument">
                <boolProp name="HTTPArgument.always_encode">false</boolProp>
                <stringProp name="Argument.value">{escape(body)}</stringProp>
                <stringProp name="Argument.metadata">=</stringProp>
              </elementProp>
            </collectionProp>
          </elementProp>'''
    else:
        body_xml = '''<elementProp name="HTTPsampler.Arguments" elementType="Arguments"><collectionProp name="Arguments.arguments"/></elementProp>'''
    return f'''<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="{escape(name)}" enabled="true">
          {body_xml}
          <stringProp name="HTTPSampler.path">{escape(path)}</stringProp>
          <stringProp name="HTTPSampler.method">{method}</stringProp>
          <boolProp name="HTTPSampler.follow_redirects">false</boolProp>
          <boolProp name="HTTPSampler.auto_redirects">false</boolProp>
          <boolProp name="HTTPSampler.use_keepalive">true</boolProp>
        </HTTPSamplerProxy>'''

def code_assert(code):
    return f'''<ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="HTTP {code}" enabled="true">
            <collectionProp name="Asserion.test_strings"><stringProp name="1">{code}</stringProp></collectionProp>
            <stringProp name="Assertion.test_field">Assertion.response_code</stringProp>
            <boolProp name="Assertion.assume_success">false</boolProp>
            <intProp name="Assertion.test_type">8</intProp>
          </ResponseAssertion>
          <hashTree/>'''

def json_assert(path, value):
    return f'''<JSONPathAssertion guiclass="JSONPathAssertionGui" testclass="JSONPathAssertion" testname="{escape(path)} == {value}" enabled="true">
            <stringProp name="JSON_PATH">{escape(path)}</stringProp>
            <stringProp name="EXPECTED_VALUE">{value}</stringProp>
            <boolProp name="JSONVALIDATION">true</boolProp>
            <boolProp name="EXPECT_NULL">false</boolProp>
            <boolProp name="INVERT">false</boolProp>
            <boolProp name="ISREGEX">false</boolProp>
          </JSONPathAssertion>
          <hashTree/>'''

def extract(var, path):
    return f'''<JSONPostProcessor guiclass="JSONPostProcessorGui" testclass="JSONPostProcessor" testname="extract {var}" enabled="true">
            <stringProp name="JSONPostProcessor.referenceNames">{var}</stringProp>
            <stringProp name="JSONPostProcessor.jsonPathExprs">{escape(path)}</stringProp>
            <stringProp name="JSONPostProcessor.match_numbers">1</stringProp>
            <stringProp name="JSONPostProcessor.defaultValues">NOT_FOUND</stringProp>
          </JSONPostProcessor>
          <hashTree/>'''

REFUND_GROOVY = '''def json = new groovy.json.JsonSlurper().parseText(prev.getResponseDataAsString())
long total = Long.parseLong(vars.get("total"))
long expected = Math.floorDiv(total * 50L, 100L)
if (json.refund != expected) {
  AssertionResult.setFailure(true)
  AssertionResult.setFailureMessage("refund=" + json.refund + ", expected 50% of " + total + " = " + expected)
}'''

def jsr223_assert():
    return f'''<JSR223Assertion guiclass="TestBeanGUI" testclass="JSR223Assertion" testname="refund = 50% total (персональне правило)" enabled="true">
            <stringProp name="scriptLanguage">groovy</stringProp>
            <stringProp name="cacheKey">true</stringProp>
            <stringProp name="script">{escape(REFUND_GROOVY)}</stringProp>
          </JSR223Assertion>
          <hashTree/>'''

def flow():
    think = '''<TestAction guiclass="TestActionGui" testclass="TestAction" testname="Think time" enabled="true">
          <intProp name="ActionProcessor.action">1</intProp>
          <intProp name="ActionProcessor.target">0</intProp>
          <stringProp name="ActionProcessor.duration">${__P(think_ms,1000)}</stringProp>
        </TestAction>
        <hashTree/>'''
    steps = [
        (http("POST /customers", "POST", "/customers", '{"code":"C-${__UUID()}","regular":false}'),
         [code_assert(201), extract("customerId", "$.id")]),
        (http("POST /parcels", "POST", "/parcels",
              '{"code":"P-${__UUID()}","weightGrams":1000,"declaredValue":10000,"fragile":false}'),
         [code_assert(201), extract("parcelId", "$.id")]),
        (http("POST /shipments", "POST", "/shipments",
              '{"reference":"S-${__UUID()}","customerId":${customerId},"parcelId":${parcelId},'
              '"distanceKm":100,"urgent":false,"pickup":false,"couponValid":false}'),
         [code_assert(201), json_assert("$.status", "Registered"), json_assert("$.baseFee", "7000"),
          extract("shipmentId", "$.id"), extract("total", "$.total")]),
        (http("GET /shipments/{id}", "GET", "/shipments/${shipmentId}"),
         [code_assert(200), json_assert("$.status", "Registered"), json_assert("$.customerId", "${customerId}")]),
        (http("POST /shipments/{id}/dispatch", "POST", "/shipments/${shipmentId}/dispatch"),
         [code_assert(200), json_assert("$.status", "Dispatched")]),
        (http("POST /shipments/{id}/cancel", "POST", "/shipments/${shipmentId}/cancel"),
         [code_assert(200), json_assert("$.status", "Cancelled"), jsr223_assert()]),
    ]
    out = [think]
    for s, children in steps:
        out.append(s)
        out.append("<hashTree>\n" + "\n".join(children) + "\n</hashTree>")
    return "\n".join(out)

def thread_group(name, p):
    return f'''<ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="{name}" enabled="true">
        <stringProp name="ThreadGroup.on_sample_error">startnextloop</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController">
          <boolProp name="LoopController.continue_forever">false</boolProp>
          <intProp name="LoopController.loops">-1</intProp>
        </elementProp>
        <stringProp name="ThreadGroup.num_threads">${{__P({p}_users,0)}}</stringProp>
        <stringProp name="ThreadGroup.ramp_time">${{__P({p}_ramp,0)}}</stringProp>
        <boolProp name="ThreadGroup.scheduler">true</boolProp>
        <stringProp name="ThreadGroup.duration">${{__P({p}_duration,60)}}</stringProp>
        <stringProp name="ThreadGroup.delay">${{__P({p}_delay,0)}}</stringProp>
        <boolProp name="ThreadGroup.same_user_on_next_iteration">true</boolProp>
        <boolProp name="ThreadGroup.delayedStart">true</boolProp>
      </ThreadGroup>
      <hashTree>
        {flow()}
      </hashTree>'''

jmx = f'''<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Lab 7 — Delivery variant09 performance" enabled="true">
      <stringProp name="TestPlan.comments">Сценарій: customer -> parcel -> shipment -> get -> dispatch -> cancel (refund 50%). Профіль: jmeter/*.properties</stringProp>
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <boolProp name="TestPlan.serialize_threadgroups">false</boolProp>
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments"><collectionProp name="Arguments.arguments"/></elementProp>
    </TestPlan>
    <hashTree>
      <ConfigTestElement guiclass="HttpDefaultsGui" testclass="ConfigTestElement" testname="HTTP Request Defaults" enabled="true">
        <elementProp name="HTTPsampler.Arguments" elementType="Arguments"><collectionProp name="Arguments.arguments"/></elementProp>
        <stringProp name="HTTPSampler.protocol">http</stringProp>
        <stringProp name="HTTPSampler.domain">${{__P(host,127.0.0.1)}}</stringProp>
        <stringProp name="HTTPSampler.port">${{__P(port,8080)}}</stringProp>
        <stringProp name="HTTPSampler.implementation">HttpClient4</stringProp>
        <stringProp name="HTTPSampler.connect_timeout">5000</stringProp>
        <stringProp name="HTTPSampler.response_timeout">30000</stringProp>
      </ConfigTestElement>
      <hashTree/>
      <HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="Content-Type: application/json" enabled="true">
        <collectionProp name="HeaderManager.headers">
          <elementProp name="" elementType="Header">
            <stringProp name="Header.name">Content-Type</stringProp>
            <stringProp name="Header.value">application/json</stringProp>
          </elementProp>
        </collectionProp>
      </HeaderManager>
      <hashTree/>
      {thread_group("main", "main")}
      {thread_group("spike", "spike")}
    </hashTree>
  </hashTree>
</jmeterTestPlan>
'''
open("jmeter/delivery-flow.jmx", "w", encoding="utf-8").write(jmx)
print("ok")
