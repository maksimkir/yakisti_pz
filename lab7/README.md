# Лабораторна №7 — Performance and Load Testing (JMeter + k6)
Кирилюк М.О., 343А, варіант 9 — SUT B `group 2/variant09` «Доставка посилок» (Java/Spring Boot/PostgreSQL).

Звіт: `report/Lab7_Kyryliuk_343A.docx`; зведені таблиці: `report/metrics.md`; графіки: `report/img/`.
HTML-звіти інструментів: `results/k6-*/k6-report.html`, `results/jmeter-*/html-report/index.html`.

Запуск (SUT B зібраний, PostgreSQL з міграцією, DB_PASSWORD задано):
```
scripts/run.sh k6 baseline      # або load | spike
scripts/run.sh jmeter baseline
python3 scripts/analyze.py      # метрики, thresholds, графіки
python3 scripts/build_report.py # docx-звіт
```
