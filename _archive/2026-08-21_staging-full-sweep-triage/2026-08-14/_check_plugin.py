import sys
sys.path.insert(0, 'tools')
from package_skills import plugin_of
print('register-scheduled-task:', plugin_of('register-scheduled-task'))
print('daily-brief:', plugin_of('daily-brief'))
