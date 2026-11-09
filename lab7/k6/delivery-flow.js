// Лабораторна №7 — Performance and Load Testing (k6)
// SUT B: group 2 / variant09 — «Доставка посилок» (Java, Spring Boot, PostgreSQL)
//
// Одна ітерація = один бізнес-сценарій «оформити відправлення і скасувати його після передачі в доставку»
// (6 пов'язаних HTTP-запитів, ID передаються динамічно з відповіді у наступний запит):
//   1. POST /customers                -> customerId
//   2. POST /parcels                  -> parcelId
//   3. POST /shipments                (customerId, parcelId) -> shipmentId, total
//   4. GET  /shipments/{id}           перевірка збереженого стану Registered
//   5. POST /shipments/{id}/dispatch  -> Dispatched
//   6. POST /shipments/{id}/cancel    -> Cancelled, refund = floor(total * 50%) (персональне правило)
//
// Профіль обирається змінною PROFILE = baseline | load | spike.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8080';
const PROFILE = __ENV.PROFILE || 'baseline';
const THINK_TIME = Number(__ENV.THINK_TIME || 1); // пауза між бізнес-сценаріями, с

// ---------- Workload profiles (ідентичні профілям JMeter, див. jmeter/*.properties) ----------
// Модель закрита (VUs + think time 1 с). 1 VU ~ 1 бізнес-сценарій/с ~ 6 HTTP-запитів/с.
const PROFILES = {
  // baseline: 1 користувач, 60 с — еталонна продуктивність без конкуренції
  baseline: {
    main: { executor: 'constant-vus', vus: 1, duration: '60s' },
  },
  // load: очікуване робоче навантаження — рампа 0 -> 50 VU за 20 с, утримання до 120 с (~300 req/s)
  load: {
    main: {
      executor: 'ramping-vus', startVUs: 0,
      stages: [ { duration: '20s', target: 50 }, { duration: '100s', target: 50 } ],
      gracefulRampDown: '5s',
    },
  },
  // spike: фон 50 VU протягом 100 с (робоче навантаження);
  // з 30-ї с за 10 с додаємо +950 VU (разом 1000 = 20x норми), тримаємо 30 с, різко знімаємо на 70-й с,
  // 70–100 с — фаза відновлення.
  spike: {
    background: { executor: 'constant-vus', vus: 50, duration: '100s' },
    spike: {
      executor: 'ramping-vus', startVUs: 0, startTime: '30s',
      stages: [ { duration: '10s', target: 950 }, { duration: '30s', target: 950 }, { duration: '1s', target: 0 } ],
      gracefulRampDown: '5s',
    },
  },
};

// ---------- Thresholds / acceptance criteria ----------
// Обґрунтування: це інтерактивні операції UI оператора доставки. Для нормального режиму
// вимагаємо p95 < 100–200 мс і < 1% помилок; для піку допускаємо деградацію часу до p95 < 500 мс,
// але НЕ допускаємо втрати запитів (< 1% помилок) і порушення бізнес-правил (checks > 99%).
const THRESHOLDS = {
  baseline: {
    http_req_duration: ['avg<50', 'p(95)<100'],
    'http_req_duration{name:POST /shipments}': ['p(95)<150'],
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
  },
  load: {
    http_req_duration: ['avg<100', 'p(95)<200'],
    'http_req_duration{name:POST /shipments}': ['p(95)<250'],
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
  },
  spike: {
    http_req_duration: ['avg<250', 'p(95)<500'],
    'http_req_duration{name:POST /shipments}': ['p(95)<600'],
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
  },
};

export const options = {
  scenarios: PROFILES[PROFILE],
  thresholds: THRESHOLDS[PROFILE],
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
  tags: { profile: PROFILE, tool: 'k6' },
};

// Тривалість повного бізнес-сценарію без think time
const flowDuration = new Trend('flow_duration', true);
const flowsCompleted = new Counter('flows_completed');

const JSON_HDR = { headers: { 'Content-Type': 'application/json' } };
const params = (name) => Object.assign({ tags: { name } }, JSON_HDR);

export default function () {
  // Think time на ПОЧАТКУ ітерації: так само, як Flow Control Action у JMeter.
  // Завдяки цьому невдала ітерація (return) теж має паузу — однакова поведінка в обох інструментах.
  sleep(THINK_TIME);
  const uid = crypto.randomUUID(); // 36 символів; code/reference <= 40
  const started = Date.now();

  // 1. Клієнт
  const c = http.post(`${BASE_URL}/customers`, JSON.stringify({ code: `C-${uid}`, regular: false }), params('POST /customers'));
  if (!check(c, { 'customer 201': (r) => r.status === 201 })) return;
  const customerId = c.json('id');

  // 2. Посилка (1000 г, 100 км -> базовий тариф 70 грн = 7000 коп.)
  const p = http.post(`${BASE_URL}/parcels`,
    JSON.stringify({ code: `P-${uid}`, weightGrams: 1000, declaredValue: 10000, fragile: false }), params('POST /parcels'));
  if (!check(p, { 'parcel 201': (r) => r.status === 201 })) return;
  const parcelId = p.json('id');

  // 3. Відправлення — використовує ID з кроків 1 і 2
  const s = http.post(`${BASE_URL}/shipments`, JSON.stringify({
    reference: `S-${uid}`, customerId, parcelId, distanceKm: 100, urgent: false, pickup: false, couponValid: false,
  }), params('POST /shipments'));
  if (!check(s, {
    'shipment 201': (r) => r.status === 201,
    'shipment Registered, baseFee 7000': (r) => r.status === 201 && r.json('status') === 'Registered' && r.json('baseFee') === 7000,
  })) return;
  const shipmentId = s.json('id');
  const total = s.json('total');

  // 4. Читання збереженого стану
  const g = http.get(`${BASE_URL}/shipments/${shipmentId}`, { tags: { name: 'GET /shipments/{id}' } });
  check(g, { 'get 200 Registered': (r) => r.status === 200 && r.json('status') === 'Registered' && r.json('customerId') === customerId });

  // 5. Передача в доставку
  const d = http.post(`${BASE_URL}/shipments/${shipmentId}/dispatch`, null, { tags: { name: 'POST /shipments/{id}/dispatch' } });
  if (!check(d, { 'dispatch 200 Dispatched': (r) => r.status === 200 && r.json('status') === 'Dispatched' })) return;

  // 6. Скасування: персональне правило — Dispatched повертає 50% total
  const x = http.post(`${BASE_URL}/shipments/${shipmentId}/cancel`, null, { tags: { name: 'POST /shipments/{id}/cancel' } });
  const ok = check(x, {
    'cancel 200 Cancelled': (r) => r.status === 200 && r.json('status') === 'Cancelled',
    'refund = 50% total': (r) => r.status === 200 && r.json('refund') === Math.floor(total * 0.5),
  });
  if (ok) { flowDuration.add(Date.now() - started); flowsCompleted.add(1); }
}
