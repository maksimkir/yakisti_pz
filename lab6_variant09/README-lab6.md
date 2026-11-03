# Лабораторна робота №6 — Automated REST API Testing
**Варіант 09 — Доставка посилок (SUT B)** · Java 17 · Spring Boot 3.4.13 · RestAssured 5.5.0 · Testcontainers 1.21.4 · PostgreSQL 16

SUT оновлено автором курсу: до production-коду додано REST-рівень (`DeliveryApplication`,
`CustomerController`, `ParcelController`, `ShipmentsController`, `ApiExceptionHandler`,
`PolicyConfiguration`) поверх того самого `ShippingService`/Repository з лаб. №4–5.
Жоден production-файл не змінювався. Новий файл —
`src/test/java/ua/course/delivery/DeliveryApiTest.java` (15 тестових методів, 16 запусків тестів).

> **Головна відмінність від лаб. №4–5:** там тестувався `ShippingService` напряму —
> Java-виклики методів усередині однієї JVM. Тут SUT тестується **тільки через HTTP**:
> `RestAssured` надсилає реальні HTTP-запити до запущеного застосунку, а той — до реальної
> PostgreSQL. Жодного прямого звернення до `ShippingService` чи Repository з тестів немає.

## ⚠️ Важливе застереження

Так само, як і з лаб. №5, я **не можу перевірити цей код запуском** — потрібен Docker,
якого немає в моєму середовищі. Я ретельно звірив кожен HTTP-контракт із реальним кодом
контролерів і `ApiExceptionHandler` вашого SUT (статус-коди, поля `code`/`message`,
формат тіла), але перша перевірка «наживо» — на вашому комп'ютері.

## 1. Що потрібно

Те саме, що й для лаб. №5: **Docker Desktop запущений**. Локальна PostgreSQL,
змінні середовища (`DB_HOST` тощо) — **не потрібні**: тести самі піднімають контейнер
із PostgreSQL (Testcontainers) і самі запускають увесь Spring Boot застосунок усередині
тестового процесу на випадковому вільному порту.

## 2. Запуск

```
cd lab6_variant09
mvn test
```

Очікується: **16 тестів, 0 помилок** (15 методів; один параметризований розгортається у 2 запуски).

## 3. Як це влаштовано

### 3.1. Застосунок піднімається сам, у межах тесту

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
class DeliveryApiTest {
    @LocalServerPort
    int port;
```

`@SpringBootTest(webEnvironment = RANDOM_PORT)` запускає весь застосунок
(`DeliveryApplication`) по-справжньому — з реальним вбудованим веб-сервером — на вільному
порту, який Spring сам підбирає й повертає через `@LocalServerPort`. RestAssured далі
звертається саме на цей порт:

```java
@BeforeEach
void configureRestAssured() {
    RestAssured.baseURI = "http://127.0.0.1";
    RestAssured.port = port;
}
```

### 3.2. База даних — та сама схема Testcontainers, що й у лаб. №5

```java
@Container
static final PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>(...)
        .withInitScript("db/V1__create_tables.sql");

@DynamicPropertySource
static void datasourceProperties(DynamicPropertyRegistry registry) {
    registry.add("spring.datasource.url", postgres::getJdbcUrl);
    registry.add("spring.datasource.username", postgres::getUsername);
    registry.add("spring.datasource.password", postgres::getPassword);
}
```

`@DynamicPropertySource` підміняє налаштування підключення Spring Boot на ті, що реально
призначив Testcontainers — до того, як Spring почне піднімати контекст. Жодних локальних
БД, жодного ручного `psql`.

### 3.3. Зовнішня HTTP-політика

`SHIPPING_POLICY_URL` навмисно не задається. За документацією SUT (README, розділ
«REST API»): «Без цієї змінної локальна політика дозволяє операції». Межу
Service↔зовнішня HTTP-залежність уже перевірено в лаб. №5 через WireMock; тут предмет
перевірки — сам REST-контракт (коди статусів, тіло відповіді, зміна стану ресурсу), тому
зовнішня залежність свідомо спрощена до «завжди дозволено» — так само, як це передбачено
в самій конфігурації SUT (`PolicyConfiguration`), а не додано мною в обхід.

## 4. Відповідність завданню (розділ 3 методички)

| № | Вимога | Тест(и) |
|---|---|---|
| 1 | POST — створення ресурсу: 201, id, основні поля | `createCustomer_returns201WithLocationAndFields`, `createParcel_returns201WithLocationAndFields`, `createShipment_returns201WithCorrectFeeAndStatus` |
| 2 | GET за id: 200, дані відповідають створеному | `getCustomer_returnsSavedData`, `getParcel_returnsSavedData`, `getShipment_returnsSavedData` |
| 3 | GET неіснуючого: 404, поля `code`/`message` | `getNonExistentShipment_returns404WithErrorContract` |
| 4 | Action endpoint: 200, новий стан | `dispatchShipment_changesStatusTo200` |
| 5 | Повторна/заборонена дія: 409, error response | `repeatedDispatch_returns409AndLeavesStateUnchanged`, `deliverWithoutDispatch_returns409AndDoesNotChangeState` |
| 6 | Незмінність після 409: наступний GET підтверджує | `repeatedDispatch_returns409AndLeavesStateUnchanged` (другий GET у тому самому тесті) |
| 7 | Персональне правило: ≥2 набори даних, параметризація | `cancelRefundPercentage_dependsOnPreviousStatus` (Registered→100%, Dispatched→50%) + `cancelDelivered_isForbidden` (заборонений випадок) |
| 8 | Workflow POST→GET→action→GET, id передаються динамічно | `fullWorkflow_customerParcelShipmentDispatchDeliver` |

Плюс один додатковий тест на error contract для `400 INVALID_REQUEST`
(`createShipment_invalidDistance_returns400`) — зайвий, але змістовний приклад
третього типу помилки (крім 404 і 409).

Разом: **15 тестових методів (16 запусків)** (вимога — щонайменше 8–10).

## 5. Приклад workflow-тесту (п. 3.8, п. 6.6 захисту)

```java
long customerId = ...post /customers...extract id...
long parcelId   = ...post /parcels...extract id...
long shipmentId = ...post /shipments using customerId and parcelId from above...extract id...

get /shipments/{shipmentId}   -> Registered
post /shipments/{shipmentId}/dispatch -> Dispatched
get /shipments/{shipmentId}   -> Dispatched
post /shipments/{shipmentId}/deliver  -> Delivered
get /shipments/{shipmentId}   -> Delivered
```

Жоден id не захардкоджений — кожен наступний запит використовує значення, здобуте з
`response.jsonPath().getLong("id")` попереднього запиту.

## 6. Error contract (п. 3.3, 3.5-3.7 вимог)

Усі помилки SUT повертає в єдиному форматі (`ApiExceptionHandler.ApiError`):
```json
{"code": "NOT_FOUND", "message": "Відправлення не знайдено"}
```

| Ситуація | Статус | `code` |
|---|---|---|
| Ресурс не знайдено | 404 | `NOT_FOUND` |
| Заборонений/повторний перехід статусу, скасування Delivered | 409 | `SHIPMENT_CONFLICT` |
| Некоректні вхідні дані (наприклад, відстань поза 1–5000) | 400 | `INVALID_REQUEST` |

## 7. Чому тести не видаляють дані одне за одним

На відміну від лаб. №4–5, тут немає прямого доступу до Repository з тестів (принципово —
усе має йти через REST), а API не надає `DELETE`-ендпоінтів. Тому незалежність тестів
забезпечується інакше: кожен тест створює **власного** клієнта, посилку й відправлення
з унікальним кодом (`UUID`), тому дані різних тестів ніколи не перетинаються й не
впливають одне на одного, навіть залишаючись у БД до кінця запуску контейнера.
Контейнер — одноразовий і свіжий при кожному запуску `mvn test` (новий Docker-контейнер,
порожня БД), тому повторюваність результату забезпечена так само, як і в лаб. №5.

## 8. Підготовка до захисту

**Сценарій (відповідає розділу 6 методички):**

1. `mvn test` — весь automated suite, 16/16.
2. Створення ресурсу: показати `createShipment_returns201WithCorrectFeeAndStatus` —
   201, `Location`, тариф 7000 коп. для 1000 г / 100 км.
3. 404 і 409: `getNonExistentShipment_returns404WithErrorContract` і
   `repeatedDispatch_returns409AndLeavesStateUnchanged`.
4. Незмінність після відхиленої операції: другий `GET` у тому самому тесті — показати,
   що статус лишився `Dispatched`, а не щось зламане чи відкочене.
5. Персональне правило: `cancelRefundPercentage_dependsOnPreviousStatus` — два набори
   даних в одному параметризованому тесті.
6. Передача даних між запитами: `fullWorkflow_customerParcelShipmentDispatchDeliver` —
   показати рядки з `.extract().jsonPath().getLong("id")`.
7. **Різниця між тестуванням Service напряму (лаб. №4) і через REST API (лаб. №6):**
   «У лаб. №4 я викликав `service.createShipment(request)` — прямий Java-виклик методу,
   результат — об'єкт `Shipment` у тій самій JVM. Тут я надсилаю `POST /shipments` —
   реальний HTTP-запит, проходить через серіалізацію JSON, маршрутизацію Spring MVC,
   `@RequestBody`-десеріалізацію, і повертається реальна HTTP-відповідь зі статус-кодом
   і JSON-тілом. Це перевіряє не лише бізнес-логіку, а й весь шар, що її обслуговує:
   контролери, маршрутизацію, серіалізацію, `ApiExceptionHandler`».

**Типові додаткові питання:**
- *Чому не викликали Repository напряму для перевірки стану після дії?* Усі перевірки
  стану зроблені через повторний `GET` — це теж HTTP, а не прямий доступ до БД; саме так
  і має тестуватись REST API: через публічний контракт, а не внутрішню реалізацію.
- *Звідки `ApiExceptionHandler` бере статус 409 саме для заборонених переходів?*
  `ShippingService.dispatch/deliver/cancel` при неправильному поточному статусі кидає
  `ShipmentRejectedException`, а `ApiExceptionHandler` має окремий `@ExceptionHandler` для
  цього типу, що повертає 409 з кодом `SHIPMENT_CONFLICT`.
- *Чому `SHIPPING_POLICY_URL` не налаштовано — хіба це не спрощення, яке ламає чесність
  тесту?* Ні — це задокументована, штатна поведінка самого SUT (вбудований дефолт), а не
  обхідний шлях. Лаб. №6 перевіряє REST-контракт, а не межу з зовнішньою залежністю —
  це вже предмет лаб. №5.
