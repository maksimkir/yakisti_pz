package ua.course.delivery;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.github.tomakehurst.wiremock.client.WireMock;
import com.github.tomakehurst.wiremock.verification.LoggedRequest;
import org.junit.jupiter.api.*;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.net.URI;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static com.github.tomakehurst.wiremock.client.WireMock.*;
import static org.junit.jupiter.api.Assertions.*;

/**
 * Лабораторна робота №5 — Isolated Integration Testing with Testcontainers (варіант 09).
 *
 * <p>На відміну від лабораторної №4 (локальна PostgreSQL, Mock/Stub для ShippingPolicy),
 * тут обидві зовнішні залежності — і БД, і зовнішній HTTP-сервіс — є реальними
 * containerized dependencies, що піднімаються автоматично:</p>
 * <pre>
 *   ShippingService
 *     |-- Repository (CustomerRepository/ParcelRepository/ShipmentRepository)
 *     |      -> REAL JDBC, PostgreSQL у Testcontainers-контейнері (динамічний порт)
 *     \-- HttpShippingPolicy
 *            -> РЕАЛЬНИЙ HTTP POST /shipping-policy до WireMock-контейнера
 *               (не Java/Mockito Mock — справжній HTTP-сервер у Docker)
 * </pre>
 *
 * <p>Жодна локально запущена PostgreSQL не потрібна: контейнер стартує автоматично
 * для цього тестового класу, схему БД застосовує сам Testcontainers через
 * {@code withInitScript(...)} (файл {@code src/test/resources/db/V1__create_tables.sql} —
 * копія {@code migrations/V1__create_tables.sql} лабораторної №4, покладена в classpath,
 * бо саме так {@code withInitScript} читає SQL-файл). Порт PostgreSQL і WireMock
 * призначаються Docker-рантаймом динамічно й читаються у {@code @BeforeEach} безпосередньо
 * з об'єктів контейнерів — ніде немає захардкодженого порту 5432 чи 8080.</p>
 */
@Testcontainers
class ShippingContainerizedIntegrationTest {

    /** PostgreSQL піднімається в контейнері; схему застосовує сам Testcontainers з init-скрипта. */
    @Container
    static final PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>(DockerImageName.parse("postgres:16-alpine"))
            .withDatabaseName("delivery_it")
            .withUsername("it_user")
            .withPassword("it_pass")
            .withInitScript("db/V1__create_tables.sql");

    /** WireMock піднімається як окрема containerized dependency — реальний HTTP-сервер, а не Java Mock. */
    @Container
    static final GenericContainer<?> wiremock = new GenericContainer<>(DockerImageName.parse("wiremock/wiremock:3.9.1"))
            .withExposedPorts(8080)
            .waitingFor(Wait.forHttp("/__admin/health").forStatusCode(200));

    private static final ObjectMapper JSON = new ObjectMapper();

    private Connection connection;
    private CustomerRepository customers;
    private ParcelRepository parcels;
    private ShipmentRepository shipments;
    private ShippingService service;

    private final List<Long> createdShipmentIds = new ArrayList<>();
    private final List<Long> createdCustomerIds = new ArrayList<>();
    private final List<Long> createdParcelIds = new ArrayList<>();

    @BeforeEach
    void setUp() throws SQLException {
        // --- Параметри підключення до PostgreSQL беремо з runtime-об'єкта контейнера,
        //     не з фіксованих значень: getJdbcUrl()/getUsername()/getPassword() повертають
        //     саме те, що Testcontainers реально призначив цьому контейнеру зараз.
        connection = DriverManager.getConnection(postgres.getJdbcUrl(), postgres.getUsername(), postgres.getPassword());
        customers = new CustomerRepository(connection);
        parcels = new ParcelRepository(connection);
        shipments = new ShipmentRepository(connection);

        // --- Аналогічно: host і mapped port WireMock теж читаємо з контейнера в рантаймі.
        WireMock.configureFor(wiremock.getHost(), wiremock.getMappedPort(8080));
        WireMock.reset(); // ізоляція (п. 3.11): очищення stub-mappings і request journal перед кожним тестом

        HttpShippingPolicy policy = new HttpShippingPolicy(
                URI.create("http://" + wiremock.getHost() + ":" + wiremock.getMappedPort(8080)),
                Duration.ofSeconds(3));
        service = new ShippingService(customers, parcels, shipments, policy); // нові Service/Repository на кожен тест
    }

    /** Ізоляція (п. 3.11): видаляємо все створене цим тестом, незалежно від результату тесту. */
    @AfterEach
    void tearDown() throws SQLException {
        for (long id : createdShipmentIds) shipments.delete(id);
        for (long id : createdCustomerIds) customers.delete(id);
        for (long id : createdParcelIds) parcels.delete(id);
        createdShipmentIds.clear();
        createdCustomerIds.clear();
        createdParcelIds.clear();
        connection.close();
    }

    // ------------------------------------------------------------------ helpers

    private static String uniqueSuffix() {
        return UUID.randomUUID().toString().substring(0, 12);
    }

    private Customer newCustomer(boolean regular) throws SQLException {
        Customer saved = customers.create(new Customer(0, "CUST-" + uniqueSuffix(), regular));
        createdCustomerIds.add(saved.id());
        return saved;
    }

    private Parcel newParcel(int weightGrams, long declaredValue, boolean fragile) throws SQLException {
        Parcel saved = parcels.create(new Parcel(0, "PARCEL-" + uniqueSuffix(), weightGrams, declaredValue, fragile));
        createdParcelIds.add(saved.id());
        return saved;
    }

    private ShipmentRequest request(long customerId, long parcelId, int distanceKm) {
        return new ShipmentRequest("REF-" + uniqueSuffix(), customerId, parcelId, distanceKm, false, false, false);
    }

    private void track(Shipment shipment) {
        createdShipmentIds.add(shipment.id());
    }

    private void stubPolicyResponse(int httpStatus, String jsonBody) {
        var response = aResponse().withStatus(httpStatus);
        if (jsonBody != null) {
            response = response.withHeader("Content-Type", "application/json").withBody(jsonBody);
        }
        stubFor(post(urlEqualTo("/shipping-policy")).willReturn(response));
    }

    // =========================================================== REPOSITORY-LEVEL (контейнеризована БД)

    @Test
    @DisplayName("Repository ↔ контейнеризована БД: збереження і повторне отримання клієнта")
    void customerRepository_createAndFindById_repositoryState() throws SQLException {
        Customer saved = newCustomer(true);

        Customer found = customers.findById(saved.id());

        assertNotNull(found, "Запис має реально існувати в PostgreSQL-контейнері після create()");
        assertEquals(saved.code(), found.code());
        assertTrue(found.regular());
    }

    // ============================================= 3.5 ПОЗИТИВНИЙ СЦЕНАРІЙ (WireMock дозволяє)

    @Test
    @DisplayName("Позитивний: WireMock дозволяє доставку — відправлення збережено, тариф і персональне правило коректні")
    void createShipment_wiremockAllows_registersShipmentAndAppliesPersonalRule_serviceState() throws SQLException, JsonProcessingException {
        stubPolicyResponse(200, "{\"allowed\":true}");
        Customer customer = newCustomer(true);
        Parcel parcel = newParcel(1000, 500_00, false);

        Shipment created = service.createShipment(request(customer.id(), parcel.id(), 100));
        track(created);

        // --- Persisted state (п. 3.9): не лише return value, а повторний запит через Repository
        Shipment persisted = shipments.findById(created.id());
        assertEquals(ShipmentStatus.Registered, persisted.status());
        assertEquals(7000L, persisted.baseFee(), "1000 г, 100 км -> 70 грн (приклад з README SUT)");
        assertEquals(7000L, persisted.total());

        // --- HTTP-взаємодія (п. 3.10): кількість, метод, endpoint, тіло запиту
        List<LoggedRequest> requests = findAll(postRequestedFor(urlEqualTo("/shipping-policy")));
        assertEquals(1, requests.size(), "Зовнішній HTTP-сервіс має бути викликаний рівно один раз");
        JsonNode body = JSON.readTree(requests.get(0).getBodyAsString());
        assertEquals(customer.id(), body.get("customerId").asLong());
        assertEquals(parcel.id(), body.get("parcelId").asLong());
        assertEquals(100, body.get("distanceKm").asInt());

        // --- Персональне бізнес-правило варіанта (повернення залежно від статусу):
        //     Dispatched -> 50% total. Переходи статусу локальні, HTTP для них не викликається.
        service.dispatch(created.id());
        Shipment cancelled = service.cancel(created.id());
        assertEquals(3500L, cancelled.refund(), "Скасування з Dispatched має повернути 50% total (7000/2)");
        assertEquals(3500L, shipments.findById(created.id()).refund(), "Фактичний стан БД має відображати нараховане повернення");

        // Зовнішній сервіс під час dispatch/cancel не викликається -> лишається той самий 1 запит
        assertEquals(1, findAll(postRequestedFor(urlEqualTo("/shipping-policy"))).size());
    }

    // ============================================= 3.6 ЗОВНІШНЯ БІЗНЕС-ВІДМОВА

    @Test
    @DisplayName("Зовнішня відмова: WireMock забороняє доставку — запис не створено, HTTP-запит виконано")
    void createShipment_wiremockDeniesBusiness_throwsAndDoesNotPersist_serviceState() throws SQLException {
        stubPolicyResponse(200, "{\"allowed\":false}");
        Customer customer = newCustomer(true);
        Parcel parcel = newParcel(1000, 500_00, false);

        assertThrows(ShipmentRejectedException.class,
                () -> service.createShipment(request(customer.id(), parcel.id(), 100)));

        List<Shipment> found = shipments.findShipments(customer.id(), ShipmentStatus.Registered);
        assertTrue(found.isEmpty(), "Зовнішня відмова не повинна залишати запис у БД");

        verify(exactly(1), postRequestedFor(urlEqualTo("/shipping-policy")));
    }

    // ============================================= 3.7 НЕДОСТУПНІСТЬ ЗОВНІШНЬОГО СЕРВІСУ

    @Test
    @DisplayName("Недоступність сервісу: WireMock повертає 503 — IllegalStateException, запис не створено, HTTP-запит виконано")
    void createShipment_externalServiceUnavailable_throwsAndDoesNotPersist() throws SQLException {
        stubPolicyResponse(503, null);
        Customer customer = newCustomer(true);
        Parcel parcel = newParcel(1000, 500_00, false);

        assertThrows(IllegalStateException.class,
                () -> service.createShipment(request(customer.id(), parcel.id(), 100)));

        assertTrue(shipments.findShipments(customer.id(), ShipmentStatus.Registered).isEmpty(),
                "БД має лишитись у коректному стані — запис не повинен з'явитись");

        verify(exactly(1), postRequestedFor(urlEqualTo("/shipping-policy")));
    }

    // ============================================= 3.8 ЛОКАЛЬНА ВІДМОВА (до звернення до WireMock)

    @Test
    @DisplayName("Локальна відмова: невалідна відстань відхиляється ДО звернення до WireMock — HTTP-запитів 0")
    void createShipment_localValidationRejects_noHttpRequestMade() throws SQLException {
        // Навмисно НЕ налаштовуємо жоден stub — якщо сервіс все ж звернеться до WireMock,
        // тест це одразу виявить через verify(0, ...).
        Customer customer = newCustomer(true);
        Parcel parcel = newParcel(1000, 500_00, false);

        assertThrows(IllegalArgumentException.class,
                () -> service.createShipment(request(customer.id(), parcel.id(), 5001))); // поза межею 1..5000

        assertTrue(shipments.findShipments(customer.id(), ShipmentStatus.Registered).isEmpty());
        verify(0, postRequestedFor(urlEqualTo("/shipping-policy")));

        // Контраст із зовнішньою відмовою (п. 3.8): local rejection -> HTTP request = 0,
        // тоді як у createShipment_wiremockDeniesBusiness_... external rejection -> HTTP request = 1.
    }
}
