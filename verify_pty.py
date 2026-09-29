"""Isolated HTTP/WebSocket + pseudoterminal tests; never opens USB device."""
import asyncio, os, pty, ssl, time
from pathlib import Path
import aiohttp
from aiohttp import web,WSMsgType
import tempfile, subprocess, json, secrets, hashlib
fixture = tempfile.TemporaryDirectory()
p = Path(fixture.name)
salt = secrets.token_bytes(16)
(p/'auth.json').write_text(json.dumps({'username':'admin','salt':salt.hex(),'hash':hashlib.scrypt(b'test-only-invalid-target',salt=salt,n=16384,r=8,p=1).hex()}))
subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(p/'key.pem'),'-out',str(p/'cert.pem'),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
os.environ['CONSOLE_DATA_DIR'] = str(p)
os.environ['CONSOLE_ALLOWED_NETWORKS'] = '127.0.0.0/8'
import server as s
async def main():
 master,slave=pty.openpty(); os.set_blocking(master,False); device=os.ttyname(slave)
 s.ports=lambda:[{'id':'test-pty','device':device,'present':True,'name':'TEST ONLY','baud':9600,'busy':'test-pty' in s.active}]
 ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(s.DATA/'cert.pem',s.DATA/'key.pem')
 runner=web.AppRunner(s.app,access_log=None);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0,ssl_context=ctx);await site.start();port=site._server.sockets[0].getsockname()[1]
 base=f'https://127.0.0.1:{port}';s.allowed_hosts.add(f'127.0.0.1:{port}');s.sessions['test-token']=time.time()+60;headers={'Origin':base,'Cookie':'console_session=test-token'}
 client_ctx=ssl.create_default_context(cafile=str(s.DATA/'cert.pem'))
 try:
  async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=client_ctx)) as c:
   async with c.get(base+'/health',headers={'Host':'evil.invalid'}) as r:assert r.status==403;print('PASS host allowlist')
   try:await c.ws_connect(base+'/api/console?id=test-pty',headers={**headers,'Origin':'https://evil.invalid'});raise AssertionError()
   except aiohttp.WSServerHandshakeError as e:assert e.status==403;print('PASS cross-origin websocket rejected')
   ws=await c.ws_connect(base+'/api/console?id=test-pty',headers=headers);assert (await ws.receive_json())['writable'] is False
   await ws.send_json({'type':'input','data':'NO-TX'});await asyncio.sleep(.1)
   try:data=os.read(master,64)
   except BlockingIOError:data=b''
   assert not data;print('PASS readonly actually transmits zero bytes')
   os.write(master,b'DEVICE OUTPUT\r\n');m=await ws.receive(timeout=2);assert m.type==WSMsgType.BINARY and m.data==b'DEVICE OUTPUT\r\n';print('PASS serial RX exact bytes')
   await ws.send_json({'type':'mode','writable':True});await ws.receive_json()
   await ws.send_json({'type':'input','data':'PING\r'});ack=await ws.receive_json();assert ack=={'type':'tx','count':5};assert os.read(master,64)==b'PING\r';print('PASS serial TX exact bytes + acknowledgement')
   await ws.send_json({'type':'input','data':'x'*2049});await asyncio.sleep(.1)
   try:data=os.read(master,4096)
   except BlockingIOError:data=b''
   assert not data;print('PASS input greater than 2KB rejected')
   async with c.post(base+'/api/logout',headers=headers,json={}) as r:assert r.status==200
   m=await ws.receive(timeout=2);assert m.type in [WSMsgType.CLOSE,WSMsgType.CLOSED];print('PASS logout closes active websocket')
   await ws.close();await asyncio.sleep(.1);assert not s.active;print('PASS logout releases serial lock')
   for i in range(8):
    async with c.post(base+'/login',headers={'Origin':base},json={'username':'admin','password':'invalid'}) as r:assert r.status==401
   async with c.post(base+'/login',headers={'Origin':base},json={'username':'admin','password':'invalid'}) as r:assert r.status==429
   print('PASS login failure rate limit')
   s.sessions['test-token']=time.time()+60
   ws=await c.ws_connect(base+'/api/console?id=test-pty',headers=headers);await ws.receive_json();os.close(master);master=None
   m=await ws.receive(timeout=2);assert m.type==WSMsgType.TEXT and 'error' in m.data;await ws.receive(timeout=2);await ws.close();await asyncio.sleep(.1);assert not s.active;print('PASS device removal closes session + releases lock')
 finally:
  await runner.cleanup()
  if master is not None:os.close(master)
  os.close(slave)
try:
 asyncio.run(main())
finally:
 fixture.cleanup()
