"""Короткий підсумок з target/surefire-reports/TEST-*.xml: порядок виконання і результат кожного тесту."""
import glob, sys, xml.etree.ElementTree as ET
d = sys.argv[1] if len(sys.argv) > 1 else 'target/surefire-reports'
for f in sorted(glob.glob(f'{d}/TEST-*.xml')):
    root = ET.parse(f).getroot()
    print(f"{root.get('name').split('.')[-1]}: tests={root.get('tests')} failures={root.get('failures')} errors={root.get('errors')}")
    for i, tc in enumerate(root.findall('testcase'), 1):
        res = 'PASS'
        for tag in ('failure', 'error'):
            e = tc.find(tag)
            if e is not None:
                msg = (e.get('message') or e.get('type') or '').replace('\n', ' ')[:110]
                res = f'{tag.upper()}: {msg}'
        print(f'  {i:2}. {tc.get("name"):28} {res}')
