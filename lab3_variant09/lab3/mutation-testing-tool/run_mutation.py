import re, subprocess, sys, os, json

SRC = "/mnt/user-data/outputs/lab2_variant09/src/main/java/EnrollmentService.java"
TEST = "/mnt/user-data/outputs/lab2_variant09/src/test/java/EnrollmentServiceTest.java"
CP = "/usr/share/java/junit-platform-console-standalone.jar:/usr/share/java/mockito-core.jar:/usr/share/java/byte-buddy.jar:/usr/share/java/byte-buddy-agent.jar:/usr/share/java/objenesis.jar"

original = open(SRC, encoding="utf-8").read()

# (id, mutator category, human description, old substring, new substring)
mutants = [
    ("M01", "Conditionals Boundary", "credits >= 30  ->  credits > 30 (рядок 35)",
     "if (credits >= 30) {", "if (credits > 30) {"),
    ("M02", "Conditionals Boundary", "credits >= 30  ->  credits == 30 (рядок 35)",
     "if (credits >= 30) {", "if (credits == 30) {"),
    ("M03", "Negate Conditionals", "!prerequisites.isSatisfied()  ->  prerequisites.isSatisfied() (рядок 38)",
     "if (!prerequisites.isSatisfied()) {", "if (prerequisites.isSatisfied()) {"),
    ("M04", "Conditionals Boundary", "seats < 0  ->  seats <= 0 (рядок 42)",
     "if (seats < 0) {", "if (seats <= 0) {"),
    ("M05", "Conditionals Boundary", "seats < 0  ->  seats > 0 (рядок 42, інвертована межа)",
     "if (seats < 0) {", "if (seats > 0) {"),
    ("M06", "Negate Conditionals", "seats == 0  ->  seats != 0 (рядок 45)",
     "if (seats == 0) {", "if (seats != 0) {"),
    ("M07", "Conditionals Boundary / Logical", "scholarship && early  ->  scholarship || early (рядок 49)",
     "if (request.scholarship() && request.early()) {", "if (request.scholarship() || request.early()) {"),
    ("M08", "Constant Replacement", "discount = 20  ->  discount = 21 (рядок 52)",
     "discount = 20;", "discount = 21;"),
    ("M09", "Constant Replacement", "discount = 10  ->  discount = 11 (рядок 54)",
     "discount = 10;", "discount = 11;"),
    ("M10", "Constant Replacement", "discount = 0  ->  discount = 5 (рядок 56, гілка else)",
     "discount = 0;", "discount = 5;"),
    ("M11", "Math Mutator", "currentCredits() + courseCredits()  ->  віднімання (рядок 34)",
     "int credits = request.currentCredits() + request.courseCredits();",
     "int credits = request.currentCredits() - request.courseCredits();"),
    ("M12", "Math Mutator", "courseCredits() * 50_000L  ->  додавання (рядок 58)",
     "long base = request.courseCredits() * 50_000L;",
     "long base = request.courseCredits() + 50_000L;"),
    ("M13", "Math Mutator", "base - base*discount/100  ->  base + base*discount/100 (рядок 59)",
     "base - base * discount / 100, seats - 1", "base + base * discount / 100, seats - 1"),
    ("M14", "Math Mutator", "seats - 1  ->  seats + 1 (рядок 59, remainingSeats)",
     "base - base * discount / 100, seats - 1", "base - base * discount / 100, seats + 1"),
    ("M15", "Void Method Call Removal", "видалено виклик enrollments.save(...) (рядок 60)",
     "enrollments.save(request, result);", "/* mutated: save() call removed */"),
    ("M16", "Constant Replacement", "base * 50_000L  ->  50_001L (рядок 58)",
     "request.courseCredits() * 50_000L;", "request.courseCredits() * 50_001L;"),
    ("M17", "Constant Replacement (rejected())", "rejected(): credits 0 -> 1 (рядок 65)",
     'return new Result(status, 0, 0, 0, 0);', 'return new Result(status, 1, 0, 0, 0);'),
    ("M18", "Constant Replacement (rejected())", "rejected(): discountPercent 0 -> 1 (рядок 65)",
     'return new Result(status, 0, 0, 0, 0);', 'return new Result(status, 0, 1, 0, 0);'),
    ("M19", "Constant Replacement (rejected())", "rejected(): total 0 -> 1 (рядок 65)",
     'return new Result(status, 0, 0, 0, 0);', 'return new Result(status, 0, 0, 1, 0);'),
    ("M20", "Constant Replacement (rejected())", "rejected(): remainingSeats 0 -> 1 (рядок 65)",
     'return new Result(status, 0, 0, 0, 0);', 'return new Result(status, 0, 0, 0, 1);'),
    ("M21", "Conditionals Boundary (checkRange)", "value < minimum  ->  value <= minimum (рядок 69)",
     "if (value < minimum || value > maximum) {", "if (value <= minimum || value > maximum) {"),
    ("M22", "Conditionals Boundary (checkRange)", "value > maximum  ->  value >= maximum (рядок 69)",
     "if (value < minimum || value > maximum) {", "if (value < minimum || value >= maximum) {"),
    ("M23", "Logical Connector (checkRange)", "||  ->  && (рядок 69)",
     "if (value < minimum || value > maximum) {", "if (value < minimum && value > maximum) {"),
]

results = []
workdir = "/tmp/mutants"
os.makedirs(workdir, exist_ok=True)

for mid, category, desc, old, new in mutants:
    assert old in original, f"pattern not found for {mid}: {old!r}"
    mutated_src = original.replace(old, new, 1)
    mdir = os.path.join(workdir, mid)
    os.makedirs(mdir, exist_ok=True)
    src_path = os.path.join(mdir, "EnrollmentService.java")
    open(src_path, "w", encoding="utf-8").write(mutated_src)
    classes_dir = os.path.join(mdir, "classes")
    os.makedirs(classes_dir, exist_ok=True)
    # compile mutant SUT
    r = subprocess.run(["javac", "-encoding", "UTF-8", "-d", classes_dir, src_path],
                        capture_output=True, text=True)
    if r.returncode != 0:
        results.append((mid, category, desc, "COMPILE ERROR"))
        continue
    testclasses_dir = os.path.join(mdir, "testclasses")
    os.makedirs(testclasses_dir, exist_ok=True)
    r = subprocess.run(["javac", "-encoding", "UTF-8", "-d", testclasses_dir,
                         "-cp", f"{CP}:{classes_dir}", TEST],
                        capture_output=True, text=True)
    if r.returncode != 0:
        results.append((mid, category, desc, "TEST COMPILE ERROR"))
        continue
    r = subprocess.run(
        ["java", "-cp", f"{classes_dir}:{testclasses_dir}:{CP}",
         "org.junit.platform.console.ConsoleLauncher", "execute",
         "--scan-classpath", testclasses_dir, "--disable-banner",
         "--details=summary", "--disable-ansi-colors"],
        capture_output=True, text=True)
    out = r.stdout
    m = re.search(r"tests successful\s*\]", out)
    failed = re.search(r"\[\s*(\d+) tests failed\s*\]", out)
    nfailed = int(failed.group(1)) if failed else -1
    status = "SURVIVED" if nfailed == 0 else ("KILLED" if nfailed > 0 else "UNKNOWN")
    results.append((mid, category, desc, status, nfailed))

print(f"{'ID':4} {'Статус':10} {'Впало тестів':13} Категорія / опис")
killed = 0
survived = 0
for row in results:
    if len(row) == 5:
        mid, category, desc, status, nfailed = row
        if status == "KILLED":
            killed += 1
        elif status == "SURVIVED":
            survived += 1
        print(f"{mid:4} {status:10} {nfailed:<13} {category}: {desc}")
    else:
        mid, category, desc, status = row
        print(f"{mid:4} {status:10} {'-':<13} {category}: {desc}")

total = len(results)
print(f"\nGenerated mutants: {total}")
print(f"Killed: {killed}")
print(f"Survived: {survived}")
print(f"Mutation Score: {killed/total*100:.1f}%")

json.dump(
    [{"id": r[0], "category": r[1], "desc": r[2], "status": r[3], "failed": (r[4] if len(r) == 5 else None)} for r in results],
    open("/tmp/mutants/results_initial.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
