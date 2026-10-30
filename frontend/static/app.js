const $ = id => document.getElementById(id);
let csrf = '', signedIn = false;
function message(text) { $('message').textContent = text; $('message').hidden = !text; }
$('year').textContent = new Date().getFullYear();
const tabs = ['connect','answers','run'];
let currentTab = 'connect';
function show(tab) {
  currentTab = tab; save();
  document.querySelectorAll('[data-panel]').forEach(p => p.hidden = p.dataset.panel !== tab);
  document.querySelectorAll('#side a').forEach(a => a.classList.toggle('on', a.dataset.tab === tab));
  $('crumb').textContent = {connect:'Connect form',answers:'Answers',run:'Run & progress'}[tab];
  try { history.replaceState(null, '', '#' + tab); } catch(e) {}
}
document.querySelectorAll('#side a').forEach(a => a.onclick = e => { e.preventDefault(); show(a.dataset.tab); });

const KEY = 'formdesk:v1', DEFAULT_CONFIRMATION = 'Your response has been recorded.';
const EMPTY_ROWS = '<div class="empty">Load your pre-filled link to see the questions.</div>';
function snapshot() {
  return {url:$('url').value, prefill:$('prefill').value, notes:$('notes').value, count:$('count').value,
    confirmation:$('confirmation').value, allkind:$('allkind').value, tab:currentTab,
    done:[...document.querySelectorAll('#side a.done')].map(a => a.dataset.tab),
    rows:(r => [...document.querySelectorAll('.entry')].map((el, i) => ({...r[i], options:JSON.parse(el.dataset.options || '[]'), type:el.dataset.type === '' ? undefined : Number(el.dataset.type)})))(rows())};
}
function save() { if(!signedIn) return; try { localStorage.setItem(KEY, JSON.stringify(snapshot())); } catch(e) {} }
function updateCount() { $('rowcount').textContent = document.querySelectorAll('.entry').length || ''; }
function restore() {
  let s; try { s = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch(e) {}
  if(!s || typeof s !== 'object') return null;
  for(const k of ['url','prefill','notes','count','confirmation','allkind']) if(typeof s[k] === 'string') $(k).value = s[k];
  if(Array.isArray(s.rows) && s.rows.length) { $('rows').replaceChildren(); s.rows.forEach(makeRow); }
  (s.done || []).forEach(t => document.querySelector(`[data-tab=${t}]`)?.classList.add('done'));
  updateCount();
  return s.tab;
}
function resetAll() {
  if(!confirm('Clear the links, answers and settings saved in this browser?')) return;
  try { localStorage.removeItem(KEY); } catch(e) {}
  for(const id of ['url','prefill','notes']) $(id).value = '';
  $('count').value = 1; $('confirmation').value = DEFAULT_CONFIRMATION; $('allkind').value = 'text'; $('owned').checked = false;
  $('rows').innerHTML = EMPTY_ROWS;
  document.querySelectorAll('#side a.done').forEach(a => a.classList.remove('done'));
  updateCount(); message(''); show('connect');
}
['input','change'].forEach(ev => document.addEventListener(ev, e => { if(e.target.closest('#app-view')) save(); }));
document.addEventListener('click', e => { if(e.target.closest('#app-view .remove')) setTimeout(() => { updateCount(); save(); }); });
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(data)});
  const result = await response.json();
  if(!response.ok) throw Error(result.error || `Request failed (${response.status})`);
  return result;
}
function bind(id, fn) { if($(id)) $(id).onclick = async () => {try {message('');await fn();}catch(e){message(e.message);}}; }
bind('login',async()=>{await api('/login',{password:$('password').value});location.reload();});
if($('password')) $('password').onkeydown=e=>{if(e.key==='Enter') $('login').click();};
bind('reset',resetAll);
bind('logout',async()=>{await api('/logout',{});location.reload();});
function makeRow(row={id:'entry.', label:'', answers:['']}) {
  const el = document.createElement('div');el.className='entry';
  el.innerHTML='<div class="entry-head"><input class="question" placeholder="Question (optional name for you)"><button class="quiet remove">Remove</button></div><label>How to answer<select class="kind"><option value="text">Same answer every time</option><option value="random">Different each time (random pick from list)</option><option value="subset">Random few ticked (checkboxes)</option><option value="multi">Several selected together (checkboxes)</option></select></label><label><span class="hint-label">Answer</span><textarea class="answer" rows="2"></textarea></label><small class="hint kind-hint"></small><label class="idrow">Entry ID<input class="entry-id" aria-label="Entry ID"></label>';
  el.dataset.options=JSON.stringify(row.options||[]);el.dataset.type=row.type===undefined?'':row.type;
  el.querySelector('.entry-id').value=row.id;
  el.querySelector('.question').value=row.label || '';
  el.querySelector('.kind').value=row.mode==='random'||row.mode==='subset'?row.mode:row.answers.length>1?'multi':'text';
  el.querySelector('.answer').value=row.answers.join('\n');
  const kind=el.querySelector('.kind'),hint=el.querySelector('.kind-hint');
  const note=()=>{hint.textContent={text:'Type one answer.',random:'One option per line. Each response picks one at random.',subset:'One option per line. Each response ticks 1–3 of them at random.',multi:'One option per line. All of them are ticked in every response.'}[kind.value];};
  kind.onchange=note;note();
  el.querySelector('.remove').onclick=()=>el.remove();
  $('rows').querySelector('.empty')?.remove();$('rows').append(el);
}
function rows(){return [...document.querySelectorAll('.entry')].map(el=>({id:el.querySelector('.entry-id').value.trim(),label:el.querySelector('.question').value,mode:['random','subset'].includes(el.querySelector('.kind').value)?el.querySelector('.kind').value:'fixed',answers:el.querySelector('.kind').value!=='text'?el.querySelector('.answer').value.split('\n').filter(s=>s.length):[el.querySelector('.answer').value]}));}
function config(){return {version:1,url:$('url').value,prefill:$('prefill').value,notes:$('notes').value,rows:rows(),count:Number($('count').value),confirmation:$('confirmation').value};}
bind('import',async()=>{const d=await api('/api/import',{url:$('url').value,prefill:$('prefill').value});$('rows').replaceChildren();d.rows.forEach(makeRow);applyAll();updateCount();document.querySelector('[data-tab=connect]').classList.add('done');show('answers');message(`Loaded ${d.rows.length} questions. Check each answer against your form.`);});
function notesOptions(){const out=[];let cur=null;for(const raw of $('notes').value.split('\n')){const line=raw.trim();if(/^\d+\.\s/.test(line)){cur=[];out.push(cur);continue;}if(!cur||!line||line.startsWith('*')||/^\d\s*=/.test(line)||line.length>120)continue;cur.push(line);}return out;}
function applyAll(){const v=$('allkind').value;const opts=notesOptions();document.querySelectorAll('.entry').forEach((el,i)=>{const a=el.querySelector('.answer'),k=el.querySelector('.kind');const lines=()=>a.value.split('\n').filter(s=>s.length);
  if(v==='random'){const known=JSON.parse(el.dataset.options||'[]');const pool=known.length>=2?known:(opts[i]||[]);if(pool.length>=2&&lines().length<2)a.value=pool.join('\n');
    k.value=lines().length<2?'text':(el.dataset.type==='4'?'subset':'random');}
  else k.value=lines().length>1?'multi':'text';
  k.onchange();});}
$('allkind').onchange=applyAll;
bind('toRun',()=>{document.querySelector('[data-tab=answers]').classList.add('done');show('run');});
bind('add',()=>{makeRow();updateCount();save();});
bind('save',()=>{const u=URL.createObjectURL(new Blob([JSON.stringify(config(),null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='formdesk-config.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);});
if($('load')) $('load').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>2000000)throw Error('File too large.');const d=JSON.parse(await f.text());if(!Array.isArray(d.rows)||d.rows.length>300||d.rows.some(r=>!r||typeof r.id!=='string'||!Array.isArray(r.answers)||r.answers.some(a=>typeof a!=='string')))throw Error('Invalid configuration.');for(const key of ['url','prefill','notes','count','confirmation']) if(d[key]!==undefined)$(key).value=d[key];$('rows').replaceChildren();d.rows.forEach(makeRow);$('owned').checked=false;message('Configuration loaded. Review before running.');}catch(err){message(err.message);}};
async function start(mode){
  const thin=rows().filter(r=>(r.mode==='random'||r.mode==='subset')&&r.answers.length<2).length;
  if(thin&&!confirm(`${thin} question(s) are set to "Different each time" but have only one option, so they will repeat the same answer. Continue anyway?`))return;
await api('/api/start',{...config(),mode,owned:$('owned').checked});await poll();}
bind('preview',()=>start('preview'));bind('submit',()=>start('submit'));bind('cancel',()=>api('/api/cancel',{}));
async function poll(){if(!signedIn)return;try{const d=await api('/api/status');$('status').textContent=d.status;$('runbadge').textContent=d.status==='running'?'●':'';$('progress').textContent=`${d.completed} / ${d.total} done`;$('bar').max=Math.max(1,d.total);$('bar').value=d.completed;$('logs').textContent=d.logs.map(l=>`${l.time.slice(11,19)}  ${l.message}`).join('\n')||'Your job events will appear here.';for(const id of ['submit','preview'])$(id).disabled=d.status==='running';$('cancel').disabled=d.status!=='running';}catch(e){message(e.message);}}

(async()=>{
  try {
    const s = await (await fetch('/api/session')).json();
    csrf = s.csrf; signedIn = s.signed_in;
  } catch(e) { message('Cannot reach the server. Try again shortly.'); }
  $('login-view').hidden = signedIn || !csrf;
  $('app-view').hidden = !signedIn;
  $('side').hidden = !signedIn;
  $('reset').hidden = !signedIn;
  if(signedIn) { const saved = restore(); show(tabs.includes(location.hash.slice(1)) ? location.hash.slice(1) : tabs.includes(saved) ? saved : 'connect'); }
  $('logout').hidden = !signedIn;
  if(signedIn){poll();setInterval(poll,2000);}
})();
