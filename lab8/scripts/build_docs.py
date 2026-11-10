import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = lambda f: open(f'{ROOT}/evidence/{f}', encoding='utf-8').read().rstrip()

def new_doc(font='Times New Roman', size=12):
    d = Document(); st = d.styles['Normal']; st.font.name = font; st.font.size = Pt(size)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), font)
    for s in d.sections: s.left_margin = Cm(2.5); s.right_margin = Cm(1.5); s.top_margin = s.bottom_margin = Cm(2)
    return d
class W:
    def __init__(s, d, color=(0, 0, 0)): s.d = d; s.c = color
    def H(s, t, l=1):
        h = s.d.add_heading(t, l)
        for r in h.runs: r.font.color.rgb = RGBColor(*s.c); r.font.name = s.d.styles['Normal'].font.name
    def P(s, t='', b=False, i=False, c=None, size=None):
        p = s.d.add_paragraph(); r = p.add_run(t); r.bold = b; r.italic = i
        if size: r.font.size = Pt(size)
        if c == 'c': p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if c == 'r': p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        return p
    def B(s, items):
        for x in items: s.d.add_paragraph(x, style='List Bullet')
    def N(s, items):
        for x in items: s.d.add_paragraph(x, style='List Number')
    def shade(s, p, fill):
        pPr = p._p.get_or_add_pPr(); sh = OxmlElement('w:shd'); sh.set(qn('w:val'), 'clear'); sh.set(qn('w:fill'), fill); pPr.append(sh)
    def CODE(s, t, size=8.5):
        p = s.d.add_paragraph(); r = p.add_run(t); r.font.name = 'Consolas'; r.font.size = Pt(size); s.shade(p, 'F2F2F2')
    def SAY(s, t):
        p = s.d.add_paragraph(); p.add_run('🗣 ' + t); s.shade(p, 'EAF1FB')
    def T(s, h, rows, size=9, style='Table Grid'):
        t = s.d.add_table(rows=1, cols=len(h)); t.style = style
        for i, x in enumerate(h):
            c = t.rows[0].cells[i]; c.text = ''; r = c.paragraphs[0].add_run(x); r.bold = True; r.font.size = Pt(size)
        for row in rows:
            cs = t.add_row().cells
            for i, x in enumerate(row):
                cs[i].text = ''; r = cs[i].paragraphs[0].add_run(str(x)); r.font.size = Pt(size)
        s.d.add_paragraph()

PROBLEMS = [
    ['1. Order dependency', 'dispatchShipment',
     '«Некоректний ідентифікатор» (IllegalArgumentException), коли тест виконується раніше за createShipment (seed 2, 5, 6) і завжди — при ізольованому запуску.',
     'Тест брав id зі static-поля shipmentId, яке заповнював інший тест (createShipment). Без нього shipmentId = 0.',
     'Прибрано static shipmentId; dispatchShipment сам створює власне відправлення в секції Arrange і працює з його id.'],
    ['2. Shared state / dirty test data', 'parcelWeight, parcelValue',
     'Той із двох тестів, що виконується другим, падає на INSERT INTO parcels (DuplicateKeyException: duplicate key value violates unique constraint "parcels_code_key"). Поодинці обидва проходять.',
     'Обидва тести створювали посилку з однаковим кодом "REGRESSION-PARCEL", а code має обмеження UNIQUE; БД спільна для всього класу.',
     'Кожен тест створює посилку з унікальним кодом "P-<UUID>" через допоміжний метод parcel(weight, value).'],
    ['3. Fixed wait / timing dependency', 'shipmentAfterPolicyCheck',
     'expected: <1> but was: <0>. Проходить лише коли зовнішня перевірка триває менше ~40 мс (policyDelayMs=0/10 — PASS; 40/60/200 — FAIL).',
     'Операція виконується асинхронно, а тест чекав фіксовані Thread.sleep(50) і перевіряв БД до того, як відправлення було збережене (гонка).',
     'Thread.sleep(50) замінено на очікування умови — завершення операції: operation.get(10, SECONDS) (з тайм-аутом); додано перевірку id.'],
    ['4. Ще одна причина: залежність від порядку рядків у БД', 'shipmentSelection',
     'У звичайних запусках проходить, але при зміні порядку створення даних (regression.reverseFixture=true) падає: expected [A, B] but was [B, A].',
     'SELECT без ORDER BY: SQL не гарантує порядок рядків, тест випадково покладався на фізичний порядок вставки.',
     'У запит додано ORDER BY reference — порядок задано явно.'],
]

# ======================= ЗВІТ =======================
d = new_doc(); w = W(d)
w.P('Міністерство освіти і науки України', c='c')
w.P('Чернівецький національний університет імені Юрія Федьковича', c='c')
w.P('Дисципліна «Тестування та верифікація програмного забезпечення»', c='c')
for _ in range(5): w.P()
w.P('ЗВІТ', b=True, c='c', size=16)
w.P('з лабораторної роботи №8', b=True, c='c', size=14)
w.P('«Regression Testing and Flaky Test Debugging»', c='c', size=14)
for _ in range(5): w.P()
w.P('Виконав: студент групи 343А\nКирилюк Максим Олександрович\nВаріант 9 (group 2 / variant09, Java)', c='r')
w.P('Перевірив: ______________________', c='r')
for _ in range(6): w.P()
w.P('Чернівці — 2026', c='c'); d.add_page_break()

w.H('1. Мета роботи')
w.P('Навчитися організовувати regression test suite, виділяти smoke subset, виявляти flaky tests, визначати причини '
    'нестабільної поведінки тестів та забезпечувати їх незалежність і повторюваність.')

w.H('2. Вихідні дані')
w.P('SUT B варіанта group 2 / variant09 «Доставка посилок» (Java 21, Spring Boot, JdbcTemplate, PostgreSQL) і готовий regression suite '
    'src/test/java/ua/course/delivery/ShipmentRegressionIT.java з навмисно закладеними проблемами стабільності.')
w.B(['10 тестів JUnit 5; PostgreSQL піднімається через Testcontainers (образ postgres:17.6-alpine), схема — Flyway-міграцією;',
     'одна БД-контейнер спільна для всього класу (static @Container), сервіси й репозиторії — static-поля;',
     'порядок методів випадковий: @TestMethodOrder(MethodOrderer.Random.class) — тому flaky-поведінка проявляється від запуску до запуску;',
     'тест-параметри, закладені в suite для експериментів: regression.policyDelayMs (затримка зовнішньої перевірки) і regression.reverseFixture (обернений порядок створення даних).'])
w.P('Особливість середовища. З Docker Engine 29 Testcontainers 1.20.4 не стартує: «client version 1.32 is too old. Minimum supported API version is 1.40». '
    'Це не проблема тестів, а сумісність клієнта Docker: вирішено файлом ~/.docker-java.properties з рядком api.version=1.44 (на Windows — %USERPROFILE%\\.docker-java.properties). Код проєкту для цього не змінювався.', i=True)

w.H('3. Smoke subset і повний regression suite')
w.P('Smoke subset — швидка перевірка критичного шляху життєвого циклу відправлення. Обрано 4 тести:')
w.T(['Тест', 'Що перевіряє', 'Чому в smoke'], [
    ['createShipment', 'відправлення створюється і зберігається в БД зі статусом Registered', 'основна операція системи'],
    ['dispatchShipment', 'перехід Registered → Dispatched', 'ключовий перехід статусу'],
    ['delivery', 'Registered → Dispatched → Delivered, стан зберігається', 'повний «щасливий шлях» доставки'],
    ['repeatedCancellation', 'скасування і заборона повторного скасування', 'бізнес-правило повернення коштів / заборонений перехід'],
])
w.P('Механізм — теги JUnit 5 (@Tag). Клас позначено @Tag("regression"), тому кожен тест класу належить до regression; '
    'чотири тести додатково мають @Tag("smoke"). Отже smoke — підмножина regression, і повний regression run включає smoke-тести. '
    'Окремі запуски налаштовано профілями Maven Surefire у pom.xml (фільтр <groups>):')
w.CODE('''<profile><id>smoke</id>       ... <groups>smoke</groups>       <rerunFailingTestsCount>0</rerunFailingTestsCount> ...
<profile><id>regression</id>  ... <groups>regression</groups>  <rerunFailingTestsCount>0</rerunFailingTestsCount> ...

mvn -Psmoke test         # 4 тести  (smoke subset)
mvn -Pregression test    # 10 тестів (повний regression, включно зі smoke)''')
w.P('rerunFailingTestsCount=0 явно вимикає автоматичні повтори: flaky-тест не повинен «проходити з другої спроби».')

w.H('4. Виявлення нестабільних тестів')
w.P('Застосовано три прийоми (до виправлень, на оригінальному suite):')
w.N(['Повторні запуски повного suite з різним порядком тестів: -Djunit.jupiter.execution.order.random.seed=1…6;',
     'ізольований запуск кожного тесту окремо: -Dtest=ShipmentRegressionIT#<метод>;',
     'змінені умови: різна затримка зовнішньої перевірки (regression.policyDelayMs) та обернений порядок створення даних (regression.reverseFixture).'])
w.P('Порядок виконання та результати 6 повних запусків (фрагмент; повний вивід — evidence/before-repeated-runs.txt):', b=True)
w.CODE('\n'.join(EV('before-repeated-runs.txt').splitlines()[:24]), size=8)
w.P('Висновок з повторних запусків: результат одних і тих самих тестів змінюється без змін у коді — dispatchShipment падає лише коли виконується раніше за createShipment, '
    'з пари parcelWeight/parcelValue падає та, що виконується другою, shipmentAfterPolicyCheck не проходить жодного разу. Решта 6 тестів стабільні.')
w.P('Ізольовані запуски та змінені умови (evidence/before-isolated-and-variations.txt):', b=True)
w.CODE(EV('before-isolated-and-variations.txt'), size=8)
w.P('Ізольовано parcelWeight і parcelValue проходять — отже вони заважають один одному (спільні дані). dispatchShipment ізольовано падає — він залежить від іншого тесту. '
    'shipmentAfterPolicyCheck залежить від часу: проходить лише тоді, коли зовнішня перевірка коротша за фіксоване очікування. '
    'shipmentSelection проходить у звичайних запусках, але падає при зміні порядку фікстур — прихована (латентна) нестабільність.')

w.H('5. Проблеми: симптом → причина → виправлення')
w.T(['Проблема', 'Тест', 'Симптом', 'Причина (root cause)', 'Виправлення'], PROBLEMS, size=8)
w.P('Ключові зміни коду (повний diff — fix-flaky-tests.patch):', b=True)
w.CODE('''// 1. Order dependency
-    static long shipmentId;                       // спільний стан між тестами
-        var saved = service.dispatch(shipmentId);
+        var created = service.createShipment(request(customer(false), parcel(), false));
+        var saved = service.dispatch(created.id());   // тест готує власні дані

// 2. Dirty data
-        parcels.create(new Parcel(0, "REGRESSION-PARCEL", 1000, 0, false));
+        parcel(1000, 0);   // -> new Parcel(0, "P-" + UUID.randomUUID(), ...)

// 3. Fixed wait
-            Thread.sleep(50);
+            var created = operation.get(10, TimeUnit.SECONDS);  // чекаємо на завершення операції

// 4. Row order
-        "SELECT reference FROM shipments WHERE customer_id=?"
+        "SELECT reference FROM shipments WHERE customer_id=? ORDER BY reference"''')

w.H('6. Незалежність тестів')
w.B(['Жоден тест не використовує стан, створений іншим: static-поле shipmentId видалено; static лишились тільки інфраструктурні об\'єкти без стану даних (контейнер БД, JdbcTemplate, репозиторії, сервіс).',
     'Кожен тест створює власні дані з унікальними ключами (UUID) — UNIQUE-конфлікти неможливі, БД можна не очищати між тестами.',
     'Випадковий порядок методів збережено свідомо — він продовжує ловити залежності від порядку, якщо вони з\'являться в майбутньому.',
     'Синхронізація з асинхронною операцією — через очікування умови (Future.get з тайм-аутом), а не через sleep.',
     'Повтори (retry) вимкнено — стабільність досягнуто усуненням причин, а не повторними спробами.'])

w.H('7. Підтвердження стабільності')
w.P('Після виправлень (evidence/after-stability.txt):', b=True)
w.CODE(EV('after-stability.txt'), size=7.5)
w.P('10 послідовних повних запусків з різним порядком — 10 × 10 = 100 проходжень тестів, 0 падінь; кожен тест проходить ізольовано; '
    'тести стійкі до зміни затримки (0, 200, 2000 мс) і порядку створення даних. Smoke-запуск: 4 тести, 0 падінь.')

w.H('8. Ключові поняття')
w.T(['Поняття', 'Пояснення на прикладі цієї роботи'], [
    ['Smoke vs regression', 'Smoke — 4 критичні тести для швидкої перевірки, що система «жива»; regression — усі 10 тестів, що перевіряють, чи зміни не зламали наявну функціональність. Smoke ⊂ regression.'],
    ['Failing vs flaky test', 'Failing стабільно падає через дефект у коді й відтворюється щоразу. Flaky за того самого коду то проходить, то падає — залежно від порядку, даних, часу (dispatchShipment, parcelWeight/parcelValue).'],
    ['Fixed wait vs condition-based wait', 'Fixed wait (Thread.sleep(50)) чекає фіксований час: на повільній машині замало, на швидкій — зайве. Condition-based wait чекає настання умови (operation.get) з верхньою межею тайм-ауту.'],
    ['Retry vs усунення причини', 'Retry (rerunFailingTestsCount) лише маскує flaky-тест: проблема лишається і може зачепити продакшн-код. Тут кожну причину знайдено й усунено, повтори вимкнено.'],
])

w.H('9. Висновки')
w.B(['Виділено smoke subset (4 тести) через JUnit 5 @Tag і налаштовано окремі запуски mvn -Psmoke test та mvn -Pregression test; повний regression включає smoke.',
     'Повторними запусками з різним seed, ізольованими запусками й зміною умов виявлено 4 причини нестабільності: order dependency, shared/dirty data, fixed wait (timing) і залежність від порядку рядків без ORDER BY.',
     'Для кожної проблеми визначено root cause і виправлено саме причину (без retry і без збільшення sleep).',
     'Після виправлень кожен тест незалежний і проходить ізольовано; 10 послідовних запусків у різному порядку та запуски зі зміненими умовами — без жодного падіння.'])

w.H('Додаток. Команди')
w.CODE('''cd lab8\\sut-b
mvn -Psmoke test                                                     # smoke subset
mvn -Pregression test                                                # повний regression
mvn -Pregression test "-Dtest=ShipmentRegressionIT#dispatchShipment" # один тест окремо
mvn -Pregression test "-Djunit.jupiter.execution.order.random.seed=5" # конкретний порядок
..\\scripts\\stability.ps1 -Runs 5                                     # 5 послідовних запусків''')
d.save(f'{ROOT}/report/Lab8_Kyryliuk_343A.docx')

# ======================= ШПАРГАЛКА =======================
d = new_doc('Calibri', 11); w = W(d, (0x1F, 0x3A, 0x68))
d.add_heading('Шпаргалка до захисту ЛР №8 — Regression Testing and Flaky Test Debugging', 0)
w.P('Кирилюк М.О., 343А, варіант 9 (group 2/variant09 «Доставка посилок», Java, JUnit 5 + Testcontainers).', i=True)

w.H('0. Вступ (30 секунд)')
w.SAY('У regression suite мого SUT 10 інтеграційних тестів, вони працюють з реальною PostgreSQL у Docker через Testcontainers і виконуються у випадковому порядку. '
      'Я виділив smoke subset із 4 тестів через теги JUnit, налаштував окремі запуски, повторними й ізольованими запусками знайшов 4 причини нестабільності, '
      'виправив кожну і підтвердив стабільність десятьма запусками поспіль.')

w.H('1. Підготовка перед захистом')
w.B(['Запустити Docker Desktop.', 'Термінал → папка lab8\\sut-b, Java 21 (як у ЛР7):'])
w.CODE('$env:JAVA_HOME = (Get-ChildItem "C:\\Program Files\\Eclipse Adoptium" -Directory -Filter "jdk-21*" | Select-Object -First 1).FullName\n'
       '$env:Path = "$env:JAVA_HOME\\bin;$env:Path"\ncd <шлях>\\lab8\\sut-b')
w.P('Якщо тести падають з «client version 1.32 is too old» — один раз виконати:', b=True)
w.CODE('Set-Content "$env:USERPROFILE\\.docker-java.properties" "api.version=1.44"')
w.SAY('Це не помилка тестів: стара версія клієнта Testcontainers не підтримує новий Docker Engine 29; файл задає новішу версію API.')

w.H('2. Пункти захисту')
w.P('① Окремий запуск smoke subset', b=True)
w.CODE('mvn -Psmoke test        # Tests run: 4')
w.SAY('Smoke — це createShipment, dispatchShipment, delivery і repeatedCancellation: створення, передача в доставку, доставка і скасування. '
      'Позначені @Tag("smoke"), профіль smoke у pom.xml фільтрує <groups>smoke</groups>.')
w.P('② Запуск повного regression suite', b=True)
w.CODE('mvn -Pregression test   # Tests run: 10 — включно з 4 smoke')
w.SAY('Клас позначено @Tag("regression"), тож усі 10 тестів — regression, а smoke-тести мають обидва теги. Тому smoke — підмножина regression.')
w.P('③ Як виявив flaky test', b=True)
w.SAY('Тести йдуть у випадковому порядку. Я запустив suite 6 разів з різним seed і побачив, що ті самі тести то проходять, то падають без змін у коді. '
      'Потім запускав кожен тест окремо і змінював умови — затримку і порядок даних.')
w.CODE('mvn -Pregression test "-Djunit.jupiter.execution.order.random.seed=2"\nmvn -Pregression test "-Dtest=ShipmentRegressionIT#dispatchShipment"')
w.P('Можна показати «до» в оригінальній папці репозиторію (group 2\\variant09\\sut-b) тією ж командою з seed=2: падають dispatchShipment, parcelWeight, shipmentAfterPolicyCheck.', i=True)
w.P('④ Симптом → root cause → виправлення', b=True)
for p in PROBLEMS:
    w.P(f'{p[0]} — {p[1]}', b=True)
    w.B([f'Симптом: {p[2]}', f'Причина: {p[3]}', f'Виправлення: {p[4]}'])
w.P('⑤ Незалежний запуск окремого тесту', b=True)
w.CODE('mvn -Pregression test "-Dtest=ShipmentRegressionIT#dispatchShipment"')
w.SAY('До виправлення dispatchShipment окремо падав, бо брав id з іншого тесту. Тепер він сам створює своє відправлення і проходить окремо.')
w.P('⑥ Кілька послідовних успішних запусків', b=True)
w.CODE('..\\scripts\\stability.ps1 -Runs 5    # 5 запусків з різним порядком, усі PASS')
w.SAY('Я робив 10 запусків з різними seed — 100 проходжень тестів без жодного падіння. Плюс кожен тест окремо і зміна умов.')

w.H('3. Різниці, які треба пояснити (⑦)')
w.P('Smoke testing vs regression testing', b=True)
w.SAY('Smoke — мінімальна швидка перевірка, що критичний функціонал взагалі працює (запускають першим, наприклад після збірки). '
      'Regression — повна перевірка, що нові зміни нічого не зламали в уже працюючому функціоналі. Smoke — підмножина regression.')
w.P('Failing test vs flaky test', b=True)
w.SAY('Failing стабільно падає щоразу — це дефект, його легко відтворити. Flaky при тому самому коді то проходить, то падає — '
      'через порядок, спільні дані, час, мережу. Приклад: dispatchShipment проходив, якщо випадково йшов після createShipment.')
w.P('Fixed wait vs condition-based wait', b=True)
w.SAY('Fixed wait — Thread.sleep(50): вгадуємо час. Якщо операція триває 200 мс — тест падає; якщо 1 мс — даремно чекаємо. '
      'Condition-based — чекаємо саме умову: я чекаю завершення операції через operation.get(10, SECONDS). 10 секунд — лише верхня межа, щоб тест не завис.')
w.P('Retry vs усунення причини', b=True)
w.SAY('Retry — перезапустити впалий тест, і він «пройде з другого разу». Це маскує проблему: тест лишається нестабільним, а причина може бути і в продакшн-коді. '
      'Я вимкнув повтори (rerunFailingTestsCount=0) і виправив кожну причину.')

w.H('4. Можливі питання')
def QA(q, a):
    p = d.add_paragraph(); r = p.add_run('❓ ' + q); r.bold = True; w.SAY(a)
QA('Чому shipmentAfterPolicyCheck — flaky, якщо в тебе він падав завжди?', 'Бо результат залежить від часу, а не від коду: з затримкою 0–10 мс він проходив, з 40+ мс — падав. На іншій машині чи при іншому навантаженні він би «мигав».')
QA('Чому не просто збільшити sleep до 500 мс?', 'Це той самий fixed wait: тест став би повільнішим і все одно міг впасти на повільній машині. Правильно — чекати на умову.')
QA('Як знайшов четверту причину?', 'Тест shipmentSelection порівнював результат SELECT з очікуваним порядком. У SQL без ORDER BY порядок не гарантований. Я змінив порядок створення даних (regression.reverseFixture=true) — тест упав. Виправив ORDER BY reference.')
QA('Чому не очищаєш БД між тестами (@BeforeEach TRUNCATE)?', 'Можна, але тоді тести залежать від спільної чистки. Я зробив дані унікальними (UUID) — тести не перетинаються навіть у спільній БД.')
QA('Навіщо залишив випадковий порядок?', 'Випадковий порядок — це «детектор» order dependency: якщо хтось знову додасть залежність між тестами, вона проявиться.')
QA('Що таке Testcontainers?', 'Бібліотека, яка перед тестами піднімає справжню PostgreSQL у Docker-контейнері і прибирає її після. Тести працюють з реальною БД, ізольовано від робочої.')
QA('Як працює seed?', 'MethodOrderer.Random перемішує тести за seed. Той самий seed — той самий порядок, тож падіння можна відтворити.')
d.save(f'{ROOT}/report/Shpargalka_Lab8_Kyryliuk.docx')
print('ok')
