# Лабораторна робота №2 — Модульне тестування та ізоляція залежностей
**Варіант 09 — Запис на навчальні курси** · Мова: **Java** · JUnit 5 + Mockito

## 1. Структура проєкту
```
lab2_variant09/
├── pom.xml
└── src/
    ├── main/java/EnrollmentService.java        ← SUT (без змін, з репозиторію курсу)
    └── test/java/EnrollmentServiceTest.java    ← unit-тести
```

## 2. Запуск
Потрібні **JDK 17 або новіший** і **Maven**. Перевірити: `mvn -v` — у рядку «Java version» має бути 17+.

```
mvn test
```

У VS Code (Extension Pack for Java) або IntelliJ IDEA тести також запускаються з панелі Testing чи кнопкою ▶ біля класу.
Очікуваний результат: **31 тест-кейс, 0 помилок** (18 тестових методів, 3 з них параметризовані — вони розгортаються в окремі кейси).

## 3. Аналіз тестованого компонента (п. 3.1)
- **Unit:** `EnrollmentService`, публічний метод `process(Request) → Result`.
- **Бізнес-логіка:** зарахування студента на курс. Порядок перевірок:
  валідація → навантаження (≤ 30) → передумови → вільні місця → знижка → `save`.
- **Знижка:** стипендіат + ранній запис / лише стипендіат (20%) / лише ранній запис (10%) / без пільг (0%). Базова ціна 50 000 коп. за кредит.

| Залежність | Інтерфейс | Test Double | Чому ізольована |
|---|---|---|---|
| Передумови курсу | `PrerequisitePolicy.isSatisfied()` | **Stub** | Потрібна лише задана відповідь true/false або виняток |
| Вільні місця | `CourseCapacity.freeSeats()` | **Stub** | Потрібна задана кількість місць або виняток |
| Сховище зарахувань | `EnrollmentRepository.save(req, res)` | **Mock/Spy** | Виклик `save` — спостережуваний ефект: перевіряємо факт, кількість і аргументи |

## 4. Покриття вимог завдання
| Вимога | Тести |
|---|---|
| Параметризований (4–6 наборів) | `process_discountDependsOnBenefits_...` (6), `process_loadExceeded_...` (5), `process_valuesOutOfRange_...` (5) |
| State-based (≥ 2) | `..._returnsEnrolledWithLoadTotalAndSeats`, `..._calculatesPercentAndTotal`, `process_totalLoadJustBelowLimit_isEnrolled`, `process_lastFreeSeat_...` |
| Interaction-based (≥ 2) | `never()` / `times()` у тестах відмов; `process_successfulEnrollment_callsDependenciesInBusinessOrder` (`InOrder`) |
| Перевірка аргументів | `process_successfulEnrollment_savesRequestAndResultExactlyOnce` (`ArgumentCaptor`) |
| Виняткові сценарії (≥ 2) | `..._negativeFreeSeats_...`, `..._prerequisitesUnavailable_...`, `..._capacityUnavailable_...`, `..._repositoryFails_...`, `..._nullRequest_...` |
| Позитивні / негативні | зарахування (без пільг, з пільгами, межі) / відмови: навантаження, передумови, місця |

Повний список методів:

| # | Метод | Що перевіряє |
|---|---|---|
| 1 | `process_validRequestWithoutBenefits_...` | Успіх без пільг: навантаження, сума, залишок місць |
| 2 | `process_discountDependsOnBenefits_...` | Знижка й сума для 6 наборів (параметризований) |
| 3 | `process_totalLoadJustBelowLimit_isEnrolled` | Межа: навантаження 29 — зараховано |
| 4 | `process_lastFreeSeat_...` | Межа: останнє місце — зараховано, залишок 0 |
| 5 | `process_loadExceeded_...` | Сума > 30 → відмова; залежності не викликаються (параметризований) |
| 6 | `process_prerequisitesNotSatisfied_...` | Відмова за передумовами; місця не опитуються; `save` немає |
| 7 | `process_noFreeSeats_...` | Відмова «Немає місць»; `save` немає |
| 8 | `process_valuesOutOfRange_...` | Значення поза діапазоном → `IllegalArgumentException` (параметризований) |
| 9 | `process_nullRequest_...` | `null` → `IllegalArgumentException` |
| 10 | `process_negativeFreeSeats_...` | Від'ємні місця → `IllegalStateException`, `save` немає |
| 11 | `process_prerequisitesUnavailable_...` | Виняток залежності проходить нагору; далі нічого не викликається |
| 12 | `process_capacityUnavailable_...` | Виняток залежності проходить нагору; `save` немає |
| 13 | `process_repositoryFails_...` | Збій `save` → помилка, а не «Зараховано» |
| 14 | `process_successfulEnrollment_savesRequestAndResultExactlyOnce` | `save` викликано один раз з тими самими аргументами |
| 15 | `process_successfulEnrollment_callsDependenciesInBusinessOrder` | Порядок: передумови → місця → збереження |
| 16–18 | `..._counterRequirement` (3 шт.) | Дефекти SUT (розділ 5) |

## 5. Знайдені дефекти (`_counterRequirement`)
За методичкою очікуване значення в таких тестах узгоджене з **фактичною** поведінкою, щоб suite був зеленим. Вимога зі специфікації описана в коментарі до тесту.

| # | Тест | Специфікація | Фактична поведінка | Характер |
|---|---|---|---|---|
| 1 | `process_courseCredits12UpperBound_counterRequirement` | Курс 1–**12** кредитів, межі включні | `checkRange(..., 1, 11, ...)`: 12 → `IllegalArgumentException` | Неправильна верхня межа (off-by-one) |
| 2 | `process_totalLoadExactly30_counterRequirement` | Заборона, лише якщо навантаження **перевищує** 30; рівно 30 дозволено | `credits >= 30`: рівно 30 → «Перевищено навантаження» | `>=` замість `>` на межі |
| 3 | `process_scholarshipAndEarlyDiscount_counterRequirement` | Стипендіат + ранній запис = **30%** | Застосовується **25%** (сума 375 000 замість 350 000) | Неправильна константа |

**Перевірка тестів:** на копії SUT із виправленими трьома місцями падають рівно ці три тести, решта 28 кейсів проходять. Тобто тести написані за специфікацією, а не підлаштовані під код.

## 6. Підготовка до захисту
**Що показати:** запуск `mvn test` (усе зелене) → структура класу → Stub/Mock у `setUp()` → параметризований тест → `ArgumentCaptor` → тест винятку → три `_counterRequirement`.

**Типові запитання:**
- *Чому передумови й місця — Stub, а репозиторій — Mock?* Від Stub нам потрібні лише відповіді. Виклик `save` — це наслідок бізнес-операції, тому його перевіряємо (`verify`).
- *Навіщо ізолювати залежності?* Тест перевіряє лише логіку `EnrollmentService`. Він швидкий, детермінований і не залежить від БД чи зовнішніх сервісів.
- *Навіщо параметризація?* Логіка одна, змінюються дані. Без дублювання, а новий набір додається одним рядком `@CsvSource`.
- *Чому в тесті відмови залежності «не викликаються»?* За специфікацією обмеження перевіряються в порядку навантаження → передумови → місця. Отже, при перевищенні навантаження передумови й місця опитуватися не повинні.
- *Що означає `_counterRequirement`?* Тест зафіксував розбіжність між вимогою й кодом; очікуване значення взято з фактичної поведінки, а вимога описана в коментарі.
- *Чи виправляли SUT?* Ні, за умовою лабораторної це заборонено.

## 7. Лабораторна робота №3

Продовження цього ж проєкту — Code Coverage (JaCoCo) та Mutation Testing (PIT) для
того самого SUT і Test Suite. Документація, звіти й скріншоти: **`lab3/README-lab3.md`**.
Коротко: Line/Branch Coverage — 100% з першого запуску; mutation testing виявив
4 survived mutants (слабкі assertions у негативних тестах), після доповнення —
Mutation Score 100%. Плагіни JaCoCo та PIT вже додані в `pom.xml`.

**Якщо викладач попросить змінити щось на місці:**
- новий набір даних → додати рядок у `@CsvSource` відповідного тесту;
- інша поведінка Stub → змінити `givenPrerequisitesSatisfied(...)` / `givenFreeSeats(...)`;
- нова перевірка взаємодії → `verify(mock, times(n)).method(...)`.
