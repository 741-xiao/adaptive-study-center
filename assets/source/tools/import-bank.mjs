import {readFile, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
const root=process.argv[2];
const rows=[], docs=[];
for(const [i,num] of [...'一二三四五六'].entries()){
 const file=`第${num}章_填空题与大题完整解析.md`,src=(await readFile(join(root,file),'utf8')).replace(/\r/g,'');
 const blocks=[...src.matchAll(/^(#{1,3}) (.+)$/gm)];let group='';
 for(const [k,h] of blocks.entries()){
  const m=h[2].match(/^(填空|大题)\s*([A-Z]?\d+)\s*(.*)$/);if(!m){group=h[2];continue}
  const [,type,no,title]=m,body=src.slice(h.index+h[0].length,blocks[k+1]?.index??src.length).trim().replace(/(?:\n\s*---\s*)+$/,'').trim();
  const sep=/^\*\*(?:参考答案|答案|答|解)[：:]\*\*/m.exec(body);
  if(!sep){console.error('Unsplit',i+1,type,no,body.slice(0,100));continue}
  const tag=title.match(/^【[^】]+】/)?.[0]||'',stem=[title.slice(tag.length),body.slice(0,sep.index)].map(x=>x.trim()).filter(Boolean).join('\n\n');
  const [a,...ex]=body.slice(sep.index+sep[0].length).split(/^\*\*解析(?:[：:]\*\*|\*\*[：:])/m);
  const id=`${i+1}-${type==='填空'?'f':'w'}-${no}`;if(rows.some(x=>x.id===id))throw Error('duplicate '+id);
  rows.push({id,ch:i+1,type,no,tag,stem:stem.replaceAll('\\_','_'),a:a.trim(),why:ex.join('\n').trim(),group});
 }
 docs.push({file,src});
}
await writeFile('exam-data.js','globalThis.examBank='+JSON.stringify(rows)+';\n');
await writeFile('course-docs.js','globalThis.courseDocs='+JSON.stringify(docs)+';\n');
for(const ch of [1,2,3,4,5,6]) console.log(ch,...['填空','大题'].map(t=>rows.filter(x=>x.type===t&&x.ch===ch).length));
