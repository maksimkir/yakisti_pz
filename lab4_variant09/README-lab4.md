# Лабораторна робота №4 — Інтеграційне тестування
**Варіант 09 — Доставка посилок (SUT B)** · Java 21 · PostgreSQL 17 · JUnit 5 · Mockito

Готовий SUT B (production-код, `migrations/`, `pom.xml`, `EnvironmentTest.java`) узято з
репозиторію курсу без змін. Реалізовано лише Integration Test Suite —
`src/test/java/ua/course/delivery/ShippingIntegrationTest.java` (13 тестів).

## 1. Перевірено реальним запуском

Усе нижче реально виконано проти справжньої PostgreSQL (не лише написано):

```
13 tests found, 12 successful, 1 failed (навмисно, див. розділ 5)
```

Запущено 3 рази поспіль — результат однаковий щоразу (13/13, 12/1), а після кожного
прогону в таблицях `customers`, `parcels`, `shipments` залишається 0 рядків — тести
повністю незалежні й повторювані (вимога 3.7 методички).

## 2. Підготовка середовища (п. 3.2)

```sql
CREATE ROLE delivery_student LOGIN PASSWORD 'ваш_пароль';
CREATE DATABASE delivery_variant09_test OWNER delivery_student;
```
```sh
psql -h localhost -U delivery_student -d delivery_variant09_test \
     -v ON_ERROR_STOP=1 -f migrations/V1__create_tables.sql
```
Змінні середовища — за `.env.example` (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`,
`DB_PASSWORD`). Запуск:
```sh
mvn compile
mvn test
```

## 3. Integration Boundary (п. 3.3)

```
ShippingService
  ├── CustomerRepository  ─┐
  ├── ParcelRepository     ├─ REAL — справжнє JDBC-з'єднання, справжня тестова БД
  ├── ShipmentRepository  ─┘
  └── ShippingPolicy        — ПОЗА межею: Stub (лямбда) або Mock (Mockito)
```

**Чому саме так:**
- `CustomerRepository`, `ParcelRepository`, `ShipmentRepository` — не підміняються, бо
  саме їхня взаємодія з реальною БД (SQL, схема, маппінг рядків у `record`) є предметом
  перевірки цієї лабораторної.
- `ShippingPolicy` — зовнішній дозвіл на доставку. У production це може бути HTTP-виклик
  (`HttpShippingPolicy`), тобто окрема система поза межею "Service → Repository → DB".
  README SUT B прямо каже: "ShippingPolicy — Stub/Mock чи лямбдою".

## 4. Персональне бізнес-правило варіанта

**Повернення залежно від статусу:** скасування `Registered` → 100% `total`,
`Dispatched` → 50% `total`. Скасування `Delivered` та повторне скасування — заборонені.

Перевірено тестами:
- `cancelRefundPercentage_dependsOnPreviousStatus_persistedState` (параметризований:
  обидва випадки — 100% і 50%)
- `cancel_fromDelivered_isForbidden_stateUnchanged` (заборонений випадок)

## 5. Контрольна вимога — навмисно провальний тест

Методичка (розділ 5) вимагає залишити один тест навмисно `FAILED`, незалежно від
реальної поведінки SUT, і не виправляти його перед захистом.

Тест: `cancel_fromDispatched_intentionallyWrongExpectation_mustStayFailing`.

Він виконує правильний сценарій (`Registered → Dispatched → cancel`), але свідомо
звіряє результат із неправильним очікуванням: що `refund` дорівнює 100% `total`,
хоча за персональним правилом варіанта при скасуванні з `Dispatched` має бути 50%.

Реальний прогін підтверджує: `expected: <7000> but was: <3500>` — тобто сам SUT працює
правильно (повертає 3500 = 50% від 7000), а "неправильний" саме assert у тесті. Це і є
суть навмисного FAILED-тесту: контрольована, пояснювана відмова, а не дефект коду.

## 6. Повний перелік тестів (13 шт.)

### Repository ↔ Database (п. 3.4)

| Метод | Суфікс | Що перевіряє |
|---|---|---|
| `customerRepository_createAndFindById_repositoryState` | `_repositoryState` | create → findById повертає ті самі дані |
| `parcelRepository_createAndFindById_repositoryState` | `_repositoryState` | create → findById повертає ті самі дані |
| `shipmentRepository_updateStatusThenDelete_removesRecordFromDatabase` | — | updateStatus() змінює стан у БД; delete() видаляє запис |

### Service → Repository → Database (п. 3.5)

| Метод | Суфікс | Сценарій |
|---|---|---|
| `createShipment_policyAllows_registersShipmentWithCorrectFee_serviceState` | `_serviceState` | **Позитивний**: дозволена доставка, коректний тариф (7000 коп = 70 грн за 1000 г/100 км, збігається з прикладом у README SUT) |
| `createShipment_policyRejects_throwsAndDoesNotPersist_serviceState` | `_serviceState` | **Негативний**: заборонена доставка — виняток, запис не створюється |
| `createShipment_distanceOutOfRange_rejectedBeforePolicyIsInvoked` | — | **Граничний**: невалідна відстань відхиляється ДО звернення до `ShippingPolicy` (перевірено через `verify(mock, never())`) |
| `createShipment_invokesPolicyExactlyOnceWithCorrectArguments` | — | Interaction-based: `ShippingPolicy` викликано 1 раз з правильними customer/parcel/distance (`ArgumentCaptor`) |
| `cancelRefundPercentage_dependsOnPreviousStatus_persistedState` | `_persistedState` | **Персональне правило**: 100%/50% повернення залежно від статусу; перевірка через повторний `findById` |
| `cancel_fromDelivered_isForbidden_stateUnchanged` | — | **Персональне правило, негативний**: скасування `Delivered` заборонене, стан БД не змінюється |
| `dispatchThenDeliver_transitionsStatusAcrossFullLifecycle` | — | **Альтернативний**: повний цикл `Registered → Dispatched → Delivered` |
| `cancel_fromDispatched_intentionallyWrongExpectation_mustStayFailing` | — | **Навмисно FAILED** (розділ 5) |

## 7. Незалежність і повторюваність (п. 3.7)

- Кожен тест відкриває власне з'єднання в `@BeforeEach` і закриває в `@AfterEach`.
- Клієнт/посилка/відправлення створюються з унікальним кодом (`UUID`-суфікс) у кожному
  тесті — жодних спільних fixture-даних.
- `@AfterEach` видаляє все створене цим тестом (спочатку `shipments`, потім
  `customers`/`parcels` — через FK `ON DELETE RESTRICT`) **незалежно від результату
  тесту**, тому БД лишається чистою навіть після навмисно провального тесту.
- Підтверджено: 3 послідовні запуски дають однаковий результат, 0 рядків у таблицях
  після кожного прогону.

## 8. Підготовка до захисту

**Сценарій демонстрації (п. 5 методички):**

1. Пояснити структуру SUT B: `ShippingService` + 3 Repository + `ShippingPolicy`.
2. Показати персональне правило (розділ 4 цього файлу).
3. Пояснити Integration Boundary (розділ 3): чому Repository real, а Policy — Test Double.
4. Показати `.env`/`Database.java` і запустити `EnvironmentTest` (підключення).
5. `mvn test` — повний набір, 12 passed + 1 навмисно failed.
6. Показати один Repository-тест (`customerRepository_createAndFindById_repositoryState`).
7. Показати один Service-тест (`createShipment_policyAllows_..._serviceState`).
8. Позитивний і негативний бізнес-сценарій (тести `_serviceState`).
9. Тест персонального правила (`cancelRefundPercentage_..._persistedState`).
10. Показати перевірку фактичного стану БД після Service-операції (повторний `findById`
    у `cancelRefundPercentage_..._persistedState` або `dispatchThenDeliver_...`).
11. Пояснити незалежність тестів (розділ 7).
12. Пояснити навмисно провальний тест (розділ 5) — **не виправляти**.

**Типові питання:**

- *Чому це integration test, а не unit test?* Використовується реальне з'єднання з
  PostgreSQL і реальні Repository — перевіряється взаємодія Service з фактичною БД
  (SQL, схема, маппінг), а не ізольована бізнес-логіка з підміненими залежностями.
- *Чому Repository не підмінюється Mock?* Бо саме його коректна робота з реальною БД —
  предмет цієї лабораторної. Mock Repository перетворив би тест назад на unit test.
- *Чому ShippingPolicy — Test Double?* Вона поза межею "Service → Repository → DB": у
  production може бути зовнішнім HTTP-викликом (`HttpShippingPolicy`), тому її ізольовано
  Stub/Mock, щоб тест не залежав від зовнішньої системи.
- *Який стан БД очікується після операції?* Наприклад, після `cancel()` з `Dispatched`:
  `status=Cancelled`, `refund=total/2`, перевірено повторним зверненням до Repository, а
  не лише значенням, що повернув `Service`.
- *Чому перевірки лише return value Service недостатньо?* Return value можна підробити
  або отримати з багу, що не дійшов до БД; лише повторний запит через Repository
  підтверджує, що дані дійсно збережені.
