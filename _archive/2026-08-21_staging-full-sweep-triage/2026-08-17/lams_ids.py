import json, io
p = r"C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\583f08bc-0123-4111-8158-8fe3d927e350\scheduled-tasks.json"
t = json.load(io.open(p, encoding="utf8"))["scheduledTasks"]
rec = [x for x in t if not x.get("enabled") and x.get("cronExpression")]
one = [x for x in t if not x.get("enabled") and not x.get("cronExpression")]
print("DISABLED RECURRING (%d):" % len(rec))
print(", ".join(x["id"] for x in rec))
print()
print("DISABLED ONE-TIME (%d) - do NOT resume, verify individually:" % len(one))
for x in one:
    print("  ", x["id"], x.get("fireAt"))
