import json, io, sys

paths = [
 (r"CC/MCP", r"C:\Users\Owner\AppData\Roaming\Claude\claude-code-sessions\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\583f08bc-0123-4111-8158-8fe3d927e350\scheduled-tasks.json"),
 (r"LAMS  ", r"C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\583f08bc-0123-4111-8158-8fe3d927e350\scheduled-tasks.json"),
]

def walk(o):
    """yield dicts that look like task records"""
    if isinstance(o, dict):
        keys = set(o.keys())
        if {"id"} & keys and ({"cronExpression","schedule","cron","runAt","fireAt","nextRunAt","enabled"} & keys):
            yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)

for label, p in paths:
    print("=" * 100)
    print(label, p)
    with io.open(p, encoding="utf8") as f:
        j = json.load(f)
    print("  top-level type:", type(j).__name__, "keys:", list(j)[:12] if isinstance(j, dict) else len(j))
    recs = list(walk(j))
    print("  task-like records:", len(recs))
    for t in recs:
        print("   -", json.dumps({k: t.get(k) for k in
              ("id","name","enabled","cronExpression","cron","schedule","runAt","fireAt","nextRunAt","type","oneTime")
              if k in t}, ensure_ascii=False))
