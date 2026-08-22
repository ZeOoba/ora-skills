import sys
sys.path.insert(0, 'tools')
from package_skills import plugin_of

skills = [
    'acquisition-underwriting', 'census-acs-extract', 'communication-intelligence',
    'conversation-archival', 'deal-comparison', 'document-assembly',
    'file-reconciliation', 'fleet-advisory-remediation', 'graph-app-registration',
    'legal-intelligence', 'orphaned-task-forensics', 'portfolio-growth',
    'portfolio-reporting', 'rent-comp', 'tenant-intelligence',
]
for s in skills:
    print(s, '->', plugin_of(s))
