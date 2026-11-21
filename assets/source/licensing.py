"""Account-bound study licenses. Only the local operator CLI may assign staff roles."""
import argparse
import hashlib
import json
import math
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from html import escape
from urllib.parse import urlencode

DAY = 86400
GET = {'/license', '/license/activate', '/admin/licenses','/admin/overview'}
POST = {'/license/redeem', '/license/bind', '/admin/licenses/issue', '/admin/licenses/revoke'}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS license_staff(uid TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS licenses(id INTEGER PRIMARY KEY, hash TEXT UNIQUE NOT NULL, days INTEGER NOT NULL, seats INTEGER NOT NULL, issued INTEGER NOT NULL, issuer TEXT NOT NULL, owner TEXT, start INTEGER, until_ts INTEGER, closed TEXT NOT NULL DEFAULT '');
CREATE UNIQUE INDEX IF NOT EXISTS one_current_license ON licenses(owner) WHERE closed='' AND owner IS NOT NULL;
CREATE TABLE IF NOT EXISTS license_devices(lid INTEGER, device TEXT, PRIMARY KEY(lid,device));
CREATE TABLE IF NOT EXISTS license_trials(uid TEXT PRIMARY KEY, window INTEGER, hits INTEGER);
'''
BASE = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/account.css"><link rel="stylesheet" href="/license.css"><title>{title} · 网络研习室</title></head><body class="lic {theme}"><header><a href="/">网络研习室</a><nav><a href="/">学习首页</a><a href="/license">我的授权</a>{admin}</nav></header><main><h1>{title}</h1>{body}</main></body></html>'''
def staff(c,uid): return bool(c.execute('SELECT 1 FROM license_staff WHERE uid=?',(uid,)).fetchone())
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def ref(uid): return sha('staff-ref:'+uid)[:20]
def date(ts): return datetime.fromtimestamp(ts,timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M') if ts else '未开始'
def status(row,now): return row['closed'] or ('待激活' if row['owner'] is None else '已到期' if row['until_ts']<=now else '有效')
def ident(i): return f'LS-{i:06d}'
def begin(u,path):return f'<form method="post" action="{path}"><input type="hidden" name="csrf" value="{escape(u[3],quote=True)}">'
def device(h):
    token=h.cookie('study_device');return sha(token) if re.fullmatch('[A-Za-z0-9_-]{43}',token) else ''
def device_token(h):
    key=device(h)
    if key:return key,[]
    token=secrets.token_urlsafe(32);return sha(token),[h.setting('study_device',token,365*DAY)]
def page(h,c,u,title,body,code=200):
    a='<a href="/admin/licenses">授权后台</a>' if staff(c,u[0]) else ''
    h.reply(code,BASE.format(title=title,body=body,admin=a,theme='ops' if title=='授权后台' else 'student'))
def notice(h,c,u,msg,code=400,back='/license'):
    return page(h,c,u,'授权操作',f'<p role="status">{msg}</p><a class="button" href="{back}">返回</a>',code)
def current(c,uid):
    return c.execute("SELECT * FROM licenses WHERE owner=? ORDER BY (closed='') DESC,start DESC,id DESC LIMIT 1",(uid,)).fetchone()
def stats(pairs):return '<dl class="metrics">'+''.join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k,v in pairs)+'</dl>'
def get(h,c,u,path,query):
    c.row_factory=sqlite3.Row
    admin=staff(c,u[0]); ops=path.startswith('/admin/')
    if ops and not admin:return notice(h,c,u,'此账号没有后台权限。',403)
    sql='SELECT l.id,l.owner,l.issued,l.start,l.until_ts,l.days,l.seats,l.closed,u.name,u.student,(SELECT COUNT(*) FROM license_devices d WHERE d.lid=l.id) AS devices,EXISTS(SELECT 1 FROM license_devices d WHERE d.lid=l.id AND d.device=?) AS bound FROM licenses l LEFT JOIN users u ON u.id=l.owner'
    rows=[dict(id=r['id'],mine=r['owner']==u[0],issued=r['issued']*1000,start=(r['start'] or 0)*1000,end=(r['until_ts'] or 0)*1000,days=r['days'],seats=r['seats'],devices=r['devices'],closed=r['closed'],name=r['name'] or '',student=r['student'] or '',bound=bool(r['bound'])) for r in c.execute(sql+('' if ops else ' WHERE l.owner=?'),(device(h),) if ops else (device(h),u[0]))]
    view={'/license':'student','/license/activate':'activate','/admin/overview':'admin','/admin/licenses':'ledger'}[path]
    data=json.dumps(dict(view=view,rows=rows,admin=admin,name=u[1],csrf=u[3],ref=ref(u[0])),ensure_ascii=True).replace('<','\\u003c')
    h.reply(200,'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>授权中心</title><link rel="stylesheet" href="/console-ui.css"></head><body><div id="consoleApp"></div><script>window.LICENSE_PAGE='+data+';</script><script src="/console-ui.js"></script></body></html>')

def legacy_view(h,c,u,path,query):
    c.row_factory=sqlite3.Row;now=int(time.time());uid=u[0]
    if path=='/admin/licenses':
        if not staff(c,uid):return notice(h,c,u,'此账号没有后台权限。',403)
        kw=query.get('q',[''])[0][:64];flt=query.get('state',[''])[0];labels=['待激活','有效','已到期','已撤销','已更换'];flt=flt if flt in labels else ''
        state="CASE WHEN closed<>'' THEN closed WHEN owner IS NULL THEN '待激活' WHEN until_ts<=? THEN '已到期' ELSE '有效' END"
        counts=dict(c.execute('SELECT '+state+' AS s,count(*) FROM licenses GROUP BY s',(now,)).fetchall());summary=stats([(s,counts.get(s,0)) for s in labels]);base=" FROM licenses l LEFT JOIN users u ON u.id=l.owner WHERE (instr(coalesce(u.name,''),?) OR instr(coalesce(u.student,''),?) OR instr(printf('LS-%06d',l.id),?))";args=[kw,kw,kw.upper()]
        if flt:base+=' AND '+state+'=?';args.extend([now,flt])
        total=c.execute('SELECT count(*)'+base,args).fetchone()[0];pages=max(1,math.ceil(total/25));raw=query.get('p',['1'])[0];p=max(1,min(pages,int(raw))) if re.fullmatch(r'[0-9]{1,7}',raw) else 1
        table='';
        for r in c.execute('SELECT l.*,u.name,u.student,(SELECT count(*) FROM license_devices WHERE lid=l.id) AS devices'+base+' ORDER BY l.id DESC LIMIT 25 OFFSET ?',args+[(p-1)*25]):
            s=status(r,now);ctrl=begin(u,'/admin/licenses/revoke')+f'<input type="hidden" name="id" value="{r["id"]}"><details><summary>撤销</summary><button>确认撤销</button></details></form>' if not r['closed'] else '—'
            table+=f'<tr><td>{ident(r["id"])}</td><td>{escape(r["name"] or "未领取")}<small>{escape(r["student"] or "")}</small></td><td>{s}</td><td>{r["days"]} 天</td><td>{date(r["until_ts"])}</td><td>{r["devices"]}/{r["seats"]}</td><td>{ctrl}</td></tr>'
        links=' '.join(f'<a href="?{escape(urlencode(dict(q=kw,state=flt,p=i)),quote=True)}">{label}</a>' for i,label in [(p-1,'上一页'),(p+1,'下一页')] if 1<=i<=pages)
        body=summary+'<h2>签发授权码</h2>'+begin(u,'/admin/licenses/issue')+'<label>时长 <select name="days"><option value="7">7 天</option><option value="30">30 天</option><option selected value="365">365 天</option></select></label><label>设备上限 <select name="seats"><option>1</option><option selected>2</option><option>3</option></select></label><button>创建授权码</button></form><h2>授权记录</h2>'+f'<form method="get"><input name="q" aria-label="搜索授权" placeholder="姓名、学号或授权编号" value="{escape(kw,quote=True)}"><select aria-label="授权状态" name="state"><option value="">全部状态</option>'+''.join(f'<option {"selected" if flt==s else ""}>{s}</option>' for s in labels)+'</select><button>筛选</button></form><div class="scroll"><table><thead><tr>'+''.join(f'<th>{s}</th>' for s in ['授权编号','学生','状态','时长','到期时间（北京时间）','设备','操作'])+'</tr></thead><tbody>'+(table or '<tr><td colspan="7">暂无匹配的授权记录</td></tr>')+f'</tbody></table></div><p>{total} 条 · 第 {p}/{pages} 页　{links}</p>'
        return page(h,c,u,'授权后台',body)
    r=current(c,uid);state=status(r,now) if r else '未激活';signed=state=='有效'
    if path=='/license/activate':return page(h,c,u,'激活授权',f'<p>授权账号：{escape(u[1])} · {escape(u[2])}</p>'+begin(u,'/license/redeem')+'<label>授权码<input required name="code" maxlength="32" spellcheck="false" autocomplete="off" placeholder="XXXX-XXXX-XXXX-XXXX"></label><button>激活并绑定此浏览器</button></form><p>每个码只可由一个账号领取。续期从当前有效期末累加，更换后设备名额重新绑定。</p>')
    bound=r and c.execute('SELECT 1 FROM license_devices WHERE lid=? AND device=?',(r['id'],device(h))).fetchone();count=c.execute('SELECT count(*) FROM license_devices WHERE lid=?',(r['id'],)).fetchone()[0] if r else 0
    body=f'<div class="statusline"><b>{state}</b><span>{escape(u[1])} · {escape(u[2])}</span></div>'+stats([('剩余天数',max(0,math.ceil((r['until_ts']-now)/DAY)) if signed else 0),('授权编号',ident(r['id']) if r else '—'),('设备名额',f'{count} / {r["seats"]}' if r else '—')]);body+=f'<h2>授权信息</h2><p>开始时间：{date(r["start"]) if r else "—"}　到期时间：{date(r["until_ts"]) if r else "—"}（北京时间）</p><p>当前浏览器：{"已绑定" if bound else "未绑定"}</p>'
    if signed and not bound:body+=begin(u,'/license/bind')+'<button>绑定当前浏览器</button></form>'
    goal='使用新码续期' if signed else '激活授权';body+=f'<a class="button" href="/license/activate">{goal}</a><p><small>账户识别号：<code>{ref(uid)}</code></small></p>';return page(h,c,u,'我的授权',body)

def post(h,c,u,path,data):
    c.row_factory=sqlite3.Row;uid=u[0];now=int(time.time());c.execute('BEGIN IMMEDIATE')
    if path.startswith('/admin/'):
        if not staff(c,uid):return notice(h,c,u,'此账号没有后台权限。',403)
        if path.endswith('/issue'):
            d=str(data.get('days'));n=str(data.get('seats'))
            if d not in {'7','30','365'} or n not in {'1','2','3'}:return notice(h,c,u,'签发参数无效。')
            token=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(16));i=c.execute('INSERT INTO licenses(hash,days,seats,issued,issuer) VALUES(?,?,?,?,?)',(sha(token),int(d),int(n),now,uid)).lastrowid;c.commit();return page(h,c,u,'授权码已签发',f'<p>{ident(i)} · {d} 天 · {n} 台设备</p><output>{"-".join(token[j:j+4] for j in range(0,16,4))}</output><p>明码仅本次显示，请单独交给领取人。</p><a href="/admin/licenses">返回后台</a>')
        i=str(data.get('id',''));valid=re.fullmatch('[0-9]{1,16}',i) and c.execute("UPDATE licenses SET closed='已撤销' WHERE id=? AND closed=''",(i,)).rowcount
        if not valid:return notice(h,c,u,'此记录不可撤销。',400,'/admin/licenses')
        c.commit();return h.redir('/admin/licenses')
    r=current(c,uid);key,headers=device_token(h)
    if path=='/license/bind':
        if not r or status(r,now)!='有效':return notice(h,c,u,'需要有效授权。',403)
        i=r['id'];old=c.execute('SELECT device FROM license_devices WHERE lid=?',(i,)).fetchall()
        if key not in [x[0] for x in old] and len(old)>=r['seats']:return notice(h,c,u,'设备名额已满。',409)
    else:
        c.execute('INSERT INTO license_trials VALUES(?,?,1) ON CONFLICT(uid) DO UPDATE SET hits=CASE WHEN window<=? THEN 1 ELSE hits+1 END,window=CASE WHEN window<=? THEN excluded.window ELSE window END',(uid,now,now-300,now-300));hits=c.execute('SELECT hits FROM license_trials WHERE uid=?',(uid,)).fetchone()[0]
        if hits>15:return notice(h,c,u,'尝试过于频繁，请稍后再试。',429)
        code=str(data.get('code','')).strip().upper().replace('-','');new=c.execute("SELECT * FROM licenses WHERE hash=? AND owner IS NULL AND closed=''",(sha(code),)).fetchone()
        if not new:return notice(h,c,u,'授权码无效或已被领取。',400,'/license/activate')
        end=max(now,r['until_ts']) if r and status(r,now)=='有效' else now
        c.execute("UPDATE licenses SET closed='已更换' WHERE owner=? AND closed=''",(uid,));i=new['id'];c.execute('UPDATE licenses SET owner=?,start=?,until_ts=? WHERE id=?',(uid,now,end+new['days']*DAY,i))
    c.execute('INSERT OR IGNORE INTO license_devices VALUES(?,?)',(i,key));c.commit();return h.redir('/license',*headers)

if __name__=='__main__':
    from account_server import db, init
    parser=argparse.ArgumentParser(description='按学生页面的账户识别号管理授权管理员');parser.add_argument('action',choices=['grant','remove']);parser.add_argument('reference');args=parser.parse_args();init()
    with db() as c:
        matches=[uid for uid, in c.execute('SELECT id FROM users') if ref(uid)==args.reference];
        if len(matches)!=1:parser.error('未找到唯一匹配账号。')
        c.execute('INSERT OR IGNORE INTO license_staff VALUES(?)' if args.action=='grant' else 'DELETE FROM license_staff WHERE uid=?',matches);print('授权管理员角色已更新。')
