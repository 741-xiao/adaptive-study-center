"""WeChat website sign-in and account-bound progress for the exam handbook."""
import hashlib
import html
import json
import licensing
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing, contextmanager
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
HOME = '计算机网络_分步备考手册.html'
PAGES = {HOME, '填空题.html', '大题.html'}
ASSETS = set('exam-data.js course-docs.js exam-common.js learning-centers.js bank-page.js exam.css account.js account.css license.css console-ui.css console-ui.js network-map.png'.split())
PORT = int(os.getenv('STUDY_PORT', '8765'))
ORIGIN = os.getenv('STUDY_ORIGIN', f'http://127.0.0.1:{PORT}').rstrip('/')
APP, SECRET = os.getenv('WECHAT_APP_ID',''), os.getenv('WECHAT_APP_SECRET','')
PREVIEW = not (APP or SECRET) and ORIGIN == f'http://127.0.0.1:{PORT}'
DB = Path(os.getenv('STUDY_DB', ROOT/'private-data'/'study.sqlite3'))
KEYS = {'cn_alg_mastered_v1','net_exam_coach_1',*('cn3:'+s for s in ['notes','posts','passes','projectDone','examLog','bank:填空','bank:大题','recent'])}
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
@contextmanager
def db():
    with closing(sqlite3.connect(DB, timeout=8)) as c, c: yield c
def init():
    DB.parent.mkdir(parents=True,exist_ok=True)
    with db() as c: c.executescript('''CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT NOT NULL DEFAULT '',student TEXT NOT NULL DEFAULT ''); CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,uid TEXT,csrf TEXT,expires INTEGER); CREATE TABLE IF NOT EXISTS states(token TEXT PRIMARY KEY,expires INTEGER); CREATE TABLE IF NOT EXISTS records(uid TEXT,k TEXT,v TEXT,rev INTEGER,PRIMARY KEY(uid,k));''')
    with db() as c: c.executescript(licensing.SCHEMA)
def framed(title, content):
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/account.css"><title>{title} · 学习中心</title></head><body class="access"><main><small>计算机网络　/　学习档案</small><h1>{title}</h1>{content}</main></body></html>'
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass  # OAuth callback query strings contain authorization codes.
    def reply(self,status,body='',kind='text/html; charset=utf-8',headers=()):
        data=body if isinstance(body,bytes) else body.encode(); self.send_response(status)
        for k,v in [('Content-Type',kind),('Content-Length',str(len(data))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','same-origin'),('X-Frame-Options','DENY'),*headers]: self.send_header(k,v)
        self.end_headers(); self.wfile.write(data)
    def redir(self,path,*headers): self.reply(303,headers=[('Location',path),*headers])
    def cookie(self,k):
        jar=SimpleCookie();jar.load(self.headers.get('Cookie',''));return jar[k].value if k in jar else ''
    def setting(self,k,v,ttl):return ('Set-Cookie',f'{k}={v}; Path=/; HttpOnly; SameSite=Lax; Max-Age={ttl}'+('; Secure' if ORIGIN.startswith('https:') else ''))
    def session(self,c):return c.execute('SELECT u.id,u.name,u.student,s.csrf FROM sessions s JOIN users u ON s.uid=u.id WHERE s.token=? AND s.expires>?',(digest(self.cookie('sid')),time.time())).fetchone()
    def create_session(self,c,uid):
        sid=secrets.token_urlsafe(32);c.execute('INSERT OR IGNORE INTO users(id) VALUES(?)',(uid,));c.execute('DELETE FROM sessions WHERE token=? OR expires<?',(digest(self.cookie('sid')),time.time()));c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(sid),uid,secrets.token_urlsafe(24),time.time()+7*86400));return self.setting('sid',sid,7*86400)
    def goodhost(self):return self.headers.get('Host','').lower()==urlsplit(ORIGIN).netloc.lower()
    def do_GET(self):
        if not self.goodhost():return self.reply(400)
        url=urlsplit(self.path); path=unquote(url.path);file=path[1:];q=parse_qs(url.query)
        if file in ASSETS:return self.reply(200,(ROOT/file).read_bytes(), 'application/javascript; charset=utf-8' if file.endswith('.js') else 'image/png' if file.endswith('.png') else 'text/css; charset=utf-8')
        with db() as c:
            u=self.session(c)
            if path=='/auth/start' and APP and SECRET:
                state=secrets.token_urlsafe(24);c.execute('DELETE FROM states WHERE expires<?',(time.time(),));c.execute('INSERT INTO states VALUES(?,?)',(digest(state),time.time()+600));return self.redir('https://open.weixin.qq.com/connect/qrconnect?'+urlencode(dict(appid=APP,redirect_uri=ORIGIN+'/auth/callback',response_type='code',scope='snsapi_login',state=state))+'#wechat_redirect',self.setting('wx_state',state,600))
            if path=='/auth/callback':
                state=q.get('state',[''])[0];code=q.get('code',[''])[0];valid=state.isascii() and secrets.compare_digest(state,self.cookie('wx_state')) and c.execute('DELETE FROM states WHERE token=? AND expires>?',(digest(state),time.time())).rowcount==1;c.commit()
                if not (APP and SECRET and valid and code):return self.reply(400,framed('授权未完成','<a href="/">重新登录</a>'))
                try:
                    with urlopen('https://api.weixin.qq.com/sns/oauth2/access_token?'+urlencode(dict(appid=APP,secret=SECRET,code=code,grant_type='authorization_code')),timeout=8) as r: result=json.load(r)
                    oid=result['openid']
                    if not isinstance(oid,str) or not oid or not result.get('access_token'):raise ValueError('invalid authorization response')
                except Exception:return self.reply(502,framed('微信授权未成功','<a href="/">重新授权</a>'))
                h=self.create_session(c,digest(APP+':'+oid));c.commit();return self.redir('/',h,self.setting('wx_state','',0))
            if path!='/' and file not in PAGES and path!='/account' and path not in licensing.GET:return self.reply(404)
            if not u:
                action='<form method="post" action="/preview"><button>进入本机体验</button></form><p>本机体验不是微信登录，不与正式账号共用数据。</p>' if PREVIEW else '<a class="wx" href="/auth/start">微信扫码登录</a>'
                return self.reply(200,framed('AI 智能学习中心',action))
            if not u[1] or path=='/account':return self.reply(200,framed('学生档案',f'<form method="post" action="/profile"><input type="hidden" name="csrf" value="{u[3]}"><label>姓名<input required name="name" maxlength="40" value="{html.escape(u[1],quote=True)}"></label><label>学号<input required name="student" maxlength="40" value="{html.escape(u[2],quote=True)}"></label><button>保存并进入学习中心</button></form><form method="post" action="/logout"><input type="hidden" name="csrf" value="{u[3]}"><button class="quiet">退出登录</button></form>'))
            if path in licensing.GET:return licensing.get(self,c,u,path,q)
            records={k:[json.loads(v),rev] for k,v,rev in c.execute('SELECT k,v,rev FROM records WHERE uid=?',(u[0],))};boot=json.dumps(dict(name=u[1],student=u[2],csrf=u[3],records=records,preview=PREVIEW,licenseAdmin=licensing.staff(c,u[0])),ensure_ascii=True).replace('<','\\u003c');doc=(ROOT/(file or HOME)).read_text('utf-8-sig');return self.reply(200,doc.replace('<head>','<head><script>window.STUDY_ACCOUNT='+boot+';</script>',1))
    def do_POST(self):
        if not self.goodhost() or self.headers.get('Origin')!=ORIGIN:return self.reply(403)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<=size<=5000000:return self.reply(413)
            raw=self.rfile.read(size).decode(); payload=json.loads(raw) if self.headers.get_content_type()=='application/json' else {k:v[0] for k,v in parse_qs(raw).items()}
            if not isinstance(payload,dict):raise ValueError()
        except (UnicodeError,ValueError):return self.reply(400)
        with db() as c:
            if self.path=='/preview' and PREVIEW:
                device=self.cookie('preview_device');device=device if re.fullmatch('[A-Za-z0-9_-]{43}',device) else secrets.token_urlsafe(32);h=self.create_session(c,'local:'+digest(device));c.commit();return self.redir('/',h,self.setting('preview_device',device,31536000))
            u=self.session(c)
            if not u:return self.reply(401)
            if payload.get('csrf')!=u[3]:return self.reply(403)
            if self.path=='/logout':
                c.execute('DELETE FROM sessions WHERE token=?',(digest(self.cookie('sid')),));c.commit();return self.redir('/',self.setting('sid','',0))
            if self.path=='/profile':
                name,student=str(payload.get('name','')).strip(),str(payload.get('student','')).strip()
                if not name or len(name)>40 or not re.fullmatch(r'[\w.-]{1,40}',student):return self.reply(400,framed('请检查资料','姓名不超过 40 字，学号可用字母、数字、下划线、点或短横线。<a href="/account">返回</a>'))
                c.execute('UPDATE users SET name=?,student=? WHERE id=?',(name,student,u[0]));c.commit();return self.redir('/')
            if self.path in licensing.POST and u[1]:return licensing.post(self,c,u,self.path,payload)
            if self.path!='/save' or not u[1]:return self.reply(403)
            k=payload.get('key');rev=payload.get('rev');v=payload.get('value');
            if not isinstance(k,str) or k not in KEYS or type(rev)!=int or rev<0 or not valid_data(k,v):return self.reply(400)
            c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT rev FROM records WHERE uid=? AND k=?',(u[0],k)).fetchone()
            if (row[0] if row else 0)!=rev:return self.reply(409)
            c.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?)',(u[0],k,json.dumps(v,ensure_ascii=False),rev+1));c.commit();return self.reply(200,'{}','application/json')

def valid_data(k,v):
    if k=='cn_alg_mastered_v1':return isinstance(v,list) and len(v)<=55 and all(type(x)==int and 1<=x<=55 for x in v)
    if k=='net_exam_coach_1':
        return isinstance(v,dict) and all(i in {'2','8','17','27','41','51'} and isinstance(r,dict) and all((key in {'wins','miss','streak','due','last','seed'} and type(val) in (int,float) and val>=0) or (key=='error' and isinstance(val,str)) or (key=='errors' and isinstance(val,list) and all(isinstance(a,dict) and all(isinstance(s,str) for s in a.values()) for a in val)) for key,val in r.items()) for i,r in v.items())
    if k in ('cn3:notes','cn3:posts'):return isinstance(v,list) and all(isinstance(x,str) for x in v)
    if k=='cn3:passes':return type(v)==int and v>=0
    if k=='cn3:projectDone':return type(v)==bool
    if k=='cn3:examLog':return isinstance(v,list) and all(isinstance(x,dict) and all(type(j)==int for j in x.values()) for x in v)
    if k.startswith('cn3:bank:'):return isinstance(v,dict) and all(re.fullmatch(r'[1-6]-[fw]-A?\d+',i) and isinstance(r,dict) and all((j=='star' and type(a)==bool) or (j in {'status','draft'} and isinstance(a,str)) for j,a in r.items()) for i,r in v.items())
    return k=='cn3:recent' and isinstance(v,str) and bool(re.fullmatch(r'[1-6]-[fw]-A?\d+',v))

if __name__=='__main__':
    if not PREVIEW and not (APP and SECRET and re.fullmatch(r'https://[a-zA-Z0-9.-]+(?::\d+)?',ORIGIN)):raise SystemExit('正式模式需要 WECHAT_APP_ID、WECHAT_APP_SECRET 和 HTTPS STUDY_ORIGIN。')
    init();print(f'Study center: {ORIGIN}',flush=True);ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
