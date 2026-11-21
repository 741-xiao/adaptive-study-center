import {readFile,writeFile} from 'node:fs/promises';
const read=p=>readFile(p,'utf8');
const image='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%221%22 height=%221%22/%3E';
const home='计算机网络_分步备考手册.html';
const assets={};
for(const n of ['account.js','exam-common.js','bank-page.js','learning-centers.js','exam-data.js','course-docs.js','console-ui.js','account.css','exam.css','console-ui.css'])assets[n]=(await read(n)).replaceAll(' url(network-map.png)','');
assets['account.js']=assets['account.js'].replace('http://127.0.0.1:8765/','http://127.0.0.1:8766/');
assets['learning-centers.js']=assets['learning-centers.js'].replace("location.href=key==='blanks'?pages['填空']:pages['大题']","location.href=key==='blanks'?'?page=blanks':'?page=written'");
const bridge=`<script>document.addEventListener('click',ev=>{const a=ev.target.closest('a');if(!a)return;const raw=a.getAttribute('href')||'',m=raw.match(/^(填空题|大题|计算机网络_分步备考手册)\\.html(?:\\?(.*))?$/);if(m){a.href='?page='+({'填空题':'blanks','大题':'written','计算机网络_分步备考手册':'home'}[m[1]])+(m[2]?'&'+m[2]:'')}},true);document.addEventListener('DOMContentLoaded',()=>{const links=document.querySelector('#hub .entrylinks');if(links){links.insertAdjacentHTML('afterbegin','<a href="?page=student"><b>学生授权中心</b></a><a href="?page=admin"><b>管理员后台</b></a>')}});</script>`;
const consolePage='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="console-ui.css"></head><body><div id="consoleApp"></div><script src="console-ui.js"></script></body></html>';
// Keep one copy of the bank and chapter sources shared across all document routes.
const pages={home:await read(home),blanks:await read('填空题.html'),written:await read('大题.html'),console:consolePage};
const safe=o=>JSON.stringify(o).replaceAll('<','\\u003c');
const output=`<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>计算机网络 · 完整学习中心</title></head><body><script>(()=>{const pages=${safe(pages)},assets=${safe(assets)},image=${safe(image)},bridge=${safe(bridge)};const k=new URLSearchParams(location.search).get('page');const name=['student','activate','admin','ledger'].includes(k)?'console':['blanks','written'].includes(k)?k:'home';const doc=pages[name].replace(/<link rel="stylesheet" href="([^"]+)">/g,(_,p)=>'<style>'+assets[p].replaceAll('url(network-map.png)','url('+image+')')+'</style>').replace(/<script src="([^"]+)"><\\/script>/g,(_,p)=>'<script>'+assets[p].replace(/<\\/script/gi,'<\\\\/script')+'</'+'script>').replace('</head>',()=>bridge+'</head>');document.open();document.write(doc);document.close()})();</script></body></html>`;
await writeFile('计算机网络_完整学习中心.html',output);
