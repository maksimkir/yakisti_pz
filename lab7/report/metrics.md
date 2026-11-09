### Зведені метрики (HTTP-запити)

| Запуск | Max VU | Запитів | Throughput, req/s | Сценаріїв/с | avg, ms | med, ms | p95, ms | p99, ms | max, ms | Error rate | Checks/assertions OK | CPU SUT avg/max, % ядра |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| k6 baseline | 1 | 348 | 5.8 | 1.0 | 6.93 | 6.63 | 10.51 | 14.33 | 15.58 | 0.00% | 100.00% | - / - |
| jmeter baseline | 1 | 336 | 5.7 | 0.9 | 7.08 | 6.0 | 9.0 | 10.65 | 140.0 | 0.00% | 100.00% | - / - |
| k6 load | 50 | 31902 | 263.7 | 43.9 | 5.96 | 5.76 | 10.16 | 13.07 | 59.92 | 0.00% | 100.00% | - / - |
| jmeter load | 50 | 31350 | 263.4 | 43.9 | 6.12 | 6.0 | 10.0 | 14.0 | 119.0 | 0.00% | 100.00% | - / - |
| k6 spike | 1000 | 68574 | 679.0 | 113.2 | 424.6 | 499.95 | 869.75 | 1085.65 | 2017.93 | 0.00% | 100.00% | - / - |
| jmeter spike | 1000 | 65602 | 662.6 | 107.4 | 401.01 | 502.0 | 808.0 | 1006.99 | 1841.0 | 0.00% | 100.00% | - / - |

### Thresholds

| Запуск | Критерій | Результат |
| --- | --- | --- |
| k6-baseline | avg < 50 ms | ✅ PASS |
| k6-baseline | p95 < 100 ms | ✅ PASS |
| k6-baseline | POST /shipments p95 < 150 ms | ✅ PASS |
| k6-baseline | error rate < 1% | ✅ PASS |
| k6-baseline | checks/assertions > 99% | ✅ PASS |
| jmeter-baseline | avg < 50 ms | ✅ PASS |
| jmeter-baseline | p95 < 100 ms | ✅ PASS |
| jmeter-baseline | POST /shipments p95 < 150 ms | ✅ PASS |
| jmeter-baseline | error rate < 1% | ✅ PASS |
| jmeter-baseline | checks/assertions > 99% | ✅ PASS |
| k6-load | avg < 100 ms | ✅ PASS |
| k6-load | p95 < 200 ms | ✅ PASS |
| k6-load | POST /shipments p95 < 250 ms | ✅ PASS |
| k6-load | error rate < 1% | ✅ PASS |
| k6-load | checks/assertions > 99% | ✅ PASS |
| jmeter-load | avg < 100 ms | ✅ PASS |
| jmeter-load | p95 < 200 ms | ✅ PASS |
| jmeter-load | POST /shipments p95 < 250 ms | ✅ PASS |
| jmeter-load | error rate < 1% | ✅ PASS |
| jmeter-load | checks/assertions > 99% | ✅ PASS |
| k6-spike | avg < 250 ms | ❌ FAIL |
| k6-spike | p95 < 500 ms | ❌ FAIL |
| k6-spike | POST /shipments p95 < 600 ms | ❌ FAIL |
| k6-spike | error rate < 1% | ✅ PASS |
| k6-spike | checks/assertions > 99% | ✅ PASS |
| jmeter-spike | avg < 250 ms | ❌ FAIL |
| jmeter-spike | p95 < 500 ms | ❌ FAIL |
| jmeter-spike | POST /shipments p95 < 600 ms | ❌ FAIL |
| jmeter-spike | error rate < 1% | ✅ PASS |
| jmeter-spike | checks/assertions > 99% | ✅ PASS |

### Spike по фазах

| Інструмент | Фаза | Throughput, req/s | avg, ms | p95, ms | p99, ms | max, ms | Error rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| k6 | до піку (0–30 с) | 288.4 | 8.34 | 23.18 | 46.42 | 151.88 | 0.00% |
| k6 | пік (30–70 с) | 1205.4 | 562.37 | 916.8 | 1140.55 | 2017.93 | 0.00% |
| k6 | відновлення (70–100 с) | 377.6 | 164.82 | 626.2 | 806.57 | 1453.01 | 0.00% |
| jmeter | до піку (0–30 с) | 275.8 | 11.85 | 42.3 | 146.26 | 371.0 | 0.00% |
| jmeter | пік (30–70 с) | 1228.8 | 532.13 | 837.0 | 1043.0 | 1841.0 | 0.00% |
| jmeter | відновлення (70–100 с) | 282.0 | 6.73 | 13.0 | 22.0 | 52.0 | 0.00% |

### По операціях (avg / p95, ms)

| Операція | k6 baseline | jmeter baseline | k6 load | jmeter load | k6 spike | jmeter spike |
| --- | --- | --- | --- | --- | --- | --- |
| GET /shipments/{id} | 3.99 / 6.44 | 3.59 / 4.0 | 2.61 / 4.01 | 2.7 / 4.0 | 391.69 / 800.52 | 366.03 / 715.0 |
| POST /customers | 6.79 / 8.72 | 10.89 / 8.0 | 5.34 / 7.76 | 5.85 / 8.0 | 398.3 / 819.42 | 374.83 / 723.0 |
| POST /parcels | 6.1 / 8.38 | 5.62 / 6.0 | 5.39 / 7.73 | 5.28 / 7.0 | 400.83 / 823.74 | 376.12 / 726.0 |
| POST /shipments | 9.62 / 14.69 | 8.61 / 10.0 | 8.74 / 12.73 | 8.88 / 13.0 | 485.5 / 989.05 | 464.14 / 932.5 |
| POST /shipments/{id}/cancel | 7.46 / 9.9 | 6.8 / 8.0 | 6.81 / 10.01 | 7.0 / 10.0 | 434.33 / 889.96 | 413.19 / 822.0 |
| POST /shipments/{id}/dispatch | 7.64 / 10.57 | 6.95 / 8.0 | 6.87 / 9.96 | 7.01 / 10.0 | 436.93 / 892.2 | 412.83 / 822.0 |
