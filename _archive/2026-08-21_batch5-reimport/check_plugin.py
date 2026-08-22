import sys
sys.path.insert(0, 'tools')
from package_skills import plugin_of

for s in ['daily-brief', 'insurance-renewal-review', 'listing-agreement-qc',
          'register-scheduled-task', 'settlement-basis-extraction']:
    print(s, '->', plugin_of(s))
