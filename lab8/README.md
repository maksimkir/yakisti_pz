# Лабораторна №8 — Regression Testing and Flaky Test Debugging
Кирилюк М.О., 343А, варіант 9 — SUT B `group 2/variant09` «Доставка посилок» (Java, JUnit 5, Testcontainers).

- `sut-b/` — копія SUT B з виправленим regression suite і smoke subset (git: коміт «Original» → коміт з виправленнями)
- `fix-flaky-tests.patch` — diff усіх змін
- `evidence/` — виводи запусків до і після виправлення
- `scripts/stability.ps1` — кілька послідовних запусків suite (Windows)
- `report/` — звіт і шпаргалка

## Запуск (з папки `sut-b`, потрібні Docker Desktop і Java 21)
```
mvn -Psmoke test                                                      # smoke subset (4 тести)
mvn -Pregression test                                                 # повний regression (10 тестів, включно зі smoke)
mvn -Pregression test "-Dtest=ShipmentRegressionIT#dispatchShipment"  # один тест окремо
..\scripts\stability.ps1 -Runs 5                                      # 5 запусків поспіль
```
Якщо Testcontainers пише `client version 1.32 is too old` (Docker Engine 29+), один раз створіть файл:
```
Set-Content "$env:USERPROFILE\.docker-java.properties" "api.version=1.44"
```
