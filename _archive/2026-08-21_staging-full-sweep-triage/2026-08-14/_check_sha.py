import hashlib
for name in ['register-scheduled-task', 'daily-brief']:
    path = f'_staging/2026-08-14/{name}.skill'
    with open(path, 'rb') as f:
        h = hashlib.sha256(f.read()).hexdigest()
    print(f'{name}.skill  {h}')
