package ua.course.delivery;

import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.mockito.ArgumentCaptor;

import java.sql.Connection;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * Integration Test Suite для SUT B (варіант 09 — Доставка посилок).
 *
 * <p><b>Integration boundary:</b></p>
 * <pre>
 *   ShippingService
 *     |-- CustomerRepository  --\
 *     |-- ParcelRepository     |-- REAL, реальне JDBC-з'єднання, реальна тестова БД PostgreSQL
 *     |-- ShipmentRepository  --/
 *     \-- ShippingPolicy        -- поза межею: зовнішній дозвіл на доставку.
 *                                   У виробничому коді може бути HTTP-викликом
 *                                   (HttpShippingPolicy), тому в цих тестах він
 *                                   замінюється Stub (лямбдою) або Mock (Mockito) —
 *                                   залежно від того, що перевіряє конкретний тест.
 * </pre>
 *
 * <p>Репозиторії (CustomerRepository, ParcelRepository, ShipmentRepository) НЕ підміняються
 * Test Double, бо саме їхня взаємодія з реальною БД (SQL, схема, маппінг) є предметом
 * перевірки цієї лабораторної роботи.</p>
 *
 * <p><b>Персональне бізнес-правило варіанта (повернення залежно від статусу):</b>
 * скасування Registered повертає 100% total, Dispatched — 50%; скасування Delivered
 * та повторне скасування заборонені.</p>
 *
 * <p><b>Незалежність і повторюваність:</b> кожен тест відкриває власне з'єднання,
 * створює власних клієнта й посилку з унікальним кодом (UUID) і видаляє все створене
 * в {@code @AfterEach} незалежно від результату тесту. Тести не залежать один від
 * одного і від порядку запуску.</p>
 *
 * <p><b>Контрольна вимога методички:</b> метод
 * {@link #cancel_fromDispatched_intentionallyWrongExpectation_mustStayFailing()}
 * навмисно залишено FAILED — його не потрібно і не можна виправляти перед захистом.</p>
 */
class ShippingIntegrationTest {

    private Connection connection;
    private CustomerRepository customers;
    private ParcelRepository parcels;
    private ShipmentRepository shipments;

    private final List<Long> createdShipmentIds = new ArrayList<>();
    private final List<Long> createdCustomerIds = new ArrayList<>();
    private final List<Long> createdParcelIds = new ArrayList<>();

    @BeforeEach
    void openConnection() throws SQLException {
        connection = Database.connect();
        customers = new CustomerRepository(connection);
        parcels = new ParcelRepository(connection);
        shipments = new ShipmentRepository(connection);
    }

    /** Повна незалежність тестів: видаляємо все створене в цьому тесті, у правильному
     *  порядку (shipments мають FK ON DELETE RESTRICT на customers/parcels). Виконується
     *  завжди, навіть якщо тест впав — тому стан БД лишається чистим і для НАВМИСНО
     *  провального тесту теж. */
    @AfterEach
    void cleanUpAndCloseConnection() throws SQLException {
        for (long id : createdShipmentIds) shipments.delete(id);
        for (long id : createdCustomerIds) customers.delete(id);
        for (long id : createdParcelIds) parcels.delete(id);
        createdShipmentIds.clear();
        createdCustomerIds.clear();
        createdParcelIds.clear();
        connection.close();
    }

    // ------------------------------------------------------------------ helpers

    /** Короткий унікальний суфікс (до 40 символів з префіксом укладається з запасом). */
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

    private ShippingService service(ShippingPolicy policy) {
        return new ShippingService(customers, parcels, shipments, policy);
    }

    private ShipmentRequest request(long customerId, long parcelId, int distanceKm) {
        return new ShipmentRequest("REF-" + uniqueSuffix(), customerId, parcelId, distanceKm, false, false, false);
    }

    private void track(Shipment shipment) {
        createdShipmentIds.add(shipment.id());
    }

    // =========================================================== REPOSITORY-LEVEL

    @Test
    @DisplayName("Repository: збереження і повторне отримання клієнта (CustomerRepository ↔ БД)")
    void customerRepository_createAndFindById_repositoryState() throws SQLException {
        Customer saved = newCustomer(true);

        Customer found = customers.findById(saved.id());

        assertNotNull(found, "Запис має реально існувати в БД після create()");
        assertEquals(saved.id(), found.id());
        assertEquals(saved.code(), found.code());
        assertTrue(found.regular());
    }

    @Test
    @DisplayName("Repository: збереження і повторне отримання посилки (ParcelRepository ↔ БД)")
    void parcelRepository_createAndFindById_repositoryState() throws SQLException {
        Parcel saved = newParcel(2500, 15_000_00, true);

        Parcel found = parcels.findById(saved.id());

        assertNotNull(found);
        assertEquals(saved.id(), found.id());
        assertEquals(2500, found.weightGrams());
        assertEquals(15_000_00L, found.declaredValue());
        assertTrue(found.fragile());
    }

    @Test
    @DisplayName("Repository: зміна статусу відправлення та видалення запису (ShipmentRepository ↔ БД)")
    void shipmentRepository_updateStatusThenDelete_removesRecordFromDatabase() throws SQLException {
        Customer customer = newCustomer(false);
        Parcel parcel = newParcel(1000, 0, false);
        long baseFee = new ShippingService(customers, parcels, shipments, (c, p, d) -> true)
                .calculateBaseFee(1000, 100); // 7000, узгоджено з прикладом у README

        Shipment created = shipments.create(new Shipment(0, "REF-" + uniqueSuffix(), customer.id(), parcel.id(),
                100, false, false, customer.regular(), false, parcel.fragile(), 1000, 0,
                baseFee, 0, baseFee, 0, ShipmentStatus.Registered));
        track(created);

        // Зміна стану: Registered -> Dispatched
        shipments.updateStatus(created.id(), ShipmentStatus.Registered, ShipmentStatus.Dispatched, 0);
        Shipment afterUpdate = shipments.findById(created.id());
        assertEquals(ShipmentStatus.Dispatched, afterUpdate.status(), "Статус у БД має оновитись на Dispatched");

        // Видалення запису
        shipments.delete(created.id());
        assertNull(shipments.findById(created.id()), "Після delete() запис не повинен знаходитись у БД");
        createdShipmentIds.remove(created.id()); // вже видалено вручну, прибираємо з переліку очищення
    }

    // ============================================= SERVICE -> REPOSITORY -> DATABASE

    @Test
    @DisplayName("Service (позитивний сценарій): дозволена доставка реєструється з коректним тарифом")
    void createShipment_policyAllows_registersShipmentWithCorrectFee_serviceState() throws SQLException {
        Customer customer = newCustomer(true);
        Parcel parcel = newParcel(1000, 500_00, false);
        ShippingService service = service((c, p, d) -> true); // Stub: дозвіл завжди "так"

        Shipment created = service.createShipment(request(customer.id(), parcel.id(), 100));
        track(created);

        assertEquals(ShipmentStatus.Registered, created.status());
        assertEquals(7000L, created.baseFee(), "1000 г, 100 км -> 70 грн (приклад з README)");
        assertEquals(7000L, created.total());
        assertEquals(0L, created.refund());
    }

    @Test
    @DisplayName("Service (негативний сценарій): заборонена доставка не створює запис")
    void createShipment_policyRejects_throwsAndDoesNotPersist_serviceState() throws SQLException {
        Customer customer = newCustomer(true);
        Parcel parcel = newParcel(1000, 500_00, false);
        ShippingService service = service((c, p, d) -> false); // Stub: дозвіл завжди "ні"

        assertThrows(ShipmentRejectedException.class,
                () -> service.createShipment(request(customer.id(), parcel.id(), 100)));

        List<Shipment> found = shipments.findShipments(customer.id(), ShipmentStatus.Registered);
        assertTrue(found.isEmpty(), "Жодного запису не повинно з'явитись у БД при відмові політики");
    }

    @Test
    @DisplayName("Service (граничний сценарій): відстань поза межею 1..5000 відхиляється ДО звернення до політики")
    void createShipment_distanceOutOfRange_rejectedBeforePolicyIsInvoked() throws SQLException {
        Customer customer = newCustomer(true);
        Parcel parcel = newParcel(1000, 0, false);
        ShippingPolicy policyMock = mock(ShippingPolicy.class);
        ShippingService service = service(policyMock);

        assertThrows(IllegalArgumentException.class,
                () -> service.createShipment(request(customer.id(), parcel.id(), 5001)));

        verify(policyMock, never()).isAllowed(any(), any(), anyInt()); // зовнішня залежність не повинна викликатись
        assertTrue(shipments.findShipments(customer.id(), ShipmentStatus.Registered).isEmpty(),
                "Стан БД не змінюється при відмові на етапі валідації");
    }

    @Test
    @DisplayName("Service (interaction-based): політику викликано рівно один раз з коректними клієнтом/посилкою/відстанню")
    void createShipment_invokesPolicyExactlyOnceWithCorrectArguments() throws SQLException {
        Customer customer = newCustomer(false);
        Parcel parcel = newParcel(1500, 1000, true);
        ShippingPolicy policyMock = mock(ShippingPolicy.class);
        when(policyMock.isAllowed(any(), any(), anyInt())).thenReturn(true);
        ShippingService service = service(policyMock);

        Shipment created = service.createShipment(request(customer.id(), parcel.id(), 250));
        track(created);

        ArgumentCaptor<Customer> customerCaptor = ArgumentCaptor.forClass(Customer.class);
        ArgumentCaptor<Parcel> parcelCaptor = ArgumentCaptor.forClass(Parcel.class);
        ArgumentCaptor<Integer> distanceCaptor = ArgumentCaptor.forClass(Integer.class);
        verify(policyMock, times(1)).isAllowed(customerCaptor.capture(), parcelCaptor.capture(), distanceCaptor.capture());

        assertEquals(customer.id(), customerCaptor.getValue().id());
        assertEquals(parcel.id(), parcelCaptor.getValue().id());
        assertEquals(250, distanceCaptor.getValue());
    }

    @ParameterizedTest(name = "статус={0} -> refund = {1}% від total")
    @CsvSource({
            "Registered, 100",
            "Dispatched, 50"
    })
    @DisplayName("Service (персональне правило): відсоток повернення залежить від статусу на момент скасування")
    void cancelRefundPercentage_dependsOnPreviousStatus_persistedState(String statusName, int expectedPercent) throws SQLException {
        Customer customer = newCustomer(true);
        Parcel parcel = newParcel(1000, 0, false);
        ShippingService service = service((c, p, d) -> true);

        Shipment created = service.createShipment(request(customer.id(), parcel.id(), 100));
        track(created);
        if (ShipmentStatus.valueOf(statusName) == ShipmentStatus.Dispatched) {
            service.dispatch(created.id());
        }

        Shipment cancelled = service.cancel(created.id());

        long expectedRefund = created.total() * expectedPercent / 100;
        assertEquals(expectedRefund, cancelled.refund());
        assertEquals(ShipmentStatus.Cancelled, cancelled.status());

        // Персистентність: повторне звернення до Repository (а не лише перевірка return value)
        Shipment persisted = shipments.findById(created.id());
        assertEquals(ShipmentStatus.Cancelled, persisted.status(), "Фактичний стан БД має відображати скасування");
        assertEquals(expectedRefund, persisted.refund(), "Фактичний refund у БД має відповідати бізнес-правилу");
    }

    @Test
    @DisplayName("Service (персональне правило, негативний): скасування Delivered заборонене, стан БД не змінюється")
    void cancel_fromDelivered_isForbidden_stateUnchanged() throws SQLException {
        Customer customer = newCustomer(true);
        Parcel parcel = newParcel(1000, 0, false);
        ShippingService service = service((c, p, d) -> true);

        Shipment created = service.createShipment(request(customer.id(), parcel.id(), 100));
        track(created);
        service.dispatch(created.id());
        service.deliver(created.id());

        assertThrows(ShipmentRejectedException.class, () -> service.cancel(created.id()));

        Shipment persisted = shipments.findById(created.id());
        assertEquals(ShipmentStatus.Delivered, persisted.status(), "Статус не повинен змінитись після забороненої спроби");
        assertEquals(0L, persisted.refund(), "refund не повинен змінитись після забороненої спроби");
    }

    @Test
    @DisplayName("Service (альтернативний сценарій): повний життєвий цикл Registered -> Dispatched -> Delivered")
    void dispatchThenDeliver_transitionsStatusAcrossFullLifecycle() throws SQLException {
        Customer customer = newCustomer(false);
        Parcel parcel = newParcel(2000, 0, false);
        ShippingService service = service((c, p, d) -> true);

        Shipment created = service.createShipment(request(customer.id(), parcel.id(), 300));
        track(created);

        Shipment dispatched = service.dispatch(created.id());
        assertEquals(ShipmentStatus.Dispatched, dispatched.status());
        assertEquals(ShipmentStatus.Dispatched, shipments.findById(created.id()).status());

        Shipment delivered = service.deliver(created.id());
        assertEquals(ShipmentStatus.Delivered, delivered.status());
        assertEquals(ShipmentStatus.Delivered, shipments.findById(created.id()).status());
    }

    // =========================== НАВМИСНО ПРОВАЛЬНИЙ ТЕСТ (контрольна вимога лаб. №4)

    /**
     * Методичка лабораторної №4 (розділ 5) вимагає залишити в фінальному Integration
     * Test Suite один навмисно невдалий тест (FAILED), незалежно від фактичної
     * поведінки SUT, і НЕ виправляти його перед захистом.
     *
     * Тут навмисно перевіряється завідомо неправильне очікування: що скасування
     * Dispatched повертає 100% total, хоча за персональним правилом варіанта
     * повертається 50%. Сам SUT при цьому працює правильно — "неправильний" саме
     * assert, а не код.
     */
    @Test
    @DisplayName("[НАВМИСНО FAILED, за вимогою лаб.№4 — не виправляти] Скасування Dispatched нібито повертає 100% total")
    void cancel_fromDispatched_intentionallyWrongExpectation_mustStayFailing() throws SQLException {
        Customer customer = newCustomer(true);
        Parcel parcel = newParcel(1000, 0, false);
        ShippingService service = service((c, p, d) -> true);

        Shipment created = service.createShipment(request(customer.id(), parcel.id(), 100));
        track(created);
        service.dispatch(created.id());

        Shipment cancelled = service.cancel(created.id());

        // НАВМИСНА ПОМИЛКА: за правилом варіанта тут має бути created.total() / 2.
        assertEquals(created.total(), cancelled.refund(),
                "НАВМИСНО НЕПРАВИЛЬНЕ очікування (контрольна вимога лаб.№4, розділ 5): " +
                        "справжнє правило повертає 50% при скасуванні зі статусу Dispatched, " +
                        "а не 100%. Тест залишено FAILED навмисно — не виправляти перед захистом.");
    }
}
