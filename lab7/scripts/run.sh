#!/usr/bin/env bash
# Використання: scripts/run.sh <k6|jmeter> <baseline|load|spike>
# Перед кожним запуском БД очищується (однакові початкові умови), паралельно знімається CPU/RSS процесу SUT.
set -euo pipefail
TOOL=$1; PROFILE=$2
ROOT=$(cd "$(dirname "$0")/.." && pwd)
K6=${K6:-/home/user/tools/k6-v1.3.0-linux-amd64/k6}
JMETER=${JMETER:-/home/user/tools/apache-jmeter-5.6.3/bin/jmeter}
BASE_URL=${BASE_URL:-http://127.0.0.1:8080}
OUT="$ROOT/results/$TOOL-$PROFILE"
rm -rf "$OUT"; mkdir -p "$OUT"

# 0. Перезапуск SUT і прогрів JVM (однаковий стартовий стан для кожного прогону)
SUT_DIR=${SUT_DIR:-"/home/user/university_testing/group 2/variant09/sut-b"}
pkill -f 'sut-b-delivery-variant09' || true; sleep 2
( cd "$SUT_DIR" && DB_PASSWORD=${DB_PASSWORD:-student} nohup java -jar target/sut-b-delivery-variant09-1.0-SNAPSHOT.jar > "$OUT/sut.log" 2>&1 & )
until curl -sf -o /dev/null "$BASE_URL/customers/0" -w '' || curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/customers/0" | grep -q 404; do sleep 1; done
"$K6" run -q --vus 10 --duration 15s -e PROFILE=warmup "$ROOT/k6/delivery-flow.js" --no-thresholds >/dev/null 2>&1 || true

# 1. Чиста БД
PGPASSWORD=${DB_PASSWORD:-student} psql -q -h localhost -U delivery_student -d delivery_variant09_test \
  -c "TRUNCATE shipments, parcels, customers RESTART IDENTITY;"

# 2. Моніторинг SUT (CPU % ядра, RSS) і CPU машини кожну секунду
SUT_PID=$(pgrep -f 'sut-b-delivery-variant09' | head -1)
python3 "$ROOT/scripts/monitor.py" "$SUT_PID" "$OUT/sut-resources.csv" &
MON=$!
trap 'kill $MON 2>/dev/null || true' EXIT

# 3. Запуск
if [ "$TOOL" = k6 ]; then
  K6_WEB_DASHBOARD=true K6_WEB_DASHBOARD_PORT=-1 K6_WEB_DASHBOARD_PERIOD=2s \
  K6_WEB_DASHBOARD_EXPORT="$OUT/k6-report.html" \
  "$K6" run -e PROFILE="$PROFILE" -e BASE_URL="$BASE_URL" \
    --summary-export "$OUT/summary.json" --out csv="$OUT/raw.csv.gz" \
    "$ROOT/k6/delivery-flow.js" 2>&1 | tee "$OUT/console.txt" || true
else
  "$JMETER" -n -t "$ROOT/jmeter/delivery-flow.jmx" -q "$ROOT/jmeter/$PROFILE.properties" -q "$ROOT/jmeter/report.properties" \
    -l "$OUT/results.jtl" -j "$OUT/jmeter.log" -e -o "$OUT/html-report" 2>&1 | grep -v JAVA_TOOL | tee "$OUT/console.txt"
fi

# 4. Кількість записів у БД після тесту (контроль: shipments == успішні сценарії)
PGPASSWORD=${DB_PASSWORD:-student} psql -At -h localhost -U delivery_student -d delivery_variant09_test \
  -c "SELECT status, count(*) FROM shipments GROUP BY status;" | tee "$OUT/db-after.txt"
