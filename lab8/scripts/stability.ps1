# Перевірка стабільності regression suite кількома послідовними запусками з різним (випадковим) порядком тестів.
# Використання (з папки lab8\sut-b):  ..\scripts\stability.ps1            # 5 запусків
#                                    ..\scripts\stability.ps1 -Runs 10
param([int]$Runs = 5, [string]$Profile = 'regression')
$results = @()
for ($seed = 1; $seed -le $Runs; $seed++) {
    Write-Host "== Запуск $seed з $Runs (seed=$seed)..."
    $out = & mvn "-P$Profile" test "-Djunit.jupiter.execution.order.random.seed=$seed" 2>&1 | Out-String
    $ok = ($LASTEXITCODE -eq 0)
    $line = ($out -split "`n" | Select-String 'Tests run:' | Select-Object -Last 1)
    if (-not $line) { $line = if ($ok) { 'Tests run: OK (усі тести пройшли)' } else { 'див. target\surefire-reports' } }
    $results += [pscustomobject]@{ Run = $seed; Result = $(if ($ok) { 'PASS' } else { 'FAIL' }); Details = "$line".Trim() }
}
Write-Host ''
Write-Host 'Підсумок:'
foreach ($r in $results) { Write-Host ("  запуск {0}: {1}  {2}" -f $r.Run, $r.Result, $r.Details) }
$failed = ($results | Where-Object Result -eq 'FAIL').Count
if ($failed -eq 0) { Write-Host "Усі $Runs запусків успішні - suite стабільний." -ForegroundColor Green }
else { Write-Host "Невдалих запусків: $failed з $Runs" -ForegroundColor Red }
