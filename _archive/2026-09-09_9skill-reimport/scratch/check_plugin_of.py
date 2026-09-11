import sys
sys.path.insert(0, 'tools')
from package_skills import plugin_of

skills = ['annual-cycle','cash-position-monitor','debt-management','disposition-analysis',
          'lease-form-qc','lease-generation','lease-renewal-pipeline','parcel-data-recovery',
          'security-and-hardening']
for s in skills:
    print(s, '->', plugin_of(s))
