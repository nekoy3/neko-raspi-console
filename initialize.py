"""Create initial auth if missing; never prints the password."""
import hashlib,json,secrets,os
from pathlib import Path
p=Path(os.environ.get('CONSOLE_DATA_DIR',str(Path(__file__).resolve().parent/'data')));p.mkdir(mode=0o700,exist_ok=True)
if not (p/'auth.json').exists():
 salt=secrets.token_bytes(16);password=secrets.token_urlsafe(18)
 (p/'auth.json').write_text(json.dumps({'username':os.environ.get('CONSOLE_USERNAME','admin'),'salt':salt.hex(),'hash':hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1).hex()}))
 (p/'login-password.txt').write_text(password+'\n')
 for name in ['auth.json','login-password.txt']:(p/name).chmod(0o600)
 print('Authentication initialized; initial password is in data/login-password.txt (600).')
else:print('Existing authentication preserved.')
