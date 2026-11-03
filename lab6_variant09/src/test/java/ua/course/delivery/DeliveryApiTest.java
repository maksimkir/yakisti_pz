package ua.course.delivery;

import io.restassured.RestAssured;
import io.restassured.http.ContentType;
import io.restassured.response.Response;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.util.UUID;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

/**
 * Лабораторна робота №6 — Automated REST API Testing (варіант 09, SUT B: доставка посилок).
 *
 * <p>На відміну від лаб. №4-5 (тестування Service напряму, Java-виклики методів), тут
 * SUT тестується ТІЛЬКИ через HTTP: {@link io.restassured.RestAssured} надсилає реальні
 * запити до запущеного Spring Boot застосунку (піднятого на випадковому порту через
 * {@code @SpringBootTest(webEnvironment = RANDOM_PORT)}), а застосунок, своєю чергою,
 * працює з реальною PostgreSQL, яку автоматично підіймає Testcontainers (та сама схема,
 * що й у лаб. №5). Жодного прямого виклику {@code ShippingService} чи Repository з тестів
 * немає — лише HTTP-запити й перевірка HTTP-відповідей.</p>
 *
 * <p>Зовнішня HTTP-політика ({@code SHIPPING_POLICY_URL}) свідомо НЕ налаштована: за
 * документацією SUT (README, розділ «REST API»), без цієї змінної діє вбудована локальна
 * політика, яка завжди дозволяє операцію. Межу Service/Policy вже перевірено в лаб. №5;
 * тут предмет перевірки — контракт REST API (статус-коди, тіло відповіді, зміна стану
 * ресурсу), тому зовнішня залежність навмисно спрощена до "завжди дозволено".</p>
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
class DeliveryApiTest {

    @Container
    static final PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>(DockerImageName.parse("postgres:16-alpine"))
            .withDatabaseName("delivery_it")
            .withUsername("it_user")
            .withPassword("it_pass")
            .withInitScript("db/V1__create_tables.sql");

    /** Spring Boot підключається до тієї самої контейнеризованої БД, яку підняв Testcontainers. */
    @DynamicPropertySource
    static void datasourceProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @LocalServerPort
    int port;

    @BeforeEach
    void configureRestAssured() {
        RestAssured.baseURI = "http://127.0.0.1";
        RestAssured.port = port;
    }

    // ------------------------------------------------------------------ helpers

    private static String uniqueCode(String prefix) {
        return prefix + "-" + UUID.randomUUID().toString().substring(0, 12);
    }

    /** Створює клієнта через REST API і повертає його id — для використання в тілі інших запитів. */
    private long createCustomer(boolean regular) {
        return given()
                .contentType(ContentType.JSON)
                .body("{\"code\":\"" + uniqueCode("CUST") + "\",\"regular\":" + regular + "}")
                .when().post("/customers")
                .then().statusCode(201)
                .extract().jsonPath().getLong("id");
    }

    /** Створює посилку через REST API і повертає її id. */
    private long createParcel(int weightGrams, long declaredValue, boolean fragile) {
        return given()
                .contentType(ContentType.JSON)
                .body(String.format("{\"code\":\"%s\",\"weightGrams\":%d,\"declaredValue\":%d,\"fragile\":%b}",
                        uniqueCode("PARCEL"), weightGrams, declaredValue, fragile))
                .when().post("/parcels")
                .then().statusCode(201)
                .extract().jsonPath().getLong("id");
    }

    /** Створює відправлення через REST API і повертає повну відповідь (для подальших перевірок полів). */
    private Response createShipment(long customerId, long parcelId, int distanceKm) {
        return given()
                .contentType(ContentType.JSON)
                .body(String.format(
                        "{\"reference\":\"%s\",\"customerId\":%d,\"parcelId\":%d,\"distanceKm\":%d,\"urgent\":false,\"pickup\":false,\"couponValid\":false}",
                        uniqueCode("REF"), customerId, parcelId, distanceKm))
                .when().post("/shipments");
    }

    // =========================================================== 1-2. CREATE + GET (customers, parcels)

    @Test
    @DisplayName("POST /customers: 201, Location, id, поля відповідають запиту")
    void createCustomer_returns201WithLocationAndFields() {
        String code = uniqueCode("CUST");
        given()
                .contentType(ContentType.JSON)
                .body("{\"code\":\"" + code + "\",\"regular\":true}")
                .when().post("/customers")
                .then()
                .statusCode(201)
                .header("Location", containsString("/customers/"))
                .body("id", greaterThan(0))
                .body("code", equalTo(code))
                .body("regular", equalTo(true));
    }

    @Test
    @DisplayName("GET /customers/{id}: 200, дані відповідають створеному ресурсу")
    void getCustomer_returnsSavedData() {
        String code = uniqueCode("CUST");
        long id = given()
                .contentType(ContentType.JSON)
                .body("{\"code\":\"" + code + "\",\"regular\":false}")
                .when().post("/customers")
                .then().statusCode(201)
                .extract().jsonPath().getLong("id");

        given()
                .when().get("/customers/{id}", id)
                .then()
                .statusCode(200)
                .body("id", equalTo((int) id))
                .body("code", equalTo(code))
                .body("regular", equalTo(false));
    }

    @Test
    @DisplayName("POST /parcels: 201, Location, id, поля відповідають запиту")
    void createParcel_returns201WithLocationAndFields() {
        String code = uniqueCode("PARCEL");
        given()
                .contentType(ContentType.JSON)
                .body(String.format("{\"code\":\"%s\",\"weightGrams\":1500,\"declaredValue\":25000,\"fragile\":true}", code))
                .when().post("/parcels")
                .then()
                .statusCode(201)
                .header("Location", containsString("/parcels/"))
                .body("id", greaterThan(0))
                .body("code", equalTo(code))
                .body("weightGrams", equalTo(1500))
                .body("fragile", equalTo(true));
    }

    @Test
    @DisplayName("GET /parcels/{id}: 200, дані відповідають створеному ресурсу")
    void getParcel_returnsSavedData() {
        long id = createParcel(2000, 10_000, false);

        given()
                .when().get("/parcels/{id}", id)
                .then()
                .statusCode(200)
                .body("id", equalTo((int) id))
                .body("weightGrams", equalTo(2000))
                .body("fragile", equalTo(false));
    }

    // =========================================================== 1-2. CREATE + GET (shipments, основний ресурс)

    @Test
    @DisplayName("POST /shipments: 201, Location, тариф і статус Registered коректні")
    void createShipment_returns201WithCorrectFeeAndStatus() {
        long customerId = createCustomer(true);
        long parcelId = createParcel(1000, 50_000, false);

        createShipment(customerId, parcelId, 100)
                .then()
                .statusCode(201)
                .header("Location", containsString("/shipments/"))
                .body("id", greaterThan(0))
                .body("status", equalTo("Registered"))
                .body("baseFee", equalTo(7000))   // 1000 г, 100 км -> 70 грн (приклад з README)
                .body("total", equalTo(7000))
                .body("refund", equalTo(0));
    }

    @Test
    @DisplayName("GET /shipments/{id}: 200, дані відповідають створеному ресурсу")
    void getShipment_returnsSavedData() {
        long customerId = createCustomer(true);
        long parcelId = createParcel(1000, 0, false);
        long shipmentId = createShipment(customerId, parcelId, 100)
                .then().statusCode(201).extract().jsonPath().getLong("id");

        given()
                .when().get("/shipments/{id}", shipmentId)
                .then()
                .statusCode(200)
                .body("id", equalTo((int) shipmentId))
                .body("customerId", equalTo((int) customerId))
                .body("parcelId", equalTo((int) parcelId))
                .body("status", equalTo("Registered"));
    }

    // =========================================================== 3. GET неіснуючого ресурсу

    @Test
    @DisplayName("GET /shipments/{неіснуючий id}: 404, error contract {code, message}")
    void getNonExistentShipment_returns404WithErrorContract() {
        given()
                .when().get("/shipments/{id}", 999_999_999L)
                .then()
                .statusCode(404)
                .body("code", equalTo("NOT_FOUND"))
                .body("message", not(emptyOrNullString()));
    }

    // =========================================================== 4. Action endpoint

    @Test
    @DisplayName("POST /shipments/{id}/dispatch: 200, статус змінюється на Dispatched")
    void dispatchShipment_changesStatusTo200() {
        long customerId = createCustomer(true);
        long parcelId = createParcel(1000, 0, false);
        long shipmentId = createShipment(customerId, parcelId, 100)
                .then().statusCode(201).extract().jsonPath().getLong("id");

        given()
                .when().post("/shipments/{id}/dispatch", shipmentId)
                .then()
                .statusCode(200)
                .body("status", equalTo("Dispatched"));
    }

    // =========================================================== 5-6. Заборонена дія (409) + незмінність стану

    @Test
    @DisplayName("Повторний dispatch: 409 з error contract, а GET після цього підтверджує незмінність стану")
    void repeatedDispatch_returns409AndLeavesStateUnchanged() {
        long customerId = createCustomer(true);
        long parcelId = createParcel(1000, 0, false);
        long shipmentId = createShipment(customerId, parcelId, 100)
                .then().statusCode(201).extract().jsonPath().getLong("id");

        given().when().post("/shipments/{id}/dispatch", shipmentId).then().statusCode(200);

        // --- 5. Повторна (заборонена) дія: ще один dispatch того самого відправлення
        given()
                .when().post("/shipments/{id}/dispatch", shipmentId)
                .then()
                .statusCode(409)
                .body("code", equalTo("SHIPMENT_CONFLICT"))
                .body("message", not(emptyOrNullString()));

        // --- 6. Незмінність: наступний GET підтверджує, що ресурс не змінився після відхилення
        given()
                .when().get("/shipments/{id}", shipmentId)
                .then()
                .statusCode(200)
                .body("status", equalTo("Dispatched")); // не відкотився і не зламався
    }

    @Test
    @DisplayName("Доставка без попереднього dispatch (Registered -> Delivered): 409, стан не змінюється")
    void deliverWithoutDispatch_returns409AndDoesNotChangeState() {
        long customerId = createCustomer(true);
        long parcelId = createParcel(1000, 0, false);
        long shipmentId = createShipment(customerId, parcelId, 100)
                .then().statusCode(201).extract().jsonPath().getLong("id");

        given()
                .when().post("/shipments/{id}/deliver", shipmentId)
                .then()
                .statusCode(409)
                .body("code", equalTo("SHIPMENT_CONFLICT"));

        given()
                .when().get("/shipments/{id}", shipmentId)
                .then()
                .statusCode(200)
                .body("status", equalTo("Registered"));
    }

    // =========================================================== 7. Персональне бізнес-правило (параметризований)

    @ParameterizedTest(name = "скасування зі статусу {0} -> {1}% від total")
    @CsvSource({
            "Registered, 100",
            "Dispatched, 50"
    })
    @DisplayName("Персональне правило: відсоток повернення при скасуванні залежить від статусу")
    void cancelRefundPercentage_dependsOnPreviousStatus(String fromStatus, int expectedPercent) {
        long customerId = createCustomer(true);
        long parcelId = createParcel(1000, 0, false);
        Response created = createShipment(customerId, parcelId, 100);
        created.then().statusCode(201);
        long shipmentId = created.jsonPath().getLong("id");
        long total = created.jsonPath().getLong("total");

        if ("Dispatched".equals(fromStatus)) {
            given().when().post("/shipments/{id}/dispatch", shipmentId).then().statusCode(200);
        }

        long expectedRefund = total * expectedPercent / 100;

        given()
                .when().post("/shipments/{id}/cancel", shipmentId)
                .then()
                .statusCode(200)
                .body("status", equalTo("Cancelled"))
                .body("refund", equalTo((int) expectedRefund));

        // Персистентність: повторний GET підтверджує фактичний збережений стан, а не лише response дії
        given()
                .when().get("/shipments/{id}", shipmentId)
                .then()
                .statusCode(200)
                .body("status", equalTo("Cancelled"))
                .body("refund", equalTo((int) expectedRefund));
    }

    @Test
    @DisplayName("Персональне правило (негативний випадок): скасування Delivered заборонене")
    void cancelDelivered_isForbidden() {
        long customerId = createCustomer(true);
        long parcelId = createParcel(1000, 0, false);
        long shipmentId = createShipment(customerId, parcelId, 100)
                .then().statusCode(201).extract().jsonPath().getLong("id");

        given().when().post("/shipments/{id}/dispatch", shipmentId).then().statusCode(200);
        given().when().post("/shipments/{id}/deliver", shipmentId).then().statusCode(200);

        given()
                .when().post("/shipments/{id}/cancel", shipmentId)
                .then()
                .statusCode(409)
                .body("code", equalTo("SHIPMENT_CONFLICT"));

        given()
                .when().get("/shipments/{id}", shipmentId)
                .then()
                .statusCode(200)
                .body("status", equalTo("Delivered"))
                .body("refund", equalTo(0));
    }

    // =========================================================== 8. Workflow: POST -> GET -> action -> GET

    @Test
    @DisplayName("Workflow: клієнт -> посилка -> відправлення -> dispatch -> deliver, id передаються динамічно")
    void fullWorkflow_customerParcelShipmentDispatchDeliver() {
        // 1. POST /customers -> id з response
        long customerId = given()
                .contentType(ContentType.JSON)
                .body("{\"code\":\"" + uniqueCode("CUST") + "\",\"regular\":true}")
                .when().post("/customers")
                .then().statusCode(201)
                .extract().jsonPath().getLong("id");

        // 2. POST /parcels -> id з response
        long parcelId = given()
                .contentType(ContentType.JSON)
                .body(String.format("{\"code\":\"%s\",\"weightGrams\":1200,\"declaredValue\":0,\"fragile\":false}", uniqueCode("PARCEL")))
                .when().post("/parcels")
                .then().statusCode(201)
                .extract().jsonPath().getLong("id");

        // 3. POST /shipments, використовуючи ОБИДВА id з попередніх кроків
        long shipmentId = given()
                .contentType(ContentType.JSON)
                .body(String.format(
                        "{\"reference\":\"%s\",\"customerId\":%d,\"parcelId\":%d,\"distanceKm\":50,\"urgent\":false,\"pickup\":false,\"couponValid\":false}",
                        uniqueCode("REF"), customerId, parcelId))
                .when().post("/shipments")
                .then().statusCode(201)
                .body("status", equalTo("Registered"))
                .extract().jsonPath().getLong("id");

        // 4. GET — підтвердження створеного стану
        given().when().get("/shipments/{id}", shipmentId)
                .then().statusCode(200).body("status", equalTo("Registered"));

        // 5. action: dispatch
        given().when().post("/shipments/{id}/dispatch", shipmentId)
                .then().statusCode(200).body("status", equalTo("Dispatched"));

        // 6. GET — підтвердження нового стану
        given().when().get("/shipments/{id}", shipmentId)
                .then().statusCode(200).body("status", equalTo("Dispatched"));

        // 7. action: deliver
        given().when().post("/shipments/{id}/deliver", shipmentId)
                .then().statusCode(200).body("status", equalTo("Delivered"));

        // 8. GET — фінальне підтвердження
        given().when().get("/shipments/{id}", shipmentId)
                .then().statusCode(200).body("status", equalTo("Delivered"));
    }

    // =========================================================== Додатково: error contract для 400

    @Test
    @DisplayName("Некоректна відстань (поза 1..5000): 400, error contract")
    void createShipment_invalidDistance_returns400() {
        long customerId = createCustomer(true);
        long parcelId = createParcel(1000, 0, false);

        createShipment(customerId, parcelId, 5001)
                .then()
                .statusCode(400)
                .body("code", equalTo("INVALID_REQUEST"))
                .body("message", not(emptyOrNullString()));
    }
}
