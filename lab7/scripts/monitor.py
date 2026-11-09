"""Щосекундний моніторинг: CPU процесу SUT (% одного ядра), RSS, і загальне завантаження CPU машини (%)."""
import sys, time, os
pid = sys.argv[1]; out = open(sys.argv[2], 'w')
tck = os.sysconf('SC_CLK_TCK'); ncpu = os.cpu_count()
def proc():
    f = open(f'/proc/{pid}/stat').read().rsplit(')', 1)[1].split()
    return int(f[11]) + int(f[12]), int(f[21]) * os.sysconf('SC_PAGE_SIZE') // 1024
def total():
    v = list(map(int, open('/proc/stat').readline().split()[1:]))
    return sum(v), v[3] + v[4]
out.write('ts,sut_cpu_pct,sut_rss_kb,host_cpu_pct\n')
p0, _ = proc(); t0, i0 = total()
while True:
    time.sleep(1)
    p1, rss = proc(); t1, i1 = total()
    host = 100 * (1 - (i1 - i0) / max(1, t1 - t0))
    out.write(f'{time.time():.0f},{100*(p1-p0)/tck:.1f},{rss},{host:.1f}\n'); out.flush()
    p0, t0, i0 = p1, t1, i1
