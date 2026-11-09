import json, os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = json.load(open(f'{ROOT}/results/summary.json'))
doc = Document()
st = doc.styles['Normal']; st.font.name = 'Times New Roman'; st.font.size = Pt(12)
st.element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')
for s in doc.sections:
    s.left_margin = Cm(2.5); s.right_margin = Cm(1.5); s.top_margin = Cm(2); s.bottom_margin = Cm(2)

def P(text='', bold=False, align=None, size=None, italic=False):
    p = doc.add_paragraph(); r = p.add_run(text); r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    if align == 'c': p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p
def H(text, lvl=1):
    h = doc.add_heading(text, lvl)
    for r in h.runs: r.font.color.rgb = RGBColor(0, 0, 0); r.font.name = 'Times New Roman'
def B(items):
    for i in items: doc.add_paragraph(i, style='List Bullet')
def CODE(text):
    p = doc.add_paragraph(); r = p.add_run(text); r.font.name = 'Consolas'; r.font.size = Pt(9)
    pPr = p._p.get_or_add_pPr(); sh = OxmlElement('w:shd'); sh.set(qn('w:val'), 'clear'); sh.set(qn('w:fill'), 'F2F2F2'); pPr.append(sh)
def T(header, rows, size=9):
    t = doc.add_table(rows=1, cols=len(header)); t.style = 'Table Grid'
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]; c.text = ''; r = c.paragraphs[0].add_run(str(h)); r.bold = True; r.font.size = Pt(size)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ''; r = cells[i].paragraphs[0].add_run(str(v)); r.font.size = Pt(size)
    doc.add_paragraph()
def IMG(name, caption, w=16):
    doc.add_picture(f'{ROOT}/report/img/{name}', width=Cm(w)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    P(caption, italic=True, align='c', size=10)

g = lambda k: S[k]
# ---------- титул ----------
P('Міністерство освіти і науки України', align='c')
P('Дисципліна «Тестування та верифікація програмного забезпечення»', align='c')
for _ in range(5): P()
P('ЗВІТ', bold=True, align='c', size=16)
P('з лабораторної роботи №7', bold=True, align='c', size=14)
P('«Performance and Load Testing»', align='c', size=14)
P('Варіант виконання: JMeter + k6', align='c')
for _ in range(5): P()
p = P('Виконав: студент групи 343А\nКирилюк Максим Олександрович\nВаріант 9 (group 2 / variant09, Java)')
p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
for _ in range(6): P()
P('2026', align='c')
doc.add_page_break()

# ---------- 1 ----------
H('1. Мета роботи')
P('Навчитися будувати сценарії навантажувального тестування REST API, виконувати різні типи performance-тестів '
  '(baseline, load, spike), збирати ключові метрики (average, p95, throughput, error rate), задавати thresholds '
  'та інтерпретувати результати; порівняти два інструменти — Apache JMeter і Grafana k6.')

H('2. Вихідні дані та тестове середовище')
P('SUT: SUT B свого варіанта — group 2 / variant09 «Доставка посилок» (репозиторій y-nikitin/university_testing). '
  'Backend: Java 21, Spring Boot (вбудований Tomcat), JdbcTemplate + HikariCP, PostgreSQL. REST API на http://127.0.0.1:8080.')
T(['Компонент', 'Значення'], [
    ['ОС / CPU / RAM', 'Linux (контейнер), 4 vCPU Intel Xeon @ 2.30 GHz, 15 GB RAM'],
    ['SUT', 'sut-b-delivery-variant09-1.0-SNAPSHOT.jar, OpenJDK 21.0.12, налаштування за замовчуванням'],
    ['База даних', 'PostgreSQL 16.15 (локально), БД delivery_variant09_test, міграція V1__create_tables.sql'],
    ['k6', 'Grafana k6 v1.3.0'],
    ['JMeter', 'Apache JMeter 5.6.3 (non-GUI режим, HttpClient4)'],
    ['Розташування', 'Генератор навантаження і SUT працюють на одній машині (див. обмеження в п. 9)'],
])
P('Однакові умови для кожного з 6 запусків (скрипт scripts/run.sh): (1) перезапуск SUT; (2) прогрів JVM — 10 VU × 15 с; '
  '(3) очищення таблиць TRUNCATE … RESTART IDENTITY; (4) моніторинг CPU процесу SUT і всієї машини щосекунди; '
  '(5) запуск тесту; (6) контроль кількості записів у БД після тесту.')

# ---------- 3 ----------
H('3. Performance scenario')
P('Одна ітерація віртуального користувача — повний бізнес-сценарій «оформити відправлення і скасувати його після '
  'передачі в доставку». Він складається з 6 пов\'язаних HTTP-запитів; кожен наступний використовує дані з відповіді попереднього:')
T(['№', 'Запит', 'Тіло / звідки беруться дані', 'Перевірки (k6 check / JMeter assertion)'], [
    ['1', 'POST /customers', '{"code":"C-<UUID>","regular":false} → витягуємо id → customerId', 'HTTP 201'],
    ['2', 'POST /parcels', '{"code":"P-<UUID>","weightGrams":1000,"declaredValue":10000,"fragile":false} → parcelId', 'HTTP 201'],
    ['3', 'POST /shipments', 'reference S-<UUID>, customerId і parcelId з кроків 1–2, distanceKm 100 → shipmentId, total', 'HTTP 201, status = Registered, baseFee = 7000 (тариф 50 + 10·1 кг + 0,10·100 км = 70 грн)'],
    ['4', 'GET /shipments/{shipmentId}', 'id з кроку 3', 'HTTP 200, status = Registered, customerId збігається'],
    ['5', 'POST /shipments/{shipmentId}/dispatch', 'id з кроку 3', 'HTTP 200, status = Dispatched'],
    ['6', 'POST /shipments/{shipmentId}/cancel', 'id з кроку 3, total з кроку 3', 'HTTP 200, status = Cancelled, refund = ⌊total·50%⌋ (персональне правило варіанта)'],
])
P('Динамічні дані:')
B(['унікальні code/reference генеруються через UUID у кожній ітерації (k6: crypto.randomUUID(); JMeter: ${__UUID()}), '
   'тому немає конфліктів UNIQUE і повторні запуски незалежні;',
   'ідентифікатори передаються з відповіді в наступний запит (k6: response.json(\'id\'); JMeter: JSON Extractor $.id → ${customerId}, ${parcelId}, ${shipmentId}, ${total});',
   'якщо передумова не виконана (наприклад, клієнт не створився), ітерація переривається і наступні запити з невалідним ID не надсилаються '
   '(k6: return після невдалого check; JMeter: Thread Group → «Start Next Thread Loop» on sampler error);',
   'URL з ID групуються під стабільною назвою (k6 tag name «GET /shipments/{id}», така сама назва sampler у JMeter) — це уникає high cardinality і дає однакові назви операцій в обох інструментах.'])
P('Think time 1 с виконується на початку кожної ітерації (k6: sleep(1); JMeter: Flow Control Action Pause 1000 мс). '
  'Отже, 1 VU ≈ 1 бізнес-сценарій/с ≈ 6 HTTP-запитів/с (закрита модель навантаження).')
P('Фрагмент k6-сценарію (повний код — k6/delivery-flow.js):', bold=True)
CODE('''const c = http.post(`${BASE_URL}/customers`, JSON.stringify({ code: `C-${uid}`, regular: false }), params('POST /customers'));
if (!check(c, { 'customer 201': (r) => r.status === 201 })) return;
const customerId = c.json('id');
...
const s = http.post(`${BASE_URL}/shipments`, JSON.stringify({
  reference: `S-${uid}`, customerId, parcelId, distanceKm: 100, urgent: false, pickup: false, couponValid: false,
}), params('POST /shipments'));
const shipmentId = s.json('id'); const total = s.json('total');
...
check(x, { 'refund = 50% total': (r) => r.json('refund') === Math.floor(total * 0.5) });''')
P('Структура JMeter Test Plan (jmeter/delivery-flow.jmx):', bold=True)
CODE('''Test Plan
├─ HTTP Request Defaults (host/port з -Jhost/-Jport, HttpClient4, keep-alive)
├─ HTTP Header Manager (Content-Type: application/json)
├─ Thread Group "main"   (threads/ramp/duration = ${__P(main_*)})
│   ├─ Flow Control Action: Pause ${__P(think_ms,1000)}
│   ├─ POST /customers      [Response Assertion 201, JSON Extractor customerId]
│   ├─ POST /parcels        [Response Assertion 201, JSON Extractor parcelId]
│   ├─ POST /shipments      [201, JSON Assertion status/baseFee, JSON Extractor shipmentId,total]
│   ├─ GET /shipments/{id}  [200, JSON Assertion status, customerId]
│   ├─ POST …/dispatch      [200, JSON Assertion status=Dispatched]
│   └─ POST …/cancel        [200, JSON Assertion status=Cancelled, JSR223 Assertion refund=50%]
└─ Thread Group "spike"  (той самий потік; ${__P(spike_*)}, startup delay — тільки для spike)''')

# ---------- 4 ----------
H('4. Workload profiles')
P('Профілі однакові для k6 і JMeter. Рівень «очікуваного навантаження» і рівень піку обрано за результатами калібрувального '
  'прогону (300/600/1000 VU по 25 с): до ~600 VU throughput зростав лінійно, на 1000 VU (≈4500 req/s) зростання сповільнилось, '
  'а p95 збільшився до ~160 мс. Тобто 1000 VU — межа насичення цього стенду, і на неї розраховано spike.')
T(['Тест', 'k6 (executor)', 'JMeter (jmeter/*.properties)', 'Сенс'], [
    ['Baseline', 'constant-vus: 1 VU, 60 с', 'main: 1 потік, ramp 0, 60 с', 'еталонний час відповіді без конкуренції'],
    ['Load', 'ramping-vus: 0→50 VU за 20 с, далі 50 VU до 120 с', 'main: 50 потоків, ramp-up 20 с, duration 120 с', 'очікуване робоче навантаження ≈ 50 сценаріїв/с ≈ 300 req/s'],
    ['Spike', 'background: constant 50 VU 100 с; spike: startTime 30 с, 0→950 VU за 10 с, 30 с утримання, різке зняття на 70-й с', 'main: 50 потоків 100 с; spike: 950 потоків, delay 30 с, ramp 10 с, duration 40 с', 'раптовий стрибок до 1000 VU (20× від норми) і фаза відновлення 70–100 с'],
])
P('Команди запуску:', bold=True)
CODE('''# k6
k6 run -e PROFILE=load -e BASE_URL=http://127.0.0.1:8080 \\
       --summary-export results/k6-load/summary.json --out csv=results/k6-load/raw.csv.gz k6/delivery-flow.js
# (з K6_WEB_DASHBOARD=true K6_WEB_DASHBOARD_EXPORT=results/k6-load/k6-report.html)

# JMeter (non-GUI + HTML dashboard)
jmeter -n -t jmeter/delivery-flow.jmx -q jmeter/load.properties -q jmeter/report.properties \\
       -l results/jmeter-load/results.jtl -e -o results/jmeter-load/html-report

# усе разом з перезапуском SUT, прогрівом і очищенням БД
scripts/run.sh k6 load ;  scripts/run.sh jmeter load ;  python3 scripts/analyze.py''')

# ---------- 5 ----------
H('5. Thresholds / acceptance criteria')
P('Критерії сформульовано до основних запусків. Обґрунтування: усі операції — інтерактивні дії оператора в UI доставки. '
  'У нормальному режимі відповідь має бути «миттєвою» для користувача (p95 ≤ 100–200 мс), а втрата запитів неприпустима (< 1%). '
  'Під час піку допускається деградація часу відповіді (p95 < 500 мс), але не допускаються помилки та порушення бізнес-правил. '
  'POST /shipments — найважча операція (читання клієнта й посилки, розрахунок тарифу, запис), тому для неї окремий поріг.')
T(['Метрика', 'Baseline', 'Load', 'Spike'], [
    ['avg http_req_duration', '< 50 мс', '< 100 мс', '< 250 мс'],
    ['p95 http_req_duration', '< 100 мс', '< 200 мс', '< 500 мс'],
    ['p95 POST /shipments', '< 150 мс', '< 250 мс', '< 600 мс'],
    ['error rate (http_req_failed)', '< 1%', '< 1%', '< 1%'],
    ['checks / assertions', '> 99%', '> 99%', '> 99%'],
])
P('У k6 пороги задані в options.thresholds (k6 сам позначає запуск як PASS/FAIL і повертає ненульовий код виходу). '
  'JMeter не має вбудованих SLA-порогів, тому ті самі критерії перевіряються скриптом scripts/analyze.py за JTL-файлом; '
  'додатково в HTML-звіті JMeter налаштовано APDEX (satisfied 200 мс, tolerated 1000 мс).')

# ---------- 6 ----------
H('6. Результати')
P('Пояснення метрик: average — середній час відповіді (чутливий до викидів); p95 — 95% запитів виконались не довше цього часу '
  '(показує «хвіст», який відчувають користувачі); throughput — кількість HTTP-запитів за секунду (окремо наведено кількість повних бізнес-сценаріїв за секунду: 1 сценарій = 6 запитів); '
  'error rate — частка неуспішних HTTP-запитів (не 2xx/3xx або мережева помилка). Checks/assertions — частка успішних перевірок бізнес-логіки.')
rows = []
for p in ['baseline', 'load', 'spike']:
    for t in ['k6', 'jmeter']:
        s = g(f'{t}-{p}')
        rows.append([f'{t} {p}', s['max_vus'], s['requests'], s['rps'], s['flows_per_s'], s['avg'], s['med'], s['p95'], s['p99'], s['max'],
                     f"{s['err']*100:.2f}%", f"{s['checks']*100:.2f}%"])
T(['Запуск', 'Max VU', 'Запитів', 'req/s', 'сценар./с', 'avg, мс', 'med, мс', 'p95, мс', 'p99, мс', 'max, мс', 'Error rate', 'Checks OK'], rows, size=8)

P('Перевірка thresholds:', bold=True)
names = list(g('k6-baseline')['thresholds'].keys())
rows = []
for p in ['baseline', 'load', 'spike']:
    for t in ['k6', 'jmeter']:
        s = g(f'{t}-{p}'); ks = list(s['thresholds'].keys())
        rows.append([f'{t} {p}'] + [f"{k.split(' <')[0].split(' >')[0]}: {'PASS' if v else 'FAIL'}" for k, v in s['thresholds'].items()])
T(['Запуск', 'avg', 'p95', 'p95 POST /shipments', 'error rate', 'checks'], [[r[0]] + [x.split(': ')[1] for x in r[1:]] for r in rows], size=9)
P('Усі 30 перевірок порогів пройдено (✓ також у підсумку k6 — results/k6-*/console.txt).')

P('Час відповіді за операціями (avg / p95, мс):', bold=True)
ops = list(g('k6-baseline')['by_endpoint'].keys())
T(['Операція'] + [f'{t} {p}' for p in ['baseline', 'load', 'spike'] for t in ['k6', 'JM']],
  [[o] + [f"{g(f'{t}-{p}')['by_endpoint'][o]['avg']} / {g(f'{t}-{p}')['by_endpoint'][o]['p95']}"
          for p in ['baseline', 'load', 'spike'] for t in ['k6', 'jmeter']] for o in ops], size=8)

P('Spike за фазами:', bold=True)
rows = []
for t in ['k6', 'jmeter']:
    for ph, s in g(f'{t}-spike')['phases'].items():
        rows.append([t, ph, s['rps'], s['avg'], s['p95'], s['p99'], s['max'], f"{s['err']*100:.2f}%"])
T(['Інструмент', 'Фаза', 'req/s', 'avg, мс', 'p95, мс', 'p99, мс', 'max, мс', 'Error rate'], rows, size=9)

P('Ресурси (CPU у % одного ядра; 400% = вся 4-ядерна машина):', bold=True)
rows = []
for p in ['baseline', 'load', 'spike']:
    for t in ['k6', 'jmeter']:
        s = g(f'{t}-{p}'); rows.append([f'{t} {p}', s['sut_cpu_avg'], s['sut_cpu_max'], f"{s['host_cpu_max']}%"])
T(['Запуск', 'CPU SUT avg', 'CPU SUT max', 'Макс. завантаження всієї машини'], rows)
P('Контроль у БД після тестів: кількість відправлень у статусі Cancelled відповідає кількості успішних сценаріїв '
  '(k6: 60 / 5471 / 35579; JMeter: 58 / 5413 / 22257). Поодинокі записи Registered/Dispatched у JMeter load/spike — ітерації, '
  'перервані в момент завершення duration Thread Group (JMeter зупиняє потік посеред ітерації; k6 дає VU завершити ітерацію за gracefulRampDown/gracefulStop). '
  'Помилками SUT вони не є.')

# ---------- 7 ----------
H('7. Графічний звіт')
P('Інструменти формують власні HTML-звіти: k6 Web Dashboard export — results/k6-<profile>/k6-report.html; '
  'JMeter HTML Dashboard — results/jmeter-<profile>/html-report/index.html. Нижче — зведені графіки (scripts/analyze.py), '
  'на яких обидва інструменти показано на одній осі часу з вікном агрегації 2 с.')
IMG('timeline-baseline.png', 'Рис. 1. Baseline: VU, throughput, avg/p95, error rate, CPU', 15)
IMG('timeline-load.png', 'Рис. 2. Load: VU, throughput, avg/p95, error rate, CPU', 15)
IMG('timeline-spike.png', 'Рис. 3. Spike: VU, throughput, avg/p95, error rate, CPU (виділено фазу піку 30–70 с)', 15)
IMG('cmp-avg.png', 'Рис. 4. Average response time за типами тестів (логарифмічна шкала)', 13)
IMG('cmp-p95.png', 'Рис. 5. p95 за типами тестів (логарифмічна шкала)', 13)
IMG('cmp-rps.png', 'Рис. 6. Throughput (HTTP req/s) за типами тестів', 13)
IMG('endpoints-load.png', 'Рис. 7. Load: p95 за окремими операціями', 15)

# ---------- 8 ----------
kb, kl, ks = g('k6-baseline'), g('k6-load'), g('k6-spike')
jb, jl, js = g('jmeter-baseline'), g('jmeter-load'), g('jmeter-spike')
kph = ks['phases']; jph = js['phases']; ph = list(kph.keys())
H('8. Порівняння типів навантаження та інтерпретація')
P('Baseline (1 VU).', bold=True)
P(f'Throughput ≈ {kb["rps"]} req/s (1 сценарій/с), що точно відповідає закритій моделі 1 VU + think time 1 с. '
  f'avg ≈ {kb["avg"]}–{jb["avg"]} мс, p95 ≈ {kb["p95"]}–{jb["p95"]} мс. Це еталон «чистої» вартості операцій. Найдовша — POST /customers '
  '(перший запит ітерації після 1 с паузи: з\'єднання й кеші «холодніші»), найлегша — GET /shipments/{id}. Помилок немає, CPU SUT у середньому ~2%.')
P('Load (50 VU).', bold=True)
P(f'Throughput зріс у ~45 разів до {kl["rps"]} req/s ({kl["flows_per_s"]} сценаріїв/с) — пропорційно кількості VU, тобто система '
  f'ще не насичена. Час відповіді не погіршився, а навіть трохи зменшився (k6 avg {kb["avg"]} → {kl["avg"]} мс, p95 {kb["p95"]} → {kl["p95"]} мс): '
  'при постійному потоці запитів JIT-компілятор JVM, пул з\'єднань HikariCP, кеші PostgreSQL і keep-alive-з\'єднання залишаються «гарячими». '
  'CPU SUT у середньому ~18% одного ядра. Error rate 0%. Висновок: очікуване навантаження система витримує з великим запасом.')
P('Spike (50 → 1000 VU).', bold=True)
P(f'До піку метрики збігаються з load-тестом (~290 req/s). Під час піку k6 підняв throughput до ~{kph[ph[1]]["rps"]:.0f} req/s '
  f'(у середньому за фазу; максимум ~5500 req/s), але це лише ~{kph[ph[1]]["rps"]/6000*100:.0f}% від теоретичних 6000 req/s для 1000 VU — система вийшла на насичення. '
  f'Через це зросли черги, і час відповіді збільшився: avg {kph[ph[0]]["avg"]} → {kph[ph[1]]["avg"]} мс, p95 {kph[ph[0]]["p95"]} → {kph[ph[1]]["p95"]} мс, max {kph[ph[1]]["max"]} мс '
  f'(у JMeter: p95 {jph[ph[1]]["p95"]} мс, max {jph[ph[1]]["max"]} мс). На графіку CPU видно причину: завантаження всієї 4-ядерної машини під час піку ≈ 97–100% '
  '(SUT JVM ≈ 110–170% ядра, решта — генератор навантаження та PostgreSQL). Вузьке місце стенду — CPU, спільний для SUT, БД і генератора. '
  'Найбільше зростання — у POST /shipments (найважча операція з кількома SQL-запитами, конкурує за 10 з\'єднань HikariCP).')
P(f'Важливо: навіть на піку error rate = 0%, усі перевірки бізнес-логіки (зокрема refund 50%) пройшли — система деградує «м\'яко», '
  'збільшуючи затримку, але не втрачаючи й не псуючи дані. Після зняття піку (фаза відновлення 70–100 с) час відповіді за кілька секунд '
  f'повернувся до рівня load-тесту (JMeter: avg {jph[ph[2]]["avg"]} мс, p95 {jph[ph[2]]["p95"]} мс) — накопичених черг/витоків не виявлено. '
  f'У k6 загальний показник фази відновлення трохи вищий (p95 {kph[ph[2]]["p95"]} мс, {kph[ph[2]]["rps"]} req/s), бо перші ~2 с цієї фази k6 ще дозавершує ітерації 950 spike-VU (gracefulRampDown 5 с).')
P('Зауваження щодо загального p95: для spike значення p95 за весь тест змішує три різні режими, тому для інтерпретації використано p95 окремо за фазами і часові графіки.')

H('9. Порівняння k6 і JMeter')
T(['Аспект', 'k6', 'JMeter'], [
    ['Опис сценарію', 'JavaScript-код (k6/delivery-flow.js), зручно для Git і code review', 'XML Test Plan (*.jmx), зазвичай редагується у GUI; тут згенерований скриптом scripts/gen_jmx.py'],
    ['Профіль навантаження', 'scenarios + executors (constant-vus, ramping-vus, startTime)', 'Thread Group: threads, ramp-up, duration, startup delay; для spike — дві Thread Group'],
    ['Dynamic data', 'response.json(\'id\') у змінну', 'JSON Extractor → ${var}'],
    ['Перевірки', 'check() — не впливає на http_req_failed', 'Assertions — невдала assertion робить sample неуспішним (входить у Error %)'],
    ['Thresholds', 'вбудовані, PASS/FAIL і код виходу процесу', 'немає вбудованих SLA-порогів; APDEX у звіті + зовнішня перевірка JTL'],
    ['Звіт', 'Web Dashboard / HTML export, summary JSON', 'HTML Dashboard з багатьма графіками, JTL (CSV)'],
    ['Точність часу', 'мікросекунди (float, мс)', 'цілі мілісекунди'],
    ['Завершення тесту', 'gracefulStop/gracefulRampDown — ітерації дозавершуються', 'потоки зупиняються посеред ітерації (див. записи Registered/Dispatched у БД)'],
    ['Ресурси генератора', 'Go, легкі goroutine-VU', 'Java, 1 OS-потік на користувача — значно більше CPU/RAM'],
])
P('Порівняння результатів:', bold=True)
B([f'Baseline і load: результати дуже близькі — throughput відрізняється < 2% ({kl["rps"]} vs {jl["rps"]} req/s), avg і p95 відрізняються на ~0,5–1 мс. '
   'Невелика різниця пояснюється округленням JMeter до цілих мс (p95 2,2 мс у k6 ≈ 3 мс у JMeter) і різними HTTP-клієнтами.',
   f'Spike: результати суттєво різні — JMeter отримав {js["rps"]} req/s проти {ks["rps"]} у k6 і p95 {js["p95"]} мс проти {ks["p95"]} мс. '
   'Причина — не SUT, а генератор: 1000 Java-потоків JMeter на тій самій 4-ядерній машині споживають помітно більше CPU, ніж k6, '
   'тому на SUT лишається менше ресурсів, а час відповіді з точки зору JMeter включає ще й очікування планування власних потоків. '
   'Наприкінці піку (≈ 60–68 с), коли JMeter-потоки розподілились у часі, його throughput наздогнав k6 (~5000 req/s). '
   'Тобто на піку JMeter частково вимірює обмеження самого генератора (coordinated omission/«client-side bottleneck»).',
   'Обидва інструменти дали однаковий якісний висновок: система витримує очікуване навантаження з великим запасом, на 20-кратному піку деградує лише за часом відповіді (без помилок), і швидко відновлюється.'])

H('10. Обмеження експерименту')
B(['Генератор і SUT (і PostgreSQL) працюють на одній 4-ядерній машині — на піку вони конкурують за CPU; абсолютні значення не переносяться на інше обладнання.',
   'Зовнішня HTTP-політика (SHIPPING_POLICY_URL) не підключалась — використовувалась локальна політика SUT; затримка зовнішнього сервісу не моделювалась.',
   'Тривалість тестів невелика (1–2 хв), тому довгострокові ефекти (накопичення даних, GC, витоки пам\'яті) не досліджувались — для цього потрібен soak test.',
   'Серверних метрик БД (pg_stat_activity, очікування пулу HikariCP) не знімалось; висновок про bottleneck зроблено за CPU процесу й машини.'])

H('11. Висновки')
B(['Розроблено performance-сценарій із 6 пов\'язаних HTTP-запитів з передачею динамічних даних (customerId, parcelId, shipmentId, total) та перевіркою бізнес-правил, включно з персональним правилом варіанта (повернення 50% при скасуванні Dispatched).',
   'Сценарій реалізовано в k6 і JMeter з однаковим SUT, сценарієм і workload profile; проведено baseline, load і spike тести в однакових умовах (перезапуск SUT, прогрів, чиста БД).',
   f'Baseline: avg ≈ 2–3 мс, p95 ≈ 3,5–5 мс, 6 req/s. Load (50 VU): {kl["rps"]} req/s, p95 ≈ 2–3 мс, 0% помилок — запас продуктивності великий.',
   f'Spike (1000 VU): система вийшла на насичення CPU стенду; throughput до ~5000 req/s, p95 зріс до {ks["p95"]} мс (k6) / {js["p95"]} мс (JMeter), помилок 0%, після піку — швидке відновлення.',
   'Усі встановлені thresholds виконано для всіх шести запусків.',
   'k6 зручніший для коду-як-сценарію, CI і порогів, а також економніший як генератор; JMeter дає багатший HTML-звіт і GUI, але потребує більше ресурсів — що прямо вплинуло на результати spike-тесту на спільній машині.'])

H('Додаток. Структура файлів')
CODE('''lab7/
├─ k6/delivery-flow.js            сценарій k6 (PROFILE=baseline|load|spike)
├─ jmeter/delivery-flow.jmx       Test Plan JMeter
├─ jmeter/{baseline,load,spike}.properties, report.properties
├─ scripts/run.sh                 запуск одного тесту (перезапуск SUT, прогрів, очищення БД, моніторинг)
├─ scripts/monitor.py             CPU/RSS SUT і CPU машини
├─ scripts/gen_jmx.py             генератор .jmx
├─ scripts/analyze.py             метрики, thresholds для JMeter, графіки
├─ results/<tool>-<profile>/      сирі дані, консоль, HTML-звіти (k6-report.html / html-report/)
└─ report/                        звіт, графіки, metrics.md''')
doc.save(f'{ROOT}/report/Lab7_Kyryliuk_343A.docx')
print('saved')
