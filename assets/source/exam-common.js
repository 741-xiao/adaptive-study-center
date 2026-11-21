'use strict';
globalThis.Study=(()=>{
 const e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const md=s=>{const lines=String(s||'').split('\n');let out='',table=false;const inline=x=>e(x).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>');for(const line of lines){if(/^\s*\|.*\|\s*$/.test(line)){if(!table){out+='<div class="scrolltable"><table>';table=true}if(!/^\s*\|[\s:|\-]+\|\s*$/.test(line))out+='<tr>'+line.trim().slice(1,-1).split('|').map(c=>`<td>${inline(c.trim())}</td>`).join('')+'</tr>';continue}if(table){out+='</table></div>';table=false}if(line.trim())out+=`<p>${inline(line)}</p>`}return out+(table?'</table></div>':'')};
 const cache={},get=(k,f={})=>{try{return JSON.parse(studyStore.getItem('cn3:'+k))??cache[k]??f}catch{return cache[k]??f}},set=(k,v)=>{cache[k]=v;try{studyStore.setItem('cn3:'+k,JSON.stringify(v))}catch{let n=document.getElementById('saveWarn');if(!n){n=document.createElement('p');n.id='saveWarn';document.body.prepend(n)}n.textContent='存储不可用；本轮记录仅在当前页面保留。'}};
 const pages={'填空':'填空题.html','大题':'大题.html'},link=x=>pages[x.type]+'?id='+encodeURIComponent(x.id),norm=s=>s.normalize('NFKC').toLowerCase().replace(/\s|[。；;、，,.$*`]/g,'');
 const sample=(arr,n)=>{const copy=[...arr];for(let i=0;i<Math.min(n,copy.length);i++){const j=i+Math.floor(Math.random()*(copy.length-i));[copy[i],copy[j]]=[copy[j],copy[i]]}return copy.slice(0,n)};
 const download=(name,text,type='text/plain')=>{const u=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};
 return {e,md,get,set,pages,link,norm,sample,download};})();
