const $ = id => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf"]').content;
function message(text) { $('message').textContent = text; $('message').hidden = !text; }
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(data)});
  const result = await response.json();
  if(!response.ok) throw Error(result.error || `Request failed (${response.status})`);
  return result;
}
function bind(id, fn) { if($(id)) $(id).onclick = async () => {try {message('');await fn();}catch(e){message(e.message);}}; }
bind('login',async()=>{await api('/login',{password:$('password').value});location.reload();});
if($('password')) $('password').onkeydown=e=>{if(e.key==='Enter') $('login').click();};
bind('logout',async()=>{await api('/logout',{});location.reload();});
function makeRow(row={id:'entry.', label:'', answers:['']}) {
  const el = document.createElement('div');el.className='entry';
  el.innerHTML='<div class="entry-head"><input class="entry-id" aria-label="Entry ID"><button class="quiet remove">Remove</button></div><label>Question label<input class="question" placeholder="Type the question here"></label><label>Answer format<select class="kind"><option value="text">One answer / text paragraph</option><option value="multi">Checkboxes — one selected option per line</option></select></label><label>Answer(s)<textarea class="answer" rows="3"></textarea></label>';
  el.querySelector('.entry-id').value=row.id;
  el.querySelector('.question').value=row.label || '';
  el.querySelector('.kind').value=row.answers.length>1?'multi':'text';
  el.querySelector('.answer').value=row.answers.join('\n');
  el.querySelector('.remove').onclick=()=>el.remove();
  $('rows').querySelector('.empty')?.remove();$('rows').append(el);
}
function rows(){return [...document.querySelectorAll('.entry')].map(el=>({id:el.querySelector('.entry-id').value.trim(),label:el.querySelector('.question').value,answers:el.querySelector('.kind').value==='multi'?el.querySelector('.answer').value.split('\n').filter(s=>s.length):[el.querySelector('.answer').value]}));}
function config(){return {version:1,url:$('url').value,prefill:$('prefill').value,notes:$('notes').value,rows:rows(),count:Number($('count').value),confirmation:$('confirmation').value};}
bind('import',async()=>{const d=await api('/api/import',{url:$('url').value,prefill:$('prefill').value});$('rows').replaceChildren();d.rows.forEach(makeRow);message(`Imported ${d.rows.length} fields. Add labels and verify every answer against your form.`);});
bind('add',()=>makeRow());
bind('save',()=>{const u=URL.createObjectURL(new Blob([JSON.stringify(config(),null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='formdesk-config.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);});
if($('load')) $('load').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>2000000)throw Error('File too large.');const d=JSON.parse(await f.text());if(!Array.isArray(d.rows)||d.rows.length>300||d.rows.some(r=>!r||typeof r.id!=='string'||!Array.isArray(r.answers)||r.answers.some(a=>typeof a!=='string')))throw Error('Invalid configuration.');for(const key of ['url','prefill','notes','count','confirmation']) if(d[key]!==undefined)$(key).value=d[key];$('rows').replaceChildren();d.rows.forEach(makeRow);$('owned').checked=false;message('Configuration loaded. Review before running.');}catch(err){message(err.message);}};
async function start(mode){await api('/api/start',{...config(),mode,owned:$('owned').checked});await poll();}
bind('preview',()=>start('preview'));bind('submit',()=>start('submit'));bind('cancel',()=>api('/api/cancel',{}));
async function poll(){if(!$('status'))return;try{const d=await api('/api/status');$('status').textContent=d.status;$('progress').textContent=`${d.completed} / ${d.total} confirmed`;$('bar').max=Math.max(1,d.total);$('bar').value=d.completed;$('logs').textContent=d.logs.map(l=>`${l.time.slice(11,19)}  ${l.message}`).join('\n')||'Your job events will appear here.';for(const id of ['submit','preview'])$(id).disabled=d.status==='running';$('cancel').disabled=d.status!=='running';}catch(e){message(e.message);}}
if($('status')){poll();setInterval(poll,2000);}
