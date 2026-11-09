# Запуск одного тесту на Windows (PowerShell).
# Використання (з папки lab7, SUT уже запущений, PostgreSQL у Docker-контейнері delivery-pg):
#   .\scripts\run.ps1 k6 baseline
#   .\scripts\run.ps1 jmeter load
# Шлях до JMeter: змінна $env:JMETER або типовий C:\tools\apache-jmeter-5.6.3\bin\jmeter.bat
param(
    [Parameter(Mandatory = $true)][ValidateSet('k6', 'jmeter')][string]$Tool,
    [Parameter(Mandatory = $true)][ValidateSet('baseline', 'load', 'spike')][string]$LoadProfile
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$JMeter = if ($env:JMETER) { $env:JMETER } else { 'C:\tools\apache-jmeter-5.6.3\bin\jmeter.bat' }
$Out = Join-Path $Root "results\$Tool-$LoadProfile"

# 0. Перевірка, що SUT відповідає і може писати в БД (пробний POST /customers)
try {
    $probe = Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://127.0.0.1:8080/customers' `
        -ContentType 'application/json' -Body ('{"code":"T-' + [guid]::NewGuid() + '","regular":false}') -TimeoutSec 10
    Write-Host "== SUT OK: POST /customers -> $($probe.StatusCode)"
} catch {
    Write-Host '== SUT повернув помилку на пробний POST /customers:' -ForegroundColor Red
    if ($_.Exception.Response) {
        $code = [int]$_.Exception.Response.StatusCode
        Write-Host "HTTP $code $($_.ErrorDetails.Message)" -ForegroundColor Red
    } else {
        Write-Host $_.Exception.Message -ForegroundColor Red
        Write-Host 'Схоже, SUT не запущений: mvn spring-boot:run у папці sut-b' -ForegroundColor Red
    }
    Write-Host 'Подивіться також на помилки (ERROR) у терміналі, де запущено SUT.' -ForegroundColor Red
    exit 1
}
# Далі запускаються зовнішні програми (k6, JMeter, docker), які пишуть у stderr:
# у Windows PowerShell 5.1 з 'Stop' це обриває скрипт, тому перемикаємо на 'Continue'.
$ErrorActionPreference = 'Continue'

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force $Out | Out-Null

# 1. Прогрів JVM (результати не зберігаються)
Write-Host '== Прогрів SUT 15 с...'
k6 run -q --vus 10 --duration 15s -e PROFILE=warmup "$Root\k6\delivery-flow.js" --no-thresholds | Out-Null

# 2. Чиста БД — однакові стартові умови
Write-Host '== Очищення БД'
docker exec delivery-pg psql -q -U delivery_student -d delivery_variant09_test -c "TRUNCATE shipments, parcels, customers RESTART IDENTITY;"

# 3. Тест
Write-Host "== Запуск: $Tool $LoadProfile"
if ($Tool -eq 'k6') {
    $env:K6_WEB_DASHBOARD = 'true'
    $env:K6_WEB_DASHBOARD_PERIOD = '2s'
    $env:K6_WEB_DASHBOARD_EXPORT = "$Out\k6-report.html"
    k6 run -e PROFILE=$LoadProfile --summary-export "$Out\summary.json" --out "csv=$Out\raw.csv.gz" "$Root\k6\delivery-flow.js" 2>&1 |
        Tee-Object -FilePath "$Out\console.txt"
    Remove-Item Env:K6_WEB_DASHBOARD, Env:K6_WEB_DASHBOARD_PERIOD, Env:K6_WEB_DASHBOARD_EXPORT
} else {
    & $JMeter -n -t "$Root\jmeter\delivery-flow.jmx" -q "$Root\jmeter\$LoadProfile.properties" -q "$Root\jmeter\report.properties" `
        -l "$Out\results.jtl" -j "$Out\jmeter.log" -e -o "$Out\html-report" 2>&1 | Tee-Object -FilePath "$Out\console.txt"
}

# 4. Контроль даних у БД після тесту
docker exec delivery-pg psql -At -U delivery_student -d delivery_variant09_test -c "SELECT status, count(*) FROM shipments GROUP BY status;" |
    Tee-Object -FilePath "$Out\db-after.txt"
Write-Host "== Готово: $Out"
