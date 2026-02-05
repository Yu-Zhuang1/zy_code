import os, pathlib
cwd = pathlib.Path('.').resolve()
print('cwd', cwd)
print('listing', [p.name for p in cwd.iterdir()][:50])
# try create
p = cwd/'session_output_dir'
p.mkdir(parents=True, exist_ok=True)
print('created?', p.exists(), p.is_dir())
print('listing after', [x.name for x in cwd.iterdir() if x.is_dir()][:50])
