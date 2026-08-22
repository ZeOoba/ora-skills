import zipfile

for name in ['register-scheduled-task', 'daily-brief']:
    path = f'_staging/2026-08-14/{name}.skill'
    print(f'--- {name} ---')
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            print(f'  {info.filename}  ({info.file_size} bytes)')
