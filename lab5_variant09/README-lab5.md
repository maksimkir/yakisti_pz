# Лабораторна робота №5 — Isolated Integration Testing with Testcontainers
**Варіант 09 — Доставка посилок (SUT B)** · Java 17 · Testcontainers 1.20.4 · WireMock 3.9.1 · PostgreSQL 16 (у контейнері)

SUT не змінювався — той самий `EnrollmentService`-рівня проєкт, що й у лаб. №4
(`ShippingService`, `CustomerRepository`/`ParcelRepository`/`ShipmentRepository`,
`HttpShippingPolicy`). Новий файл: `src/test/java/ua/course/delivery/ShippingContainerizedIntegrationTest.java`.
Тести лаб. №4 (`EnvironmentTest`, `ShippingIntegrationTest`), що залежали від локальної
PostgreSQL, у цій папці **видалені навмисно** — інакше `mvn test` намагався б
підключитись до локальної БД, порушуючи саму суть лаб. №5 («незалежність від локально
налаштованої PostgreSQL», розд. 6 методички). Вони лишаються в проєкті лаб. №4 без змін.

## ⚠️ Важливе застереження

Я **не можу запустити Docker у своєму середовищі** (немає прав і самого daemon), тому,
на відміну від лаб. №2–4, цей код я не прогнав і не бачив реального `BUILD SUCCESS`.
Я ретельно звірив кожен клас API (Testcontainers, WireMock-клієнт) із документацією
та реальним кодом вашого SUT, але перша перевірка «наживо» — на вашому комп'ютері.
Якщо щось не скомпілюється чи не запуститься з першого разу — це нормально, працюємо
разом так само, як із лаб. №2–4.

## 1. Що потрібно встановити

**Docker Desktop** (Windows): https://www.docker.com/products/docker-desktop/
- Під час встановлення лишіть усе за замовчуванням (WSL2 backend).
- Після встановлення **перезапустіть комп'ютер**, якщо попросить.
- Запустіть Docker Desktop і дочекайтесь, поки іконка в треї стане "Running" (зелена).
- Перевірте в PowerShell: `docker --version` і `docker ps` (друга команда має показати
  порожню таблицю без помилок — це ознака, що daemon працює).

Maven і JDK вже встановлені з лаб. №2–4 — нічого додатково ставити не треба.

## 2. Запуск

```
cd lab5_variant09
mvn test
```

**Жодної локальної PostgreSQL, жодних змінних середовища DB_HOST/DB_PASSWORD тощо
задавати не потрібно** — усе піднімається автоматично через Docker. Перший запуск
завантажить образи `postgres:16-alpine` і `wiremock/wiremock:3.9.1` з Docker Hub —
це займе час; наступні запуски швидші (образи кешуються локально).

Очікується: **5 тестів, 0 помилок**.

## 3. Аналіз SUT (п. 3.1)

| Що | Де |
|---|---|
| Repository з PostgreSQL | `CustomerRepository`, `ParcelRepository`, `ShipmentRepository` (ті самі, що в лаб. №4) |
| Migrations | `migrations/V1__create_tables.sql` (копія в `src/test/resources/db/` — для Testcontainers) |
| Зовнішня залежність | `ShippingPolicy` (інтерфейс) |
| HTTP-реалізація | `HttpShippingPolicy` — `POST {baseUrl}/shipping-policy` |
| Request body | `{"customerId": <long>, "parcelId": <long>, "distanceKm": <int>}` |
| Очікуваний response | `200 {"allowed": true|false}`; будь-який інший статус → `IllegalStateException` |
| Персональне правило | Повернення при скасуванні: `Registered` → 100% total, `Dispatched` → 50% total, інші статуси — заборонено |

## 4. Як працює ізольоване середовище

### 4.1. PostgreSQL через Testcontainers (п. 3.2–3.3)

```java
static final PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>(DockerImageName.parse("postgres:16-alpine"))
        .withDatabaseName("delivery_it")
        .withUsername("it_user")
        .withPassword("it_pass")
        .withInitScript("db/V1__create_tables.sql");
```

- Контейнер стартує автоматично (анотації `@Testcontainers` + `@Container`), без
  локально запущеної PostgreSQL.
- `withInitScript(...)` застосовує схему БД **автоматично під час старту контейнера** —
  ручного запуску SQL-клієнта перед тестами немає.
- Порт **не фіксований** 5432: Docker сам призначає вільний порт хоста, і підключення
  у `@BeforeEach` береться виключно з рантайм-об'єкта:
  ```java
  connection = DriverManager.getConnection(postgres.getJdbcUrl(), postgres.getUsername(), postgres.getPassword());
  ```
  `getJdbcUrl()` уже містить реальний призначений порт (наприклад
  `jdbc:postgresql://localhost:54321/delivery_it`) — ніде в коді немає `5432`.

### 4.2. WireMock як containerized dependency (п. 3.4)

```java
static final GenericContainer<?> wiremock = new GenericContainer<>(DockerImageName.parse("wiremock/wiremock:3.9.1"))
        .withExposedPorts(8080)
        .waitingFor(Wait.forHttp("/__admin/health").forStatusCode(200));
```

- Це **реальний HTTP-сервер** у Docker-контейнері (образ `wiremock/wiremock`), а не
  Java-об'єкт `Mockito.mock(...)`. `HttpShippingPolicy` надсилає до нього справжній
  TCP/HTTP-запит через `java.net.http.HttpClient`.
- Порт також динамічний: `wiremock.getMappedPort(8080)`.
- Клієнтська бібліотека `wiremock-standalone` (та сама, що й у Docker-образі) дає
  Java API для конфігурування відповідей (`stubFor`) і перевірки запитів (`verify`,
  `findAll`) через HTTP до `__admin`-API контейнера.

## 5. Сценарії (п. 3.5–3.8)

| Тест | WireMock-відповідь | Очікуваний результат |
|---|---|---|
| `createShipment_wiremockAllows_registersShipmentAndAppliesPersonalRule_serviceState` | `200 {"allowed":true}` | Успіх: запис створено, тариф і (далі) refund за персональним правилом коректні |
| `createShipment_wiremockDeniesBusiness_throwsAndDoesNotPersist_serviceState` | `200 {"allowed":false}` | `ShipmentRejectedException`, запису немає, **HTTP-запит виконано (1)** |
| `createShipment_externalServiceUnavailable_throwsAndDoesNotPersist` | `503` | `IllegalStateException`, запису немає, **HTTP-запит виконано (1)** |
| `createShipment_localValidationRejects_noHttpRequestMade` | stub не налаштовано | `IllegalArgumentException` (невалідна відстань), запису немає, **HTTP-запитів 0** |

Приклад конфігурації однієї WireMock-відповіді (п. 5.5 захисту):
```java
stubFor(post(urlEqualTo("/shipping-policy"))
        .willReturn(aResponse()
                .withStatus(200)
                .withHeader("Content-Type", "application/json")
                .withBody("{\"allowed\":true}")));
```

**Різниця local vs external rejection (п. 3.8, п. 5.9 захисту):**
- *Локальна* відмова (невалідна відстань) відбувається у валідації `ShippingService`
  ще до будь-якого звернення до `ShippingPolicy` → `verify(0, postRequestedFor(...))`.
- *Зовнішня* відмова — рішення приймає сам HTTP-сервіс (WireMock повернув
  `allowed:false`), тобто дзвінок уже відбувся → `verify(exactly(1), postRequestedFor(...))`.

## 6. Перевірка persisted state і HTTP-взаємодії (п. 3.9–3.10)

Жоден тест не обмежується лише значенням, яке повернув `Service`:

```java
Shipment persisted = shipments.findById(created.id());   // повторний запит через Repository
assertEquals(ShipmentStatus.Registered, persisted.status());
assertEquals(7000L, persisted.baseFee());
```

Перевірка самого HTTP-запиту (метод, endpoint, тіло):

```java
List<LoggedRequest> requests = findAll(postRequestedFor(urlEqualTo("/shipping-policy")));
assertEquals(1, requests.size());
JsonNode body = JSON.readTree(requests.get(0).getBodyAsString());
assertEquals(customer.id(), body.get("customerId").asLong());
assertEquals(parcel.id(), body.get("parcelId").asLong());
assertEquals(100, body.get("distanceKm").asInt());
```

## 7. Ізоляція й повторюваність (п. 3.11–3.12)

- Контейнери (`static` поля) стартують **один раз на весь клас** — це стандартна,
  рекомендована практика Testcontainers: піднімати Docker-контейнер на кожен тест
  було б надто повільно. Натомість **стан** очищається перед/після кожного тесту:
  - `WireMock.reset()` у `@BeforeEach` — очищення stub-mappings і request journal;
  - нові `Repository`/`Service`-об'єкти створюються в `@BeforeEach` для кожного тесту;
  - усе створене тестом видаляється в `@AfterEach` (`@AfterEach` виконується завжди,
    навіть якщо тест впав), так само, як це було реалізовано в лаб. №4.
- Клієнт/посилка створюються з унікальним кодом (`UUID`) у кожному тесті — тести не
  конфліктують між собою і не залежать від порядку виконання.
- **Повторюваність:** оскільки контейнери стартують наново при кожному запуску JVM
  (без `.withReuse(true)`), повторний `mvn test` гарантовано починається з чистого
  середовища — «повне видалення попереднього test environment» (п. 3.12) відбувається
  природно, без ручних дій.

## 8. Підготовка до захисту

**Сценарій демонстрації (відповідає п. 5 методички):**

1. `mvn test` — показати автоматичний запуск контейнерів у логах Maven/Testcontainers
   (рядки на кшталт `Creating container for image: postgres:16-alpine` і
   `wiremock/wiremock:3.9.1`).
2. Показати, звідки беруться URL/port/credentials: `postgres.getJdbcUrl()` у
   `@BeforeEach` — пояснити, що це рантайм-значення, а не хардкод.
3. Пояснити migrations: `withInitScript("db/V1__create_tables.sql")` застосовується
   автоматично під час старту контейнера, до першого тесту.
4. Показати один `stubFor(...)` (розділ 5 цього файлу).
5. **Різниця Mock (лаб. №4) vs WireMock (лаб. №5):** у лаб. №4 `ShippingPolicy`
   замінювалась Java-об'єктом (`Mockito.mock(ShippingPolicy.class)` або лямбдою) —
   виклик лишався в межах однієї JVM, без мережі. У лаб. №5 `HttpShippingPolicy`
   звертається по-справжньому через TCP/HTTP до окремого процесу (контейнера)
   WireMock — так само, як зверталася б до реального зовнішнього сервісу в production.
6. Показати перевірку persisted state (розділ 6).
7. Показати перевірку HTTP-запиту: `findAll(postRequestedFor(...))`.
8. Пояснити різницю `local rejection` (0 запитів) vs `external rejection` (1 запит) —
   розділ 5 цього файлу.
9. Пояснити ізоляцію (розділ 7).
10. Запустити `mvn test` ще раз і показати однаковий результат (5 тестів, 0 помилок).

**Типові питання:**
- *Чому контейнери `static`, а не створюються в кожному тесті?* Старт Docker-контейнера
  займає секунди; для десятка тестів це було б неприйнятно повільно. Ізоляція
  забезпечується не перезапуском контейнера, а очищенням його стану між тестами.
- *Чим це відрізняється від лаб. №4?* У лаб. №4 потрібна була заздалегідь вручну
  піднята локальна PostgreSQL з фіксованими username/password/портом. Тут усе
  розгортається й знищується автоматично, тому тест можна запустити на будь-якому
  комп'ютері з Docker, без попередньої ручної підготовки середовища.
- *Що, якби WireMock-контейнер взагалі не відповідав (а не повертав 503)?*
  `HttpShippingPolicy` отримала б `IOException` при спробі з'єднання й так само
  перетворила б її на `IllegalStateException` ("HTTP-перевірка недоступна") — той самий
  блок `catch (IOException)`, що й для `503`.
