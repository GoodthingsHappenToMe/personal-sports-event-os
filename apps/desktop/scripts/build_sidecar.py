"""Run using build venv Python; final users need no Python installation."""
from pathlib import Path
import subprocess,sys
from PyInstaller.utils.hooks import collect_entry_point
root=Path(__file__).resolve().parents[1]
data,hidden=collect_entry_point('sports_os.modules')
triple=subprocess.check_output(['rustc','--print','host-tuple'],text=True).strip()
args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--name','sports-os-sidecar-'+triple,
      '--distpath',str(root/'src-tauri/binaries'),'--workpath',str(root/'build/sidecar'),'--specpath',str(root/'build'),
      '--collect-submodules','sports_os','--collect-submodules','sports_os_legacy','--copy-metadata','personal-sports-event-os']
for src,dest in data:args+=['--add-data',src+':'+dest]
for name in hidden:args+=['--hidden-import',name]
args+=[str(root/'scripts/sidecar_entry.py')]
subprocess.run(args,check=True)
