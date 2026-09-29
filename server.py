import asyncio, collections, hashlib, hmac, json, logging, os, secrets, ssl, time
from pathlib import Path
import serial
import ipaddress
from logging.handlers import RotatingFileHandler
from aiohttp import web, WSMsgType
BASE = Path(__file__).resolve().parent
DATA = Path(os.environ.get('CONSOLE_DATA_DIR', str(BASE / 'data'))); DATA.mkdir(mode=0o700, exist_ok=True)
BAUDS = [9600,19200,38400,57600,115200]
CONFIG = DATA / 'ports.json'
AUTH = json.loads((DATA/'auth.json').read_text())
sessions = {}; failures = collections.defaultdict(list); active = {}; sockets = {}
allowed_hosts = set(os.environ.get('CONSOLE_ALLOWED_HOSTS', 'localhost:8443,127.0.0.1:8443').split(','))
allowed_networks = [ipaddress.ip_network(n) for n in os.environ.get('CONSOLE_ALLOWED_NETWORKS', '127.0.0.0/8,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12').split(',')]
login_username = AUTH.get('username', os.environ.get('CONSOLE_USERNAME', 'admin'))
display_host = os.environ.get('CONSOLE_DISPLAY_HOST', 'localhost')
def ports():
    return [{'id':p.name,'device':str(p),'present':p.exists(),'name':json.loads((DATA/'labels.json').read_text()).get(p.name,p.name.replace('usb-','').replace('-if00-port0','')) if (DATA/'labels.json').exists() else p.name.replace('usb-','').replace('-if00-port0',''),'baud':json.loads(CONFIG.read_text()).get(p.name,9600) if CONFIG.exists() else 9600,'busy':p.name in active} for p in sorted(Path('/dev/serial/by-id').glob('*'))]
def audit(event, **kw): logging.info(json.dumps({'event':event,**kw},ensure_ascii=False))
def authenticated(r): return sessions.get(r.cookies.get('console_session'),0)>time.time()
@web.middleware
async def guard(r, handler):
    if not any(ipaddress.ip_address(r.remote) in n for n in allowed_networks): raise web.HTTPForbidden(text='Private network only')
    if r.host not in allowed_hosts: raise web.HTTPForbidden(text='Invalid host')
    if r.path.startswith('/api/') and not authenticated(r): raise web.HTTPUnauthorized(text='ログインしてください')
    if r.method not in ('GET','HEAD') or r.path == '/api/console':
        if r.headers.get('Origin') != 'https://'+r.host: raise web.HTTPForbidden(text='Invalid origin')
    resp = await handler(r)
    resp.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' wss:; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
    return resp
async def login(r):
    ip=r.remote; now=time.time(); failures[ip]=[x for x in failures[ip] if x>now-300]
    if len(failures[ip])>=8: raise web.HTTPTooManyRequests(text='5分後に再試行してください')
    d=await r.json(); candidate=hashlib.scrypt(str(d.get('password','')).encode(),salt=bytes.fromhex(AUTH['salt']),n=16384,r=8,p=1).hex()
    if d.get('username')!=login_username or not hmac.compare_digest(candidate,AUTH['hash']):
        failures[ip].append(now); audit('login_failed',ip=ip); raise web.HTTPUnauthorized(text='ログイン情報が違います')
    for token, expiry in list(sessions.items()):
        if expiry<now: sessions.pop(token,None)
    if len(sessions)>=128: raise web.HTTPServiceUnavailable()
    token=secrets.token_urlsafe(32); sessions[token]=now+28800; failures.pop(ip,None)
    resp=web.json_response({'ok':True}); resp.set_cookie('console_session',token,secure=True,httponly=True,samesite='Strict',max_age=28800); audit('login',ip=ip); return resp
async def logout(r):
    token=r.cookies.get('console_session'); sessions.pop(token,None)
    for ws in list(sockets.get(token,[])): await ws.close()
    resp=web.json_response({'ok':True}); resp.del_cookie('console_session'); return resp
async def status(r): return web.json_response({'host':display_host,'ports':ports(),'bauds':BAUDS,'settings':'8N1 / flow control OFF','uptime':round(time.monotonic()-START)})
async def settings(r):
    d=await r.json(); ident=d.get('id'); baud=d.get('baud')
    if ident not in {p['id'] for p in ports()} or baud not in BAUDS: raise web.HTTPBadRequest()
    if ident in active: raise web.HTTPConflict(text='切断してから設定してください')
    config=json.loads(CONFIG.read_text()) if CONFIG.exists() else {}; config[ident]=baud
    tmp=CONFIG.with_suffix('.tmp'); tmp.write_text(json.dumps(config)); tmp.chmod(0o600); tmp.replace(CONFIG)
    audit('baud_change',port=ident,baud=baud); return web.json_response({'ok':True})
async def console(r):
    ident=r.query.get('id'); entry=next((p for p in ports() if p['id']==ident),None)
    if not entry: raise web.HTTPNotFound(text='ケーブルがありません')
    if ident in active: raise web.HTTPConflict(text='使用中です')
    active[ident]=True; ws=web.WebSocketResponse(heartbeat=20,max_msg_size=4096); ser=None; reader=None; writable=False; received=sent=0
    token=r.cookies.get('console_session')
    try:
        ser=serial.Serial(port=None,baudrate=entry['baud'],timeout=0,write_timeout=0.5,exclusive=True)
        ser.dtr=False; ser.rts=False; ser.port=entry['device']; ser.open()
        await ws.prepare(r); sockets.setdefault(token,[]).append(ws)
        await ws.send_json({'type':'status','state':'connected','writable':False,'baud':entry['baud']})
        audit('connect',port=ident,baud=entry['baud'],ip=r.remote)
        async def receive():
            nonlocal received
            try:
                while not ws.closed:
                    if not authenticated(r): await ws.close(code=1008,message=b'Session expired'); break
                    data=ser.read(4096)
                    if data: received+=len(data); await ws.send_bytes(data)
                    await asyncio.sleep(0.02)
            except (serial.SerialException,OSError):
                await ws.send_json({'type':'error','message':'ケーブルが外れたか、受信に失敗しました'}); await ws.close()
        reader=asyncio.create_task(receive())
        async for msg in ws:
            if not authenticated(r): await ws.close(code=1008); break
            if msg.type == WSMsgType.TEXT:
                try: d=json.loads(msg.data)
                except ValueError: continue
                if d.get('type')=='mode':
                    writable=d.get('writable') is True; audit('write_mode',port=ident,enabled=writable)
                    await ws.send_json({'type':'mode','writable':writable})
                elif d.get('type')=='input' and writable:
                    data=str(d.get('data','')).encode('utf-8')
                    if len(data)>2048: continue
                    try:
                        count=await asyncio.to_thread(ser.write,data); sent+=count
                        await ws.send_json({'type':'tx','count':count})
                    except (serial.SerialException,OSError): await ws.close(); break
    except (serial.SerialException,OSError) as e:
        audit('serial_error',port=ident,error=type(e).__name__)
        if ws.prepared: await ws.close()
        else: raise web.HTTPServiceUnavailable(text='シリアルポートを開けません')
    finally:
        if reader: reader.cancel(); await asyncio.gather(reader,return_exceptions=True)
        if ser and ser.is_open: ser.close()
        active.pop(ident,None)
        if ws in sockets.get(token,[]): sockets[token].remove(ws)
        audit('disconnect',port=ident,rx=received,tx=sent)
    return ws
async def index(r): return web.FileResponse(BASE/'static/index.html')
async def health(r): return web.json_response({'ok':True})
START=time.monotonic()
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s',handlers=[logging.StreamHandler(),RotatingFileHandler(DATA/'audit.log',maxBytes=2*1024*1024,backupCount=3)])
app=web.Application(middlewares=[guard],client_max_size=8192)
app.router.add_get('/',index); app.router.add_get('/health',health)
app.router.add_post('/login',login); app.router.add_post('/api/logout',logout)
app.router.add_get('/api/status',status); app.router.add_post('/api/settings',settings); app.router.add_get('/api/console',console,allow_head=False)
app.router.add_static('/static',BASE/'static',show_index=False)
if __name__=='__main__':
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(DATA/'cert.pem',DATA/'key.pem')
    web.run_app(app,host=os.environ.get('CONSOLE_BIND','127.0.0.1'),port=int(os.environ.get('CONSOLE_PORT','8443')),ssl_context=ctx,access_log=None)
