import json, io, datetime, zoneinfo

ET = zoneinfo.ZoneInfo("America/New_York")
CC = r"C:\Users\Owner\AppData\Roaming\Claude\claude-code-sessions\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\583f08bc-0123-4111-8158-8fe3d927e350\scheduled-tasks.json"
LAMS = r"C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\583f08bc-0123-4111-8158-8fe3d927e350\scheduled-tasks.json"

def load(p):
    with io.open(p, encoding="utf8") as f:
        return json.load(f)["scheduledTasks"]

def et(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, ET).strftime("%Y-%m-%d %H:%M %Z (%a)")

for label, p in (("CC/MCP", CC), ("LAMS", LAMS)):
    t = load(p)
    en = [x for x in t if x.get("enabled")]
    dis = [x for x in t if not x.get("enabled")]
    print(f"### {label}: {len(t)} total | {len(en)} enabled | {len(dis)} disabled")
    for x in en:
        print("   ENABLED:", x["id"], "| fireAt:", et(x["fireAt"]) if x.get("fireAt") else x.get("cronExpression"))
    print()

print("=" * 90)
for x in load(CC):
    if "pause-resume" in x["id"]:
        print(json.dumps(x, indent=2, ensure_ascii=False)[:6000])
