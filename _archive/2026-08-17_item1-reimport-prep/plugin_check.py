import sys
sys.path.insert(0, r'C:\Users\Owner\ora-skills\tools')
from package_skills import plugin_of
for s in ['daily-brief', 'ora-setup-audit', 'package-and-stage-skill', 'register-scheduled-task']:
    print(s, '->', plugin_of(s))
