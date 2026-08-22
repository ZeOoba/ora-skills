import sys
sys.path.insert(0, 'tools')
from package_skills import plugin_of
result = plugin_of('repo-architecture-review')
print('PLUGIN_OF_RESULT:', result)
