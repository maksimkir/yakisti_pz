# Лабораторна робота №3 — Аналіз покриття коду та ефективності тестового набору
**Варіант 09 — Запис на навчальні курси** · SUT і Test Suite — з лабораторної №2 (без переписування) · Java 17 · JaCoCo · PIT (pitest)

## 1. Що зроблено

Test Suite з лабораторної №2 (31 тест-кейс, 18 методів) використано без змін структури.
До нього додано **4 нові assertion-рядки** у три вже наявні тести (розділ 5), знайдені за
допомогою mutation testing. Нових тестових методів не додавалось — Test Suite вже був
достатньо повним за Line/Branch Coverage.

## 2. Інструменти й запуск

| Завдання | Інструмент | Команда |
|---|---|---|
| Code Coverage | JaCoCo 0.8.15 (`jacoco-maven-plugin` 0.8.12) | `mvn test` |
| Mutation Testing | PIT (pitest) 1.17.4 + `pitest-junit5-plugin` 1.2.1 | `mvn org.pitest:pitest-maven:mutationCoverage` |

Обидва плагіни вже прописані в `pom.xml` (корінь проєкту, на рівень вище папки `lab3/`).
Звіти генеруються на комп'ютері студента (потрібен доступ до Maven Central — той самий,
що використовувався в лабораторній №2):

```
mvn test
# HTML-звіт JaCoCo: target/site/jacoco/index.html

mvn org.pitest:pitest-maven:mutationCoverage
# HTML-звіт PIT:    target/pit-reports/index.html
```

**Важливо для захисту:** методичка explicitly вимагає демонструвати метрики "шляхом
реального запуску відповідних інструментів", тому саме ці дві команди треба виконати
наживо на захисті. Нижче — результати, отримані під час підготовки (як приклад і резерв
на випадок проблем з інтернетом на парі), плюс усі проміжні артефакти в цій папці.

## 3. Code Coverage

### 3.1. Початковий результат

Test Suite з лабораторної №2 вже виконав **100% Line Coverage і 100% Branch Coverage**
для `EnrollmentService` (34/34 рядків, 22/22 гілок, 151/151 інструкцій) з першого запуску.

Файли: `coverage-html-initial/`, `coverage-initial.csv`, `screenshots/01-*`, `screenshots/02-*`.

Це не помилка вимірювання і не привід нічого не робити — методичка (розділ 8) прямо
попереджає: **високий Code Coverage не гарантує якісного Test Suite**. Тому основна
робота цієї лабораторної була зроблена не над Coverage (він уже був повний), а над
**Mutation Testing** (розділ 4), яке й виявило реальну прогалину.

### 3.2. Демонстрація методики "аналіз → прогалина → доповнення" (для захисту)

Щоб чесно продемонструвати повний цикл роботи з Coverage (а не просто сказати
"було й так 100%"), проведено контрольований експеримент: тимчасово вилучено тест
`process_negativeFreeSeats_throwsServiceErrorAndDoesNotSave` і повторно виміряно
покриття.

**Результат без цього тесту:** Branch Coverage падає з 100% до **94% (21/22)**,
Line Coverage — до **97% (33/34)**. Непокритою лишається гілка `throw new
IllegalStateException(...)` на рядку 43 (тіло `if (seats < 0)`).

Файли: `coverage-html-demo-gap/`, `screenshots/00a-*` (зведення класу),
`screenshots/00b-*` (підсвічений вихідний код: рядок 42 — жовтий/частково покритий,
рядок 43 — червоний/не виконано жодного разу).

**Пояснення для захисту (п. 5.2 методички):**
- **Непокрита гілка:** `if (seats < 0) { throw new IllegalStateException(...); }` —
  true-гілка (від'ємна кількість місць).
- **Сценарій і вхідні дані, потрібні для її виконання:** Stub `capacity.freeSeats()`
  повертає від'ємне число (наприклад, `-1`), передумови виконані.
- **Тест, який закриває прогалину:** `process_negativeFreeSeats_throwsServiceErrorAndDoesNotSave`
  (він і так є в Test Suite з лабораторної №2 — саме тому початкове реальне покриття
  вже було 100%; експеримент вище лише ізольовано показує, що станеться без нього).

Після повернення тесту назад — знову 100%/100% (це і є `coverage-html-initial/`).

## 4. Mutation Testing

### 4.1. Методика

Оскільки PIT і Maven Central недоступні в середовищі, де готувалась ця лабораторна,
мутаційне тестування спочатку виконано **вручну**: скрипт `mutation-testing-tool/run_mutation.py`
бере production-код `EnrollmentService.java`, застосовує до нього одну точкову зміну
(мутацію) за раз (за стандартними категоріями мутаторів PIT — Conditionals Boundary,
Negate Conditionals, Math Mutator, Constant Replacement, Void Method Call Removal,
Logical Connector), компілює отриманий "mutant" і запускає на ньому повний Test Suite.
Якщо хоча б один тест впав — mutant **killed**; якщо всі 31 пройшли — **survived**.

Це не заміна PIT, а рівноцінна перевірка тієї самої ідеї на тих самих типах мутацій,
яку легко відтворити повторно (`python3 run_mutation.py`) і яку варто продублювати
реальним запуском PIT на парі — `pom.xml` для цього вже налаштовано (розділ 2).

Згенеровано **23 mutants**, що покривають усі значущі умовні конструкції, арифметичні
операції, константи та виклик залежності в `EnrollmentService.process(...)`.

### 4.2. Початковий Mutation Report

| Метрика | Значення |
|---|---|
| Generated mutants | 23 |
| Killed | 19 |
| Survived | **4** |
| Mutation Score | **82.6%** |

Файл: `mutation-report.csv` (колонки `status_before` / `failed_tests_before`).

### 4.3. Survived Mutants — аналіз (п. 3.6)

Усі 4 survived mutants виявились в одному й тому самому місці — методі `rejected()`:

```java
private static Result rejected(String status) {
    return new Result(status, 0, 0, 0, 0);
}
```

| # | Яку зміну виконано | Чому тести не виявили | Якого assertion бракує |
|---|---|---|---|
| M17 | `credits`: 0 → 1 | Тести на відмову (`Перевищено навантаження`, `Не виконано передумови`, `Немає місць`) перевіряли лише `result.status()` | `assertEquals(0, result.credits())` |
| M18 | `discountPercent`: 0 → 1 | те саме | `assertEquals(0, result.discountPercent())` |
| M19 | `total`: 0 → 1 | те саме | `assertEquals(0L, result.total())` |
| M20 | `remainingSeats`: 0 → 1 | те саме | `assertEquals(0, result.remainingSeats())` |

**Висновок:** ці мутанти вижили не через прогалину в Coverage (рядок з `rejected()`
виконувався всіма трьома негативними тестами — Line/Branch Coverage були 100%), а
через **слабкі assertions**: тести перевіряли лише `status`, ігноруючи решту полів
`Result`. Це саме той випадок, коли **100% Code Coverage не означає якісний Test
Suite** (п. 6, обмеження методички; питання на захисті п. 4.2).

### 4.4. Покращення Test Suite

У три негативні тести (`process_loadExceeded_...`, `process_prerequisitesNotSatisfied_...`,
`process_noFreeSeats_...`) додано по 4 рядки:

```java
assertEquals(0, result.credits());
assertEquals(0, result.discountPercent());
assertEquals(0L, result.total());
assertEquals(0, result.remainingSeats());
```

Нових тестових методів не створювалося — виправлення точкове, за реальною слабкістю,
без "накручування" Mutation Score штучними тестами (заборонено п. 6.5 методички).

### 4.5. Фінальний Mutation Report

| Метрика | Значення |
|---|---|
| Generated mutants | 23 |
| Killed | **23** |
| Survived | **0** |
| Mutation Score | **100%** |

Файл: `mutation-report.csv` (колонки `status_after` / `failed_tests_after`) — M17–M20
тепер `KILLED`, кожен впадає на 7 тестах (усі три негативні тести одночасно, бо всі
вони викликають той самий метод `rejected()`).

Line/Branch Coverage після цього змінення лишились **100%/100%** (нових рядків коду
не додавалось, лише нові перевірки в наявних тестах) — див. `coverage-html-final/`,
`screenshots/03-*`, `screenshots/04-*`.

## 5. Типи мутацій, застосовані в наборі (для захисту, п. 5.9)

| Категорія (мутатор) | Приклади в наборі |
|---|---|
| **Conditionals Boundary** — зміна межі порівняння (`>=`→`>`, `<`→`<=` тощо) | M01, M02, M04, M05, M21, M22 |
| **Negate Conditionals** — заперечення умови (`==`→`!=`, видалення `!`) | M03, M06 |
| **Math Mutator** — зміна арифметичного оператора (`+`→`-`, `*`→`+`) | M11, M12, M13, M14 |
| **Constant Replacement** — зміна числової константи | M08, M09, M10, M16, M17–M20 |
| **Void Method Call Removal** — видалення виклику методу без результату | M15 (`enrollments.save(...)`) |
| **Logical Connector Replacement** — заміна `\|\|` на `&&` і навпаки | M07, M23 |

## 6. Порівняння показників

| Метрика | Початково | Фінально |
|---|---|---|
| Line Coverage | 100% (34/34) | 100% (34/34) |
| Branch Coverage | 100% (22/22) | 100% (22/22) |
| Mutation Score | 82.6% (19/23) | **100% (23/23)** |
| Кількість тестових методів | 18 | 18 (без змін) |
| Кількість assertion у 3 негативних тестах | по 1 (`status`) | по 5 (`status` + 4 поля `Result`) |

## 7. Файли в цій папці

```
lab3/
├── README-lab3.md                          <- цей файл
├── mutation-report.csv                     <- 23 mutants, статус до/після
├── coverage-initial.csv                    <- JaCoCo CSV, початковий запуск
├── coverage-final.csv                      <- JaCoCo CSV, фінальний запуск
├── coverage-html-initial/                  <- повний HTML-звіт JaCoCo (початково)
├── coverage-html-final/                    <- повний HTML-звіт JaCoCo (фінально)
├── coverage-html-demo-gap/                 <- HTML-звіт для демонстрації прогалини (розд. 3.2)
├── screenshots/                            <- скріншоти звітів (00a/00b — демо прогалини; 01-04 — до/після)
├── mutation-testing-tool/run_mutation.py   <- скрипт ручної симуляції mutation testing
└── EnrollmentServiceTest_BEFORE_lab3.java  <- знімок тестів ДО лаб. №3 (для порівняння з поточним)
```

Актуальний `EnrollmentServiceTest.java` (з посиленими assertion) знаходиться в
`../src/test/java/`, а не тут — лабораторна №3 не створює окремого SUT чи окремого
Test Suite, а допрацьовує існуючий.

## 8. Підготовка до захисту

**Сценарій демонстрації (п. 5 методички), 5–7 хвилин:**

| № | Що зробити | Що сказати |
|---|---|---|
| 1 | `mvn test` | Показати початковий (він же й фінальний) Coverage: 100%/100% |
| 2 | Відкрити `target/site/jacoco/index.html` → `EnrollmentService` | Пояснити 1 гілку через демо-експеримент (розд. 3.2): без тесту на від'ємні місця гілка `throw IllegalStateException` не виконується |
| 3 | Показати тест `process_negativeFreeSeats_...` | Це той тест, що покриває саму гілку |
| 4 | `mvn org.pitest:pitest-maven:mutationCoverage` | Дочекатися Mutation Score 100% |
| 5 | Відкрити `target/pit-reports/index.html` | Показати `rejected()` — раніше тут виживали 4 мутанти |
| 6 | Пояснити один тип мутації | Наприклад, Constant Replacement: змінили `0` на `1` в `rejected()`, тести цього не помічали |
| 7 | Показати доданий assertion | `assertEquals(0, result.credits())` та інші 3 рядки в трьох тестах |

**Типові питання (п. 5 та розділ 8):**

- *Чим відрізняються Line Coverage і Branch Coverage?* Line Coverage — частка рядків,
  які хоч раз виконались. Branch Coverage — частка гілок умовної логіки (обидві
  сторони `if`/`else`, кожен операнд `&&`/`||`), які виконались. Рядок з `if (seats < 0)`
  може мати 100% Line Coverage (сам `if` виконався), але 50% Branch Coverage, якщо
  умова завжди була false.
- *Чому високий Code Coverage не гарантує якісний Test Suite?* Coverage лише фіксує,
  що рядок/гілка виконались, а не те, що тест перевірив правильний результат. У нас
  рядок `rejected()` мав 100% Coverage, але 4 мутанти в ньому вижили, бо тести
  не перевіряли значення полів, які він повертає.
- *Що таке killed / survived mutant?* Killed — мутація змінила поведінку коду, і
  хоча б один тест це виявив (впав). Survived — усі тести пройшли, попри змінену
  поведінку; це сигнал про слабкість Test Suite (або еквівалентний мутант).
- *Що таке Mutation Score?* Частка killed mutants від загальної кількості
  релевантних mutants. У нас: 19/23 → 23/23 після доповнення тестів.
- *Чи можна було підняти Mutation Score штучно?* Ні — заборонено додавати тести без
  змістовних assertions. Усі 4 додані перевірки перевіряють реальну бізнес-вимогу
  (відмова не повинна повертати "залишки" попереднього розрахунку в полях Result).
- *Чи є еквівалентні мутанти в наборі?* Ні, у поточних 23 всі релевантні (кожен або
  killed, або (до виправлення) реально survived через слабкість тестів, а не через
  еквівалентність поведінки).
