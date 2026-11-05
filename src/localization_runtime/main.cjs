'use strict';
// Installed only by a version-verified bootstrap. Importing this module grants no window trust.
const crypto=require('node:crypto');
const {Store,DEFAULT_LIMITS}=require('./storage.cjs');
const {translateBatch,TranslationError,validTranslation}=require('./providers.cjs');
const CHANNELS=Object.freeze({snapshot:'dragongirl:v1:snapshot',translate:'dragongirl:v1:translate'});
const CONTEXTS=new Set(['toolbar','settings','navigation','menu','button','label']);
const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
function safeSource(text,max=160){
  return typeof text==='string'&&Array.from(text).every(c=>c.codePointAt(0)<0xD800||c.codePointAt(0)>0xDFFF)&&text.length>0&&text.length<=max&&text.trim()===text&&/[A-Za-z]/.test(text)&&!/[\u3400-\u9fff\r\n\x00-\x1f<>`\\/]/.test(text)&&!/(?:https?:|www\.|\b\S+@\S+|\b(?:sk|pk|ghp|gho|xoxb)[_-]|[A-Za-z0-9_-]{24,}|[A-Za-z]:|\b(?:Bearer|password|secret|api[_ -]?key)\s*[:=])/i.test(text);
}
function validateEnvelope(v,limits=DEFAULT_LIMITS){
  if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).sort().join(',')!=='cacheEpoch,candidatesRevision,configRevision,dictionaryRevision,items,version'||v.version!==1||![v.configRevision,v.dictionaryRevision,v.candidatesRevision,v.cacheEpoch].every(n=>Number.isSafeInteger(n)&&n>=0)||!Array.isArray(v.items)||!v.items.length||v.items.length>limits.batchSize)throw new TranslationError('invalid_request');
  const ids=new Set();let length=0;
  for(const item of v.items){
    if(!item||Object.keys(item).sort().join(',')!=='id,safeContextKind,text'||typeof item.id!=='string'||!/^[A-Za-z0-9_-]{1,64}$/.test(item.id)||ids.has(item.id)||!CONTEXTS.has(item.safeContextKind)||!safeSource(item.text,limits.textLength))throw new TranslationError('invalid_request');
    ids.add(item.id);length+=item.text.length;
  }
  if(length>limits.batchCharacters)throw new TranslationError('invalid_request');return v;
}
function versions(state){return {version:1,configRevision:state.config.revision,dictionaryRevision:state.dictionary.revision,candidatesRevision:state.candidates.revision,cacheEpoch:state.config.cacheEpoch};}
function sameBase(request,state){return request.configRevision===state.config.revision&&request.dictionaryRevision===state.dictionary.revision&&request.cacheEpoch===state.config.cacheEpoch;}
function matches(request,state){return sameBase(request,state)&&request.candidatesRevision===state.candidates.revision;}
function createService({store=new Store(),providerTranslate=translateBatch,clock=Date.now,timers={setInterval,clearInterval}}={}){
  const pending=new Map(),controllers=new Set();let fingerprint='',generation=0,active=0,queue=[],requestTimes=[],sessionRequests=0,cooldownUntil=0,authBlocked=false,closed=false,persistenceStatus='';
  async function read(){
    const state=await store.read(clock);
    if(!state.candidates||!Number.isSafeInteger(state.candidates.revision)||!state.candidates.entries||!state.candidates.rejected||!state.candidates.epochs)throw new TranslationError('invalid_storage');
    // Independent additions do not cancel each other. User decisions, expiry and
    // personal/config edits change epochs or revisions and invalidate old work.
    const next=crypto.createHash('sha256').update(JSON.stringify([state.config,state.dictionary,state.candidates.epochs,state.candidates.rejected])).digest('hex');
    if(next!==fingerprint){fingerprint=next;generation++;pending.clear();cooldownUntil=0;authBlocked=false;persistenceStatus='';for(const c of controllers)c.abort();}
    return state;
  }
  async function snapshot(){
    try{const state=await read();const entries=Object.create(null),candidates=Object.create(null),rejected=Object.create(null);
      for(const [source,item] of Object.entries(state.dictionary.entries))entries[source]=item.translation;
      for(const source of Object.keys(state.candidates.rejected))rejected[source]=true;
      for(const [source,item] of Object.entries(state.candidates.entries))if(item.createdAt<=clock()&&item.expiresAt>clock()&&!own(rejected,source)&&!own(entries,source))candidates[source]={translation:item.translation,createdAt:item.createdAt,expiresAt:item.expiresAt,source:'ai'};
      return {...versions(state),enabled:state.config.enabled,entries,candidates,rejected,status:!state.config.enabled?'disabled':authBlocked?'authentication_failed':persistenceStatus||'ready'};
    }catch(_){for(const c of controllers)c.abort();return {version:1,enabled:false,configRevision:0,dictionaryRevision:0,candidatesRevision:0,cacheEpoch:0,entries:{},candidates:{},rejected:{},status:'storage_unavailable'};}
  }
  function pump(){
    while(queue.length && active<queue[0].concurrency){
      const job=queue.shift();active++;
      Promise.resolve().then(job.run).then(job.resolve,job.reject).finally(()=>{active--;pump();});
    }
  }
  function schedule(run,limits){
    if(closed||queue.length>=limits.queueSize)return Promise.reject(new TranslationError('queue_full'));
    return new Promise((resolve,reject)=>{queue.push({run,resolve,reject,concurrency:limits.concurrency});pump();});
  }
  async function translate(request){
    let state;
    try{
      state=await read();validateEnvelope(request,state.config.limits);
      const empty=status=>({...versions(state),status,translations:[]});
      if(closed)return empty('disabled');
      if(!matches(request,state))return empty('stale');
      const epoch=generation;const limits=state.config.limits;const promises=[];const missing=[];
      for(const item of request.items){
        // Persistence is keyed by original source, so one provider generation
        // must serve every context/ID for it. The first request supplies context.
        const key=JSON.stringify([state.config.provider,state.config.providers[state.config.provider].model,item.text]);
        if(own(state.dictionary.entries,item.text)){promises.push(Promise.resolve({id:item.id,text:state.dictionary.entries[item.text].translation,source:'personal',expiresAt:null}));continue;}
        if(own(state.candidates.rejected,item.text))continue;
        const candidate=own(state.candidates.entries,item.text)?state.candidates.entries[item.text]:null;
        // Clock rollback cannot make a future record visible or trigger another
        // paid generation of the same already-persisted candidate.
        if(candidate&&candidate.createdAt>clock())continue;
        if(candidate&&candidate.expiresAt>clock()){promises.push(Promise.resolve({id:item.id,text:candidate.translation,source:'candidate',expiresAt:candidate.expiresAt}));continue;}
        if(!state.config.enabled)continue;
        if(!pending.has(key)){
          let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});
          // The batch task owns settlement; consumers below attach rejection handlers synchronously.
          pending.set(key,promise);missing.push({key,item,resolve,reject,promise});
        }
        promises.push(pending.get(key).then(updated=>updated?{updated:true}:null));
      }
      if(missing.length){
        schedule(async()=>{
          const current=await read();
          if(epoch!==generation||!sameBase(request,current)||!current.config.enabled)throw new TranslationError('stale');
          const now=clock();requestTimes=requestTimes.filter(t=>now-t<60000);
          if(authBlocked)throw new TranslationError('authentication_failed');
          if(now<cooldownUntil||requestTimes.length>=limits.requestsPerMinute||sessionRequests>=limits.sessionRequests)throw new TranslationError('rate_limited');
          sessionRequests++;requestTimes.push(now);
          const controller=new AbortController();controllers.add(controller);
          // A changed GUI file cancels in-flight I/O even without another renderer request.
          let checking=false;
          const watcher=timers.setInterval(()=>{if(!checking){checking=true;read().catch(()=>controller.abort()).finally(()=>{checking=false;});}},250);
          try{
            const inputs=missing.map(({item},i)=>({...item,id:`t${i}`}));
            const output=await providerTranslate(inputs,{provider:current.config.provider,profile:current.config.providers[current.config.provider],timeoutMs:limits.timeoutMs},controller.signal);
            const latest=await read();
            if(controller.signal.aborted||epoch!==generation||!sameBase(request,latest)||!latest.config.enabled)throw new TranslationError('stale');
            const mapped=new Map();
            for(const result of output||[]){const input=inputs.find(i=>i.id===result.id);if(input&&validTranslation(input.text,result.text)&&!mapped.has(result.id))mapped.set(result.id,result.text);}
            const saves=missing.flatMap(({item},i)=>mapped.has(`t${i}`)?[{source:item.text,translation:mapped.get(`t${i}`)}]:[]);
            let saved=[];
            if(saves.length){
              const epochs=Object.fromEntries(saves.map(item=>[item.source,state.candidates.epochs[item.source]||0]));
              let result;
              try{result=await store.saveCandidates(saves,{configRevision:request.configRevision,dictionaryRevision:request.dictionaryRevision,epochs},clock);}
              catch(_){persistenceStatus='save_failed';throw new TranslationError('save_failed');}
              saved=result.saved||[];
              const committed=await read();
              if(controller.signal.aborted||epoch!==generation||!sameBase(request,committed)||!committed.config.enabled)throw new TranslationError('stale');
            }
            // Never expose an unpersisted provider response. The preload fetches
            // the committed snapshot, where normal precedence applies again.
            missing.forEach(({item,resolve})=>resolve(saved.some(row=>row.source===item.text)));
          }catch(error){
            if(error.code==='authentication_failed')authBlocked=true;
            cooldownUntil=Math.max(cooldownUntil,clock()+(error.retryAfterMs||5000));throw error;
          }finally{timers.clearInterval(watcher);controllers.delete(controller);}
        },limits).catch(error=>missing.forEach(({reject})=>reject(error))).finally(()=>missing.forEach(({key,promise})=>{if(pending.get(key)===promise)pending.delete(key);}));
      }
      const output=await Promise.all(promises);
      const latest=await read();
      if(epoch!==generation||!sameBase(request,latest))return empty('stale');
      const updated=output.some(row=>row?.updated);
      return {...versions(state),status:updated?'candidates_updated':!state.config.enabled?'disabled':'ok',translations:updated?[]:output.filter(row=>row?.id)};
    }catch(error){return {...(state?.candidates?versions(state):{version:1,configRevision:0,dictionaryRevision:0,candidatesRevision:0,cacheEpoch:0}),status:error instanceof TranslationError?error.code:'unavailable',translations:[]};}
  }
  let cleaning=false;
  async function cleanup(){if(closed||cleaning)return;cleaning=true;try{await read();}catch(_){for(const c of controllers)c.abort();}finally{cleaning=false;}}
  // Cleanup runs only with this component; no separate resident process is used.
  const cleanupTimer=timers.setInterval(cleanup,60000);cleanupTimer?.unref?.();
  void cleanup();
  function close(){closed=true;timers.clearInterval(cleanupTimer);for(const c of controllers)c.abort();for(const job of queue)job.reject(new TranslationError('cancelled'));queue=[];pending.clear();}
  return {snapshot,translate,close};
}
const installed=new WeakMap();
function installIpc({ipcMain,service=createService()}={}){
  if(!ipcMain||typeof ipcMain.handle!=='function')throw new TranslationError('invalid_ipc');
  if(installed.has(ipcMain))return installed.get(ipcMain);
  const trusted=new Map();let disposed=false,pageEpoch=0;
  function registerTrustedWindow(webContents,exactUrl,guard=()=>true){
    if(disposed||!webContents||typeof exactUrl!=='string'||!exactUrl||exactUrl.length>4096)throw new TranslationError('invalid_window');
    let u;try{u=new URL(exactUrl);}catch(_){throw new TranslationError('invalid_window');}
    if(['http:','data:','javascript:','about:'].includes(u.protocol)||u.username||u.password)throw new TranslationError('invalid_window');
    if(typeof guard!=='function'||guard()!==true)throw new TranslationError('unsafe_window');
    const prefs=webContents.getLastWebPreferences?.();
    if(!prefs||prefs.contextIsolation!==true||prefs.sandbox!==true||prefs.nodeIntegration!==false||webContents.isDestroyed?.())throw new TranslationError('unsafe_window');
    if(pageEpoch>=Number.MAX_SAFE_INTEGER)throw new TranslationError('invalid_window');
    trusted.get(webContents)?.revoke();
    // Re-entering the same URL is a new page lifetime even when no poll saw the
    // intervening unauthorized route. Keep this counter out of user storage.
    const entry={exactUrl,guard,pageEpoch:++pageEpoch,times:[],revoke:null};
    const revoke=()=>{if(trusted.get(webContents)===entry)trusted.delete(webContents);webContents.removeListener?.('did-start-navigation',onNavigate);webContents.removeListener?.('destroyed',revoke);};
    const onNavigate=(_event,_url,isInPlace,isMainFrame)=>{if(isMainFrame!==false)revoke();};
    entry.revoke=revoke;trusted.set(webContents,entry);webContents.on?.('did-start-navigation',onNavigate);webContents.on?.('destroyed',revoke);
    return revoke;
  }
  function authorize(event,expectedEntry){
    const wc=event?.sender,entry=trusted.get(wc);
    if(!entry||(expectedEntry&&entry!==expectedEntry)||wc.isDestroyed?.()||event.senderFrame!==wc.mainFrame||event.senderFrame?.url!==entry.exactUrl||wc.getURL?.()!==entry.exactUrl)throw new TranslationError('unauthorized');
    const prefs=wc.getLastWebPreferences?.();
    if(!prefs||prefs.contextIsolation!==true||prefs.sandbox!==true||prefs.nodeIntegration!==false||entry.guard()!==true){entry.revoke();throw new TranslationError('unauthorized');}
    const now=Date.now();entry.times=entry.times.filter(t=>now-t<1000);if(entry.times.length>=20)throw new TranslationError('ipc_rate_limited');entry.times.push(now);
    return entry;
  }
  const denied=()=>({version:1,status:'unauthorized',translations:[]});
  ipcMain.handle(CHANNELS.snapshot,async(event,request)=>{try{const entry=authorize(event);if(!request||Object.keys(request).join(',')!=='version'||request.version!==1)return denied();const result=await service.snapshot();authorize(event,entry);return {...result,pageEpoch:entry.pageEpoch};}catch(_){return denied();}});
  ipcMain.handle(CHANNELS.translate,async(event,request)=>{try{const entry=authorize(event);const result=await service.translate(request);authorize(event,entry);return result;}catch(_){return denied();}});
  function dispose(){disposed=true;for(const entry of [...trusted.values()])entry.revoke();ipcMain.removeHandler?.(CHANNELS.snapshot);ipcMain.removeHandler?.(CHANNELS.translate);service.close();installed.delete(ipcMain);}
  const api={registerTrustedWindow,dispose,service};installed.set(ipcMain,api);return api;
}
module.exports={CHANNELS,CONTEXTS,safeSource,validateEnvelope,createService,installIpc};
