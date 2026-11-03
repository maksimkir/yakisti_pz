import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

/**
 * Unit-тести для EnrollmentService (варіант 09 — запис на навчальні курси).
 *
 * Unit (SUT)       : EnrollmentService.process(Request)
 * Залежності       : PrerequisitePolicy, CourseCapacity, EnrollmentRepository
 * Test Doubles     :
 *   - prerequisites (PrerequisitePolicy) -> STUB  (повертає задане true/false або кидає виняток)
 *   - capacity      (CourseCapacity)     -> STUB  (повертає задану кількість місць або кидає виняток)
 *   - repository    (EnrollmentRepository) -> MOCK/SPY (перевіряємо факт, кількість і аргументи save)
 *
 * Очікувані значення визначені зі СПЕЦИФІКАЦІЇ (README варіанта 09).
 * Тести, де реалізація розходиться зі специфікацією, мають суфікс _counterRequirement:
 * у них очікуване значення узгоджене з ФАКТИЧНОЮ поведінкою, а вимога зі специфікації
 * описана в коментарі.
 */
class EnrollmentServiceTest {

    private EnrollmentService.PrerequisitePolicy prerequisites;
    private EnrollmentService.CourseCapacity capacity;
    private EnrollmentService.EnrollmentRepository repository;
    private EnrollmentService service;

    @BeforeEach
    void setUp() {
        prerequisites = mock(EnrollmentService.PrerequisitePolicy.class);
        capacity = mock(EnrollmentService.CourseCapacity.class);
        repository = mock(EnrollmentService.EnrollmentRepository.class);
        service = new EnrollmentService(prerequisites, capacity, repository);
    }

    // ------------------------------------------------------------------ helpers

    private static EnrollmentService.Request request(int course, int current, boolean scholarship, boolean early) {
        return new EnrollmentService.Request(course, current, scholarship, early);
    }

    private void givenPrerequisitesSatisfied(boolean satisfied) {
        when(prerequisites.isSatisfied()).thenReturn(satisfied);
    }

    private void givenFreeSeats(int seats) {
        when(capacity.freeSeats()).thenReturn(seats);
    }

    /** Усі умови для зарахування виконані: передумови є, 5 вільних місць. */
    private void givenEnrollmentPossible() {
        givenPrerequisitesSatisfied(true);
        givenFreeSeats(5);
    }

    // =========================================================== STATE-BASED

    @Test
    @DisplayName("Успішне зарахування без пільг: нове навантаження, сума, місця (state-based)")
    void process_validRequestWithoutBenefits_returnsEnrolledWithLoadTotalAndSeats() {
        givenEnrollmentPossible();

        EnrollmentService.Result result = service.process(request(4, 10, false, false));

        assertEquals("Зараховано", result.status());
        assertEquals(14, result.credits());          // 10 + 4
        assertEquals(0, result.discountPercent());
        assertEquals(200_000L, result.total());      // 4 * 50 000
        assertEquals(4, result.remainingSeats());    // 5 - 1
    }

    /**
     * Параметризований тест: одна логіка розрахунку знижки перевіряється на різних наборах.
     * Комбінація «стипендіат + ранній запис» тут відсутня — вона у окремому
     * _counterRequirement-тесті (реалізація розходиться зі специфікацією).
     */
    @ParameterizedTest(name = "кредитів={0}, стипендія={1}, ранній={2} -> знижка {3}%, сума {4}")
    @CsvSource({
            "4,  false, false, 0,  200000",   // без підстав
            "4,  false, true,  10, 180000",   // лише ранній запис
            "4,  true,  false, 20, 160000",   // лише стипендіат
            "1,  true,  false, 20, 40000",    // мінімальний курс (межа 1)
            "11, false, true,  10, 495000",   // великий курс
            "11, true,  false, 20, 440000"
    })
    @DisplayName("Розрахунок знижки та суми залежно від пільг (параметризований)")
    void process_discountDependsOnBenefits_calculatesPercentAndTotal(
            int courseCredits, boolean scholarship, boolean early, int expectedDiscount, long expectedTotal) {
        givenEnrollmentPossible();

        EnrollmentService.Result result = service.process(request(courseCredits, 0, scholarship, early));

        assertEquals("Зараховано", result.status());
        assertEquals(expectedDiscount, result.discountPercent());
        assertEquals(expectedTotal, result.total());
    }

    @Test
    @DisplayName("Гранична умова: сумарне навантаження 29 (< 30) — зараховано")
    void process_totalLoadJustBelowLimit_isEnrolled() {
        givenEnrollmentPossible();

        EnrollmentService.Result result = service.process(request(11, 18, false, false));

        assertEquals("Зараховано", result.status());
        assertEquals(29, result.credits());
    }

    @Test
    @DisplayName("Гранична умова: останнє вільне місце — зараховано, вільних місць 0")
    void process_lastFreeSeat_isEnrolledAndNoSeatsRemain() {
        givenPrerequisitesSatisfied(true);
        givenFreeSeats(1);

        EnrollmentService.Result result = service.process(request(3, 0, false, false));

        assertEquals("Зараховано", result.status());
        assertEquals(0, result.remainingSeats());
    }

    // ------------------------------------------------------------ negative business

    /**
     * Параметризований негативний сценарій. Усі інші умови ТАКОЖ невиконані
     * (передумови false, місць 0) — тест одночасно доводить, що навантаження
     * перевіряється першим, а залежності при цьому не опитуються.
     */
    @ParameterizedTest(name = "поточне={0}, курс={1} -> сума {0}+{1} > 30")
    @CsvSource({
            "25, 6",    // 31
            "30, 1",    // 31, максимальне поточне навантаження
            "20, 11",   // 31, максимальний курс (у межах, що приймає реалізація)
            "21, 10",   // 31
            "29, 2"     // 31
    })
    @DisplayName("Перевищення навантаження -> відмова, залежності не викликаються (параметризований)")
    void process_loadExceeded_rejectedBeforeAnyDependencyIsCalled(int currentCredits, int courseCredits) {
        givenPrerequisitesSatisfied(false);
        givenFreeSeats(0);

        EnrollmentService.Result result = service.process(request(courseCredits, currentCredits, true, true));

        assertEquals("Перевищено навантаження", result.status());
        // Повний Result при відмові (лаб. №3, mutation testing): відмова не повинна повертати
        // "залишки" від розрахунку — усі інші поля мають бути нульовими.
        assertEquals(0, result.credits());
        assertEquals(0, result.discountPercent());
        assertEquals(0L, result.total());
        assertEquals(0, result.remainingSeats());
        verifyNoMoreInteractions(prerequisites, capacity, repository);
    }

    @Test
    @DisplayName("Не виконано передумови -> відмова; місця не перевіряються, зарахування не зберігається")
    void process_prerequisitesNotSatisfied_rejectedWithoutCheckingSeatsOrSaving() {
        givenPrerequisitesSatisfied(false);
        givenFreeSeats(0); // навіть якщо місць немає, причина має бути «передумови» (порядок перевірок)

        EnrollmentService.Result result = service.process(request(4, 10, true, true));

        assertEquals("Не виконано передумови", result.status());
        // Повний Result при відмові (лаб. №3, mutation testing).
        assertEquals(0, result.credits());
        assertEquals(0, result.discountPercent());
        assertEquals(0L, result.total());
        assertEquals(0, result.remainingSeats());
        verify(prerequisites, times(1)).isSatisfied();
        verify(capacity, never()).freeSeats();
        verify(repository, never()).save(any(), any());
    }

    @Test
    @DisplayName("Немає вільних місць -> відмова, зарахування не зберігається")
    void process_noFreeSeats_rejectedAndNothingSaved() {
        givenPrerequisitesSatisfied(true);
        givenFreeSeats(0);

        EnrollmentService.Result result = service.process(request(4, 10, false, false));

        assertEquals("Немає місць", result.status());
        // Повний Result при відмові (лаб. №3, mutation testing): без цих перевірок
        // виживають мутанти всередині helper-методу rejected() (M17-M20, див. звіт лаб. №3).
        assertEquals(0, result.credits());
        assertEquals(0, result.discountPercent());
        assertEquals(0L, result.total());
        assertEquals(0, result.remainingSeats());
        verify(prerequisites, times(1)).isSatisfied();
        verify(capacity, times(1)).freeSeats();
        verify(repository, never()).save(any(), any());
    }

    // -------------------------------------------------------------- invalid input

    @ParameterizedTest(name = "курс={0}, поточне={1} -> помилка валідації")
    @CsvSource({
            "0,  0",    // курс нижче мінімуму (1)
            "13, 0",    // курс вище максимуму (12)
            "-5, 10",   // від'ємний курс
            "5,  -1",   // від'ємне навантаження
            "5,  31"    // навантаження вище максимуму (30)
    })
    @DisplayName("Значення поза діапазоном -> IllegalArgumentException, залежності не використовуються (параметризований)")
    void process_valuesOutOfRange_throwsValidationErrorAndTouchesNothing(int courseCredits, int currentCredits) {
        givenEnrollmentPossible();

        assertThrows(IllegalArgumentException.class,
                () -> service.process(request(courseCredits, currentCredits, false, false)));

        verifyNoMoreInteractions(prerequisites, capacity, repository);
    }

    @Test
    @DisplayName("Заявку не задано (null) -> помилка валідації")
    void process_nullRequest_throwsValidationError() {
        assertThrows(IllegalArgumentException.class, () -> service.process(null));

        verifyNoMoreInteractions(prerequisites, capacity, repository);
    }

    // ---------------------------------------------------------------- exceptional

    @Test
    @DisplayName("Від'ємна кількість вільних місць -> помилка обслуговування, нічого не зберігається")
    void process_negativeFreeSeats_throwsServiceErrorAndDoesNotSave() {
        givenPrerequisitesSatisfied(true);
        givenFreeSeats(-1);

        assertThrows(IllegalStateException.class, () -> service.process(request(4, 10, false, false)));

        verify(repository, never()).save(any(), any());
    }

    @Test
    @DisplayName("Залежність передумов недоступна (виняток) -> помилка проходить нагору, далі нічого не виконується")
    void process_prerequisitesUnavailable_propagatesErrorAndStops() {
        IllegalStateException failure = new IllegalStateException("prerequisites unavailable");
        when(prerequisites.isSatisfied()).thenThrow(failure);

        IllegalStateException thrown = assertThrows(IllegalStateException.class,
                () -> service.process(request(4, 10, false, false)));

        assertSame(failure, thrown);
        verifyNoMoreInteractions(capacity, repository);
    }

    @Test
    @DisplayName("Залежність місць недоступна (виняток) -> помилка проходить нагору, зарахування не зберігається")
    void process_capacityUnavailable_propagatesErrorAndDoesNotSave() {
        givenPrerequisitesSatisfied(true);
        IllegalStateException failure = new IllegalStateException("capacity unavailable");
        when(capacity.freeSeats()).thenThrow(failure);

        IllegalStateException thrown = assertThrows(IllegalStateException.class,
                () -> service.process(request(4, 10, false, false)));

        assertSame(failure, thrown);
        verify(repository, never()).save(any(), any());
    }

    @Test
    @DisplayName("Репозиторій не зміг зафіксувати зарахування -> помилка обслуговування, успіх не повертається")
    void process_repositoryFails_propagatesErrorInsteadOfReturningSuccess() {
        givenEnrollmentPossible();
        IllegalStateException failure = new IllegalStateException("cannot persist");
        doThrow(failure).when(repository).save(any(), any());

        IllegalStateException thrown = assertThrows(IllegalStateException.class,
                () -> service.process(request(4, 10, false, false)));

        assertSame(failure, thrown);
        verify(repository, times(1)).save(any(), any());
        verifyNoMoreInteractions(repository);
    }

    // ------------------------------------------------------- INTERACTION-BASED

    @Test
    @DisplayName("Успіх: save викликається рівно один раз з тими самими Request і Result (перевірка аргументів)")
    void process_successfulEnrollment_savesRequestAndResultExactlyOnce() {
        givenPrerequisitesSatisfied(true);
        givenFreeSeats(3);
        EnrollmentService.Request request = request(6, 12, true, false);

        EnrollmentService.Result returned = service.process(request);

        ArgumentCaptor<EnrollmentService.Request> requestCaptor = ArgumentCaptor.forClass(EnrollmentService.Request.class);
        ArgumentCaptor<EnrollmentService.Result> resultCaptor = ArgumentCaptor.forClass(EnrollmentService.Result.class);
        verify(repository, times(1)).save(requestCaptor.capture(), resultCaptor.capture());

        assertSame(request, requestCaptor.getValue());          // передана саме вхідна заявка
        assertEquals(returned, resultCaptor.getValue());        // збережено те, що повернуто клієнту
        assertEquals("Зараховано", resultCaptor.getValue().status());
        assertEquals(18, resultCaptor.getValue().credits());    // 12 + 6
        assertEquals(20, resultCaptor.getValue().discountPercent());
        assertEquals(240_000L, resultCaptor.getValue().total()); // 6*50000 = 300000, -20%
        assertEquals(2, resultCaptor.getValue().remainingSeats());
    }

    @Test
    @DisplayName("Порядок викликів: передумови -> вільні місця -> збереження")
    void process_successfulEnrollment_callsDependenciesInBusinessOrder() {
        givenEnrollmentPossible();

        service.process(request(4, 10, false, false));

        InOrder order = inOrder(prerequisites, capacity, repository);
        order.verify(prerequisites).isSatisfied();
        order.verify(capacity).freeSeats();
        order.verify(repository).save(any(), any());
        order.verifyNoMoreInteractions();
    }

    // ================================================== _counterRequirement
    // Тести нижче виявляють дефекти реалізації. Очікуване значення = ФАКТИЧНА поведінка.

    /**
     * Вимога: обсяг нового курсу — від 1 до 12 кредитів (межі включні), тому 12 — валідне значення.
     * Факт: checkRange(courseCredits, 1, 11, ...) — верхня межа 11, значення 12 відхиляється
     * як помилка валідації.
     * Характер розбіжності: неправильна верхня межа діапазону (off-by-one).
     */
    @Test
    @DisplayName("[дефект] Курс 12 кредитів: за специфікацією валідний, реалізація кидає виняток")
    void process_courseCredits12UpperBound_counterRequirement() {
        givenEnrollmentPossible();

        assertThrows(IllegalArgumentException.class, () -> service.process(request(12, 0, false, false)));
        // За специфікацією очікувалось: status "Зараховано", credits 12, total 600000.
    }

    /**
     * Вимога: зарахування заборонене, лише якщо навантаження + курс ПЕРЕВИЩУЄ 30.
     * Тобто рівно 30 кредитів — дозволено.
     * Факт: умова `credits >= 30` — рівно 30 відхиляється з причиною «Перевищено навантаження».
     * Характер розбіжності: помилка в операторі порівняння на межі (>= замість >).
     */
    @Test
    @DisplayName("[дефект] Сумарне навантаження рівно 30: за специфікацією дозволено, реалізація відмовляє")
    void process_totalLoadExactly30_counterRequirement() {
        givenEnrollmentPossible();

        EnrollmentService.Result result = service.process(request(10, 20, false, false));

        assertEquals("Перевищено навантаження", result.status());
        verify(repository, never()).save(any(), any());
        // За специфікацією очікувалось: status "Зараховано", credits 30, total 500000.
    }

    /**
     * Вимога: для стипендіата за раннього запису знижка становить 30%.
     * Факт: застосовується 25%.
     * Характер розбіжності: неправильна константа у бізнес-правилі розрахунку знижки.
     */
    @Test
    @DisplayName("[дефект] Стипендіат + ранній запис: за специфікацією 30%, реалізація застосовує 25%")
    void process_scholarshipAndEarlyDiscount_counterRequirement() {
        givenEnrollmentPossible();

        EnrollmentService.Result result = service.process(request(10, 0, true, true));

        assertEquals("Зараховано", result.status());
        assertEquals(25, result.discountPercent());
        assertEquals(375_000L, result.total());
        // За специфікацією очікувалось: discountPercent 30, total 350000.
    }
}
