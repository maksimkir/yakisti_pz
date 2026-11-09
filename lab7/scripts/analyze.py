"""Аналіз результатів k6 і JMeter: зведені метрики, перевірка thresholds, фази spike, графіки.
Вихід: results/summary.json, report/metrics.md, report/img/*.png"""
import json, os, gzip
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES, IMG = f'{ROOT}/results', f'{ROOT}/report/img'
PROFILES, TOOLS = ['baseline', 'load', 'spike'], ['k6', 'jmeter']
COL = {'k6': '#7D64FF', 'jmeter': '#D22128'}
# ті самі критерії, що в k6/delivery-flow.js
TH = {
    'baseline': dict(avg=50, p95=100, ship_p95=150, err=0.01, chk=0.99),
    'load':     dict(avg=100, p95=200, ship_p95=250, err=0.01, chk=0.99),
    'spike':    dict(avg=250, p95=500, ship_p95=600, err=0.01, chk=0.99),
}
SPIKE_PHASES = [('до піку (0–30 с)', 0, 30), ('пік (30–70 с)', 30, 70), ('відновлення (70–100 с)', 70, 101)]

def load_k6(p):
    df = pd.read_csv(f'{RES}/k6-{p}/raw.csv.gz', compression='gzip', low_memory=False,
                     usecols=['metric_name', 'timestamp', 'metric_value', 'name', 'status', 'check'])
    t0 = df.timestamp.min()
    df['t'] = df.timestamp - t0
    dur = df[df.metric_name == 'http_req_duration']
    fail = df[df.metric_name == 'http_req_failed']
    req = pd.DataFrame({'t': dur.t.values, 'ms': dur.metric_value.values, 'name': dur.name.values,
                        'http_ok': (fail.metric_value.values == 0)})
    chk = df[df.metric_name == 'checks']
    vus = df[df.metric_name == 'vus'][['t', 'metric_value']].rename(columns={'metric_value': 'vus'})
    vus = vus.groupby('t').vus.max()
    checks_rate = chk.metric_value.mean()
    flows = int(((chk['check'] == 'refund = 50% total') & (chk.metric_value == 1)).sum())
    return req, vus, checks_rate, flows

def load_jm(p):
    df = pd.read_csv(f'{RES}/jmeter-{p}/results.jtl', low_memory=False)
    t0 = df.timeStamp.min()
    code = pd.to_numeric(df.responseCode, errors='coerce')
    req = pd.DataFrame({'t': (df.timeStamp - t0) // 1000, 'ms': df.elapsed, 'name': df.label,
                        'http_ok': code.between(200, 399).values})
    vus = df.assign(t=(df.timeStamp - t0) // 1000).groupby('t').allThreads.max()
    vus.name = 'vus'
    checks_rate = df.success.astype(str).str.lower().eq('true').mean()  # HTTP code + JSON + JSR223 assertions
    flows = int(((df.label == 'POST /shipments/{id}/cancel') & df.success.astype(str).str.lower().eq('true')).sum())
    return req, vus, checks_rate, flows

def stats(req, span):
    ms = req.ms.values
    return dict(requests=int(len(req)), span_s=round(float(span), 1), rps=round(len(req) / span, 1),
                avg=round(float(ms.mean()), 2), med=round(float(np.percentile(ms, 50)), 2),
                p90=round(float(np.percentile(ms, 90)), 2), p95=round(float(np.percentile(ms, 95)), 2),
                p99=round(float(np.percentile(ms, 99)), 2), max=round(float(ms.max()), 2),
                err=round(float(1 - req.http_ok.mean()), 5))

data, summary = {}, {}
for p in PROFILES:
    for tool in TOOLS:
        if not os.path.exists(f'{RES}/{tool}-{p}'):
            continue
        req, vus, chk, flows = (load_k6 if tool == 'k6' else load_jm)(p)
        span = req.t.max() - req.t.min() + 1
        s = stats(req, span)
        s['checks'] = round(float(chk), 5); s['flows'] = flows; s['flows_per_s'] = round(flows / span, 1)
        s['max_vus'] = int(vus.max())
        s['by_endpoint'] = {n: dict(count=int(len(g)), avg=round(float(g.ms.mean()), 2),
                                    p95=round(float(np.percentile(g.ms, 95)), 2))
                            for n, g in req.groupby('name')}
        th = TH[p]
        ship = s['by_endpoint']['POST /shipments']['p95']
        s['thresholds'] = {
            f'avg < {th["avg"]} ms': s['avg'] < th['avg'],
            f'p95 < {th["p95"]} ms': s['p95'] < th['p95'],
            f'POST /shipments p95 < {th["ship_p95"]} ms': ship < th['ship_p95'],
            f'error rate < {th["err"]*100:.0f}%': s['err'] < th['err'],
            f'checks/assertions > {th["chk"]*100:.0f}%': s['checks'] > th['chk'],
        }
        if p == 'spike':
            s['phases'] = {}
            for label, a, b in SPIKE_PHASES:
                g = req[(req.t >= a) & (req.t < b)]
                s['phases'][label] = stats(g, b - a if b <= span else span - a)
        res_f = f'{RES}/{tool}-{p}/sut-resources.csv'
        res = pd.read_csv(res_f) if os.path.exists(res_f) else None
        if res is not None and len(res):
            res['t'] = res.ts - res.ts.min()
            s['sut_cpu_avg'] = round(float(res.sut_cpu_pct.mean()), 1)
            s['sut_cpu_max'] = round(float(res.sut_cpu_pct.max()), 1)
            s['host_cpu_max'] = round(float(res.host_cpu_pct.max()), 1)
        summary[f'{tool}-{p}'] = s
        data[(tool, p)] = (req, vus, res)

json.dump(summary, open(f'{RES}/summary.json', 'w'), indent=2, ensure_ascii=False)

# ---------------- графіки ----------------
plt.rcParams.update({'figure.dpi': 110, 'font.size': 9, 'axes.grid': True, 'grid.alpha': .3})
WIN = 2  # с, вікно агрегації (як K6_WEB_DASHBOARD_PERIOD і JMeter granularity)
for p in PROFILES:
    fig, ax = plt.subplots(5, 1, figsize=(10, 12), sharex=True)
    for tool in TOOLS:
        if (tool, p) not in data: continue
        req, vus, res = data[(tool, p)]
        req = req.assign(w=(req.t // WIN) * WIN)
        g = req.groupby('w')
        ax[0].plot(vus.index, vus.values, color=COL[tool], label=tool)
        ax[1].plot(g.size().index, g.size().values / WIN, color=COL[tool], label=tool)
        ax[2].plot(g.ms.mean().index, g.ms.mean().values, color=COL[tool], label=f'{tool} avg')
        ax[2].plot(g.ms.quantile(.95).index, g.ms.quantile(.95).values, color=COL[tool], ls='--', label=f'{tool} p95')
        ax[3].plot(g.http_ok.mean().index, (1 - g.http_ok.mean().values) * 100, color=COL[tool], label=tool)
        if res is not None:
            ax[4].plot(res.t, res.sut_cpu_pct, color=COL[tool], label=f'{tool}: SUT (JVM)')
            ax[4].plot(res.t, res.host_cpu_pct * os.cpu_count(), color=COL[tool], ls=':', label=f'{tool}: вся машина')
    ax[2].axhline(TH[p]['p95'], color='gray', ls='-.', lw=1, label=f'threshold p95 {TH[p]["p95"]} ms')
    ax[0].set_ylabel('Активні VU / threads'); ax[1].set_ylabel('Throughput, req/s')
    ax[2].set_ylabel('Response time, ms'); ax[3].set_ylabel('Error rate, %')
    ax[4].set_ylabel('CPU, % ядра'); ax[4].set_xlabel('Час від початку тесту, с')
    if p == 'spike':
        for a in ax: a.axvspan(30, 70, color='orange', alpha=.08)
    for a in ax: a.legend(loc='upper right', fontsize=7)
    fig.suptitle(f'{p.upper()}: k6 vs JMeter (вікно {WIN} с)', fontsize=12)
    fig.tight_layout(); fig.savefig(f'{IMG}/timeline-{p}.png'); plt.close(fig)

# порівняльні стовпчики
def bars(metric, ylabel, fname, log=False):
    fig, ax = plt.subplots(figsize=(7, 3.6))
    x = np.arange(len(PROFILES)); w = .38
    for i, tool in enumerate(TOOLS):
        vals = [summary.get(f'{tool}-{p}', {}).get(metric, 0) for p in PROFILES]
        b = ax.bar(x + (i - .5) * w, vals, w, color=COL[tool], label=tool)
        ax.bar_label(b, fmt='%.1f', fontsize=8)
    ax.set_xticks(x, PROFILES); ax.set_ylabel(ylabel); ax.legend()
    if log: ax.set_yscale('log')
    fig.tight_layout(); fig.savefig(f'{IMG}/{fname}.png'); plt.close(fig)
bars('avg', 'avg response time, ms (log)', 'cmp-avg', log=True)
bars('p95', 'p95 response time, ms (log)', 'cmp-p95', log=True)
bars('rps', 'throughput, HTTP req/s', 'cmp-rps')

# p95 по ендпоінтах (load)
fig, ax = plt.subplots(figsize=(9, 3.8))
names = list(summary['k6-load']['by_endpoint'].keys())
x = np.arange(len(names)); w = .38
for i, tool in enumerate(TOOLS):
    vals = [summary[f'{tool}-load']['by_endpoint'][n]['p95'] for n in names]
    b = ax.bar(x + (i - .5) * w, vals, w, color=COL[tool], label=tool); ax.bar_label(b, fmt='%.1f', fontsize=7)
ax.set_xticks(x, [n.replace('/shipments/{id}', '…/{id}') for n in names], rotation=15, fontsize=8)
ax.set_ylabel('p95, ms'); ax.set_title('LOAD: p95 за операціями'); ax.legend()
fig.tight_layout(); fig.savefig(f'{IMG}/endpoints-load.png'); plt.close(fig)

# ---------------- markdown таблиці ----------------
L = []
def row(*c): L.append('| ' + ' | '.join(str(x) for x in c) + ' |')
L.append('### Зведені метрики (HTTP-запити)\n')
row('Запуск', 'Max VU', 'Запитів', 'Throughput, req/s', 'Сценаріїв/с', 'avg, ms', 'med, ms', 'p95, ms', 'p99, ms', 'max, ms', 'Error rate', 'Checks/assertions OK', 'CPU SUT avg/max, % ядра')
row(*['---'] * 13)
for p in PROFILES:
    for tool in TOOLS:
        s = summary.get(f'{tool}-{p}')
        if not s: continue
        row(f'{tool} {p}', s['max_vus'], s['requests'], s['rps'], s['flows_per_s'], s['avg'], s['med'], s['p95'], s['p99'], s['max'],
            f"{s['err']*100:.2f}%", f"{s['checks']*100:.2f}%", f"{s.get('sut_cpu_avg','-')} / {s.get('sut_cpu_max','-')}")
L.append('\n### Thresholds\n')
row('Запуск', 'Критерій', 'Результат'); row('---', '---', '---')
for k, s in summary.items():
    for c, ok in s['thresholds'].items():
        row(k, c, '✅ PASS' if ok else '❌ FAIL')
L.append('\n### Spike по фазах\n')
row('Інструмент', 'Фаза', 'Throughput, req/s', 'avg, ms', 'p95, ms', 'p99, ms', 'max, ms', 'Error rate'); row(*['---'] * 8)
for tool in TOOLS:
    for ph, s in summary.get(f'{tool}-spike', {}).get('phases', {}).items():
        row(tool, ph, s['rps'], s['avg'], s['p95'], s['p99'], s['max'], f"{s['err']*100:.2f}%")
L.append('\n### По операціях (avg / p95, ms)\n')
names = list(summary['k6-baseline']['by_endpoint'].keys())
row('Операція', *[f'{t} {p}' for p in PROFILES for t in TOOLS]); row(*['---'] * (1 + 6))
for n in names:
    row(n, *[f"{summary[f'{t}-{p}']['by_endpoint'][n]['avg']} / {summary[f'{t}-{p}']['by_endpoint'][n]['p95']}" for p in PROFILES for t in TOOLS])
open(f'{ROOT}/report/metrics.md', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
