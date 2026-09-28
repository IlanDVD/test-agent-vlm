'use strict';
const $ = id => document.getElementById(id);
let token = '', session = null, busy = false, ready = false, timer = null, fingerprint = '';
const storageKey = 'mon-agent-conversation';
const nodes = new Map();
function alerte(message) { $('alerte').textContent = message; $('alerte').hidden = !message; }
async function api(path, data) {
  const response = await fetch(path, {method: data === undefined ? 'GET' : 'POST',
    headers: data === undefined ? {} : {'Content-Type':'application/json','X-Chat-Token':token},
    body: data === undefined ? undefined : JSON.stringify(data)});
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.erreur || 'Le serveur ne répond pas correctement.');
  return payload;
}
function controls() {
  $('question').disabled = !ready || busy;
  $('envoyer').disabled = !ready || busy || !$('question').value.trim();
  $('nouveau').disabled = !ready || busy;
  document.querySelectorAll('[data-question]').forEach(b => b.disabled = !ready || busy);
}
function el(tag, css, text) {const n=document.createElement(tag); if(css)n.className=css;if(text!==undefined)n.textContent=text;return n;}
function richText(target, text) {
  // Ne jamais interpréter le HTML renvoyé par le modèle.
  target.replaceChildren();
  const fragments = text.split(/(\*\*[^*]+\*\*)/g);
  for (const part of fragments) target.append(part.startsWith('**') && part.endsWith('**') ? el('strong','',part.slice(2,-2)) : document.createTextNode(part));
}
function actionLabel(event) {
  if(event.nom==='lister_documents')return 'Liste des documents';
  if(event.nom==='lire_document')return 'Lecture de '+(event.arguments?.nom || 'document');
  return event.nom || 'Action';
}
function render(data) {
  const follow = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 160;
  session=data; busy=data.tours.some(t=>t.statut==='en_cours'); controls();
  $('bienvenue').hidden = data.tours.length>0;
  const signature = JSON.stringify(data)+(busy?Math.floor(Date.now()/1000):'');
  if(signature===fingerprint)return;
  fingerprint=signature;
  for(const turn of data.tours) {
    let node=nodes.get(turn.id);
    if(!node) {
      node=el('article','turn');node.append(el('div','user-message',turn.question));
      const label=el('div','assistant-label');label.append(el('span','avatar','a.'),el('span','','Mon agent'));node.append(label);
      node.answer=el('div','answer');node.progress=el('div','progress');node.progress.append(el('span','spinner'),el('span'));
      node.steps=el('details');node.summary=el('summary');node.list=el('ol');node.steps.append(node.summary,node.list);
      node.append(node.progress,node.answer,node.steps);$('messages').append(node);nodes.set(turn.id,node);
    }
    const events=turn.evenements || [], tools=events.filter(e=>e.type==='outil');
    node.list.replaceChildren();
    tools.forEach(e=>{
      const error=e.resultat?.erreur;
      let label=actionLabel(e)+(error?' — '+error:' — terminé');
      if(e.resultat?.documents)label+=' ('+e.resultat.documents.length+' disponibles)';
      node.list.append(el('li','',label));
    });
    const generated=events.filter(e=>e.type==='diagnostic_modele').reduce((n,e)=>n+(e.eval_count||0),0);
    node.summary.textContent=`${tools.length} action${tools.length>1?'s':''} consultable${tools.length>1?'s':''}`;
    if(generated)node.list.append(el('li','',`${generated.toLocaleString('fr-FR')} tokens générés, réflexion comprise.`));
    node.steps.hidden=!tools.length && !generated;
    node.progress.hidden=turn.statut!=='en_cours';
    node.answer.className=turn.statut==='erreur'?'error-text':'answer';
    if(turn.statut==='en_cours') {
      const last=events.at(-1);
      const phase=last?.type==='outil_demande'?actionLabel(last):`L’agent prépare sa réponse${last?.tour?' · étape '+last.tour:''}…`;
      const seconds=Math.max(0,Math.floor((Date.now()-Date.parse(turn.debut))/1000));
      node.progress.lastChild.textContent=phase+` (${seconds} s)`;
    } else {
      richText(node.answer,turn.statut==='erreur'?turn.erreur:turn.reponse);
      if(node.dataset.status!==turn.statut) $('annonce').textContent=turn.statut==='termine'?'La réponse de votre agent est disponible.':'La réponse a rencontré une erreur.';
    }
    node.dataset.status=turn.statut;
  }
  if(follow)window.scrollTo({top:document.documentElement.scrollHeight,behavior:'instant'});
}
async function nouvelle() {
  alerte('');const data=await api('/api/session',{});
  sessionStorage.setItem(storageKey,data.id);nodes.clear();fingerprint='';$('messages').replaceChildren();render(data);$('question').value='';controls();$('question').focus();
}
async function refresh() {
  if(!session)return;
  try {render(await api('/api/session/'+session.id));}
  catch(error) {ready=false;controls();alerte('Connexion perdue. Vérifiez que le lanceur du chat est ouvert, puis actualisez la page.');}
  if(busy && ready)timer=setTimeout(refresh,1200);
}
$('question').addEventListener('input',controls);
$('question').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!$('envoyer').disabled)$('composer').requestSubmit();}});
document.querySelectorAll('[data-question]').forEach(button=>button.addEventListener('click',()=>{$('question').value=button.dataset.question;controls();$('question').focus();}));
$('nouveau').addEventListener('click',()=>nouvelle().catch(error=>alerte(error.message)));
$('composer').addEventListener('submit',async event=>{
  event.preventDefault();const question=$('question').value.trim();if(!question||busy||!ready)return;
  busy=true;controls();alerte('');clearTimeout(timer);
  try {await api('/api/chat',{session:session.id,question});$('question').value='';await refresh();}
  catch(error){busy=false;controls();alerte(error.message);}
});
async function boot(){
  try {
    const config=await api('/api/bootstrap');token=config.token;
    $('modele').textContent=config.modele+' · Ollama';
    $('connexion').textContent=config.etat.ok?'Ollama disponible':'Ollama indisponible';
    $('connexion').classList.toggle('ready',config.etat.ok);
    $('documents').replaceChildren(...config.documents.map(name=>el('li','',name)));
    ready=true;
    if(!config.etat.ok)alerte(config.etat.message);
    const id=sessionStorage.getItem(storageKey);
    if(id){try{render(await api('/api/session/'+id));}catch{await nouvelle();}}
    else await nouvelle();
    if(!config.etat.ok)alerte(config.etat.message);
    if(busy)refresh();else $('question').focus();
  }catch(error){ready=false;controls();alerte('Impossible de joindre le chat local. '+error.message);}
}
boot();
