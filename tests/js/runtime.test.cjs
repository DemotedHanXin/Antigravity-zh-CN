'use strict';
const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs/promises');const os=require('node:os');const path=require('node:path');const {EventEmitter}=require('node:events');
const P=require('../../src/localization_runtime/providers.cjs');const S=require('../credential_fixture.cjs');const M=require('../../src/localization_runtime/main.cjs');const {probe}=require('../../src/localization_runtime/probe.cjs');
const items=[{id:'one',text:'Open settings',safeContextKind:'settings'}];
const profile={baseUrl:'https://api.example.com/v1',apiKey:'fake-test-key',model:'test-model'};
const translated=JSON.stringify([{id:'one',text:'打开设置'}]);
const response={openai:{status:'completed',output:[{type:'message',content:[{type:'output_text',text:translated}]}]},gemini:{candidates:[{finishReason:'STOP',content:{parts:[{text:translated}]}}]},claude:{stop_reason:'end_turn',content:[{type:'text',text:translated}]},compatible:{choices:[{finish_reason:'stop',message:{content:translated}}]}};
for(const provider of P.PROVIDERS)test(`native contract ${provider}`,async()=>{
 let captured;const output=await P.translateBatch(items,{provider,profile,transport:async req=>{captured=req;return {status:200,body:response[provider]};}});
 assert.deepEqual(output,[{id:'one',text:'打开设置'}]);assert.equal(captured.body.model,provider==='gemini'?undefined:'test-model');
 assert.match(captured.url,new RegExp({openai:'/responses$',gemini:'/models/test-model:generateContent$',claude:'/messages$',compatible:'/chat/completions$'}[provider]));
 if(provider==='openai')assert.equal(captured.body.store,false);
 if(provider==='claude'){assert.equal(captured.headers['anthropic-version'],'2023-06-01');assert.equal(captured.headers['x-api-key'],profile.apiKey);}
 if(provider==='gemini')assert.equal(captured.headers['x-goog-api-key'],profile.apiKey);
 assert.equal(new URL(captured.url).search,'');
});
test('endpoint rejects HTTP, credentials, localhost, private and query',()=>{for(const baseUrl of ['http://api.example.com','https://a:b@api.example.com','https://127.0.0.1','https://10.1.2.3','https://localhost','https://api.example.com?a=b','https://api.example.com/#key','https://api.example.com\\x'])assert.throws(()=>P.endpoint('openai',{...profile,baseUrl}),P.TranslationError);});
test('empty profile never reaches transport',async()=>{let calls=0;await assert.rejects(P.translateBatch(items,{provider:'openai',profile:{...profile,apiKey:''},transport:()=>calls++}),{code:'invalid_configuration'});assert.equal(calls,0);});
test('redirect response is never followed',async()=>{await assert.rejects(P.translateBatch(items,{provider:'openai',profile,transport:async()=>({status:302,headers:{location:'https://evil.example'}})}),{code:'provider_rejected'});});
test('auth and rate limit errors are sanitized',async()=>{for(const status of [401,403,429,500])await assert.rejects(P.translateBatch(items,{provider:'openai',profile,transport:async()=>({status,headers:{'retry-after':'10'},body:{error:'secret'}})}),e=>!e.message.includes('secret')&&e.code===(status<429?'authentication_failed':status===429?'rate_limited':'provider_unavailable'));});
test('timeout bounds even a non-cooperative test transport',async()=>{await assert.rejects(P.translateBatch(items,{provider:'openai',profile,timeoutMs:5,transport:()=>new Promise(()=>{})}),{code:'timeout'});});
test('pre-aborted request cannot hit transport',async()=>{const c=new AbortController();c.abort();let calls=0;await assert.rejects(P.translateBatch(items,{provider:'openai',profile,transport:()=>calls++},c.signal),{code:'cancelled'});assert.equal(calls,0);});
test('strict batch IDs reject duplicate extra missing and fenced JSON',()=>{for(const s of ['[]','[{"id":"x","text":"设置"}]','```json\n[]\n```','[{"id":"one","text":"设置","extra":1}]'])assert.throws(()=>P.parseTranslations(s,items),P.TranslationError);});
test('invalid individual output is dropped, valid sibling survives',()=>{const source=[...items,{id:'two',text:'Delete {name}',safeContextKind:'button'}];assert.deepEqual(P.parseTranslations(JSON.stringify([{id:'one',text:'打开设置'},{id:'two',text:'删除'}]),source),[{id:'one',text:'打开设置'}]);});
test('plain Chinese and matching placeholders only',()=>{for(const value of ['','Settings','<b>设置</b>','**设置**','设置\n解释','设置 `a`'])assert.equal(P.validTranslation('Settings',value),false);assert.equal(P.validTranslation('Delete {name}','删除 {name}'),true);});
async function tempStore(t){const dir=await fs.mkdtemp(path.join(os.tmpdir(),'dragongirl-js-'));t.after(()=>fs.rm(dir,{recursive:true,force:true}));return new S.Store(dir);}
async function writeState(store,config,dictionary=S.defaultDictionary()){await S.atomicWrite(path.join(store.directory,'config.json'),config);await S.atomicWrite(path.join(store.directory,'personal-dictionary.json'),dictionary);}
function enabledConfig(){const config=S.defaultConfig();config.enabled=true;config.revision=1;config.providers.openai=profile;return config;}
test('missing store reads disabled without creating path',async(t)=>{const store=await tempStore(t);const nonexistent=new S.Store(path.join(store.directory,'missing'));assert.equal((await nonexistent.read()).config.enabled,false);await assert.rejects(fs.stat(nonexistent.directory),{code:'ENOENT'});});
test('corrupt files preserved',async(t)=>{const store=await tempStore(t);const f=path.join(store.directory,'config.json');await fs.writeFile(f,'{broken');await assert.rejects(store.read());assert.equal(await fs.readFile(f,'utf8'),'{broken');});
test('symlink storage rejected',async(t)=>{
 const store=await tempStore(t),f=path.join(store.directory,'config.json');
 await fs.writeFile(path.join(store.directory,'other'),'{}');
 try { await fs.symlink('other',f); }
 catch(error) {
  if(process.platform==='win32'&&error.code==='EPERM') { t.skip('Windows symlink privilege unavailable'); return; }
  throw error;
 }
 await assert.rejects(store.read());
});
test('new AI results enter candidates without changing personal entries or extending expiry',async(t)=>{
 const store=await tempStore(t),config=enabledConfig(),dictionary=S.defaultDictionary();dictionary.entries.Save={translation:'保存',source:'manual',updatedAt:'now',context:'ui'};dictionary.tombstones.Delete=0;
 await writeState(store,config,dictionary);const now=1000,state=await store.read(now),guard={configRevision:state.config.revision,dictionaryRevision:0,epochs:{Save:0,Delete:0,'New label':0}};
 assert.equal((await store.saveCandidates([{source:'New label',translation:'新标签'}],{...guard,dictionaryRevision:9},now)).saved.length,0);
 const saved=await store.saveCandidates([{source:'Save',translation:'储存'},{source:'Delete',translation:'删除'},{source:'New label',translation:'新标签'}],guard,now);
 assert.deepEqual(saved.saved.map(row=>row.source),['Delete','New label']);
 await store.saveCandidates([{source:'New label',translation:'改变译文'}],guard,now+1000);
 const data=await store.read(now+1000);assert.equal(data.dictionary.entries.Save.translation,'保存');assert.equal(data.dictionary.entries.Delete,undefined);assert.equal(data.dictionary.entries['New label'],undefined);assert.equal(data.dictionary.revision,0);
 assert.equal(data.candidates.entries['New label'].translation,'新标签');assert.equal(data.candidates.entries['New label'].expiresAt,now+604800000);
});
test('lock timeout does not steal existing lock',async(t)=>{const store=await tempStore(t);await fs.mkdir(path.join(store.directory,'.translation.lock'));await assert.rejects(store.withLock(()=>{}, {timeoutMs:30}),{code:'storage_locked'});assert.ok((await fs.stat(path.join(store.directory,'.translation.lock'))).isDirectory());});
test('dictionary reserved keys, conflicts and future schema rejected',()=>{for(const data of [JSON.parse('{"schemaVersion":2,"revision":0,"entries":{"__proto__":{"translation":"测试","source":"manual","context":"ui","updatedAt":"now"}},"tombstones":{}}'),{...S.defaultDictionary(),schemaVersion:3}])assert.throws(()=>S.validateDictionary(data));});
function memoryStore(){let state={config:enabledConfig(),dictionary:S.defaultDictionary(),candidates:S.defaultCandidates()};return {
 read:async(now=Date.now())=>{if(typeof now==='function')now=now();for(const [source,item] of Object.entries(state.candidates.entries))if(now>=item.expiresAt){delete state.candidates.entries[source];state.candidates.epochs[source]=(state.candidates.epochs[source]||0)+1;state.candidates.revision++;}return structuredClone(state);},
 saveCandidates:async(items,guard,now=Date.now())=>{if(typeof now==='function')now=now();const saved=[];if(!state.config.enabled)return {saved,candidatesRevision:state.candidates.revision,status:'disabled'};
 if(guard.configRevision!==state.config.revision||guard.dictionaryRevision!==state.dictionary.revision)return {saved,candidatesRevision:state.candidates.revision,status:'stale'};
 for(const {source,translation} of items){if(guard.epochs[source]!== (state.candidates.epochs[source]||0)||Object.hasOwn(state.candidates.rejected,source)||Object.hasOwn(state.dictionary.entries,source))continue;
 if(!Object.hasOwn(state.candidates.entries,source)){state.candidates.entries[source]={translation,createdAt:now,expiresAt:now+604800000,context:'ui'};state.candidates.revision++;}saved.push({source,...state.candidates.entries[source]});}
 return {saved,candidatesRevision:state.candidates.revision,status:'ok'};},set:update=>{update(state);},get:()=>state};}
function envelope(state,override={}){return {version:1,configRevision:state.config.revision,dictionaryRevision:state.dictionary.revision,candidatesRevision:state.candidates.revision,cacheEpoch:state.config.cacheEpoch,items,...override};}
function fakeProvider(list){return Promise.resolve(list.map(i=>({id:i.id,text:'打开设置'})));}
test('disabled service never invokes provider and still sends personal dictionary',async()=>{const store=memoryStore();store.set(s=>{s.config.enabled=false;s.dictionary.entries.Save={translation:'保存'};});let calls=0;const service=M.createService({store,providerTranslate:()=>calls++});assert.equal((await service.translate(envelope(store.get()))).status,'disabled');assert.equal((await service.snapshot()).entries.Save,'保存');assert.equal(calls,0);service.close();});
test('snapshot excludes credentials and profiles',async()=>{const service=M.createService({store:memoryStore()});const snap=await service.snapshot();assert.ok(!JSON.stringify(snap).includes('fake-test-key'));assert.equal(snap.providers,undefined);service.close();});
test('safe candidates and envelope limits',()=>{for(const text of ['hello\nworld','https://example.com','/home/user/file','abc@example.com','sk_secretvalue','1234','中文','C:\\code','a'.repeat(161)])assert.equal(M.safeSource(text),false);assert.throws(()=>M.validateEnvelope({...envelope(memoryStore().get()),url:'https://evil.example'}));});
test('deduplicates provider requests and reuses committed candidates',async()=>{let calls=0;const store=memoryStore(),service=M.createService({store,providerTranslate:async list=>{calls++;await new Promise(r=>setTimeout(r,5));return fakeProvider(list);}});const req=envelope(store.get());const [a,b]=await Promise.all([service.translate(req),service.translate({...req,items:[{...items[0],id:'different'}]})]);assert.equal(calls,1);assert.equal(a.status,'candidates_updated');assert.equal(b.status,'candidates_updated');assert.deepEqual(a.translations,[]);assert.deepEqual(b.translations,[]);const reused=await service.translate(envelope(store.get()));assert.equal(reused.translations[0].source,'candidate');assert.equal(reused.translations[0].text,'打开设置');assert.equal(calls,1);service.close();});
test('same source in different contexts persists once and reuses stable expiry for every ID',async(t)=>{
 let now=1000;const store=await tempStore(t);await writeState(store,enabledConfig());const received=[];
 const service=M.createService({store,clock:()=>now,providerTranslate:async list=>{received.push(list);return fakeProvider(list);}});t.after(()=>service.close());
 const repeated=[{id:'button',text:'Open settings',safeContextKind:'button'},{id:'toolbar',text:'Open settings',safeContextKind:'toolbar'}];
 const initial=await store.read(now),result=await service.translate(envelope(initial,{items:repeated}));
 assert.equal(result.status,'candidates_updated');assert.deepEqual(result.translations,[]);assert.equal(received.length,1);
 assert.equal(received[0].length,1);assert.equal(received[0][0].safeContextKind,'button');
 const saved=await store.read(now);assert.deepEqual(Object.keys(saved.candidates.entries),['Open settings']);
 const expiresAt=saved.candidates.entries['Open settings'].expiresAt;now=2000;
 const reused=await service.translate(envelope(saved,{items:repeated}));
 assert.deepEqual(reused.translations.map(row=>row.id),['button','toolbar']);assert.ok(reused.translations.every(row=>row.expiresAt===expiresAt));
 assert.equal((await service.snapshot()).candidates['Open settings'].createdAt,1000);assert.equal(received.length,1);
});
test('concurrent requests share generation for the same source across contexts',async(t)=>{
 const store=memoryStore();const releases=[];let calls=0;
 const service=M.createService({store,providerTranslate:list=>{calls++;return new Promise(resolve=>{releases.push(()=>resolve(list.map(row=>({id:row.id,text:'打开设置'}))));});}});t.after(()=>service.close());
 const first=service.translate(envelope(store.get(),{items:[{id:'button',text:'Open settings',safeContextKind:'button'}]}));
 const second=service.translate(envelope(store.get(),{items:[{id:'toolbar',text:'Open settings',safeContextKind:'toolbar'}]}));
 while(!releases.length)await new Promise(resolve=>setImmediate(resolve));releases.forEach(release=>release());
 const results=await Promise.all([first,second]);assert.equal(calls,1);assert.ok(results.every(result=>result.status==='candidates_updated'&&result.translations.length===0));
 assert.deepEqual(Object.keys(store.get().candidates.entries),['Open settings']);assert.equal(calls,1);
});
test('rejects stale request before network',async()=>{let calls=0;const store=memoryStore(),service=M.createService({store,providerTranslate:()=>calls++});assert.equal((await service.translate(envelope(store.get(),{configRevision:0}))).status,'stale');assert.equal(calls,0);service.close();});
test('in-flight config change discards result',async()=>{let resolve;const store=memoryStore(),service=M.createService({store,providerTranslate:list=>new Promise(r=>{resolve=()=>r(list.map(i=>({id:i.id,text:'打开设置'})));})});const task=service.translate(envelope(store.get()));while(!resolve)await new Promise(r=>setImmediate(r));store.set(s=>{s.config.enabled=false;s.config.revision++;});resolve();assert.equal((await task).translations.length,0);service.close();});
test('in-flight dictionary delete discards result',async()=>{let resolve;const store=memoryStore(),service=M.createService({store,providerTranslate:list=>new Promise(r=>{resolve=()=>r(list.map(i=>({id:i.id,text:'打开设置'})));})});const task=service.translate(envelope(store.get()));while(!resolve)await new Promise(r=>setImmediate(r));store.set(s=>{s.dictionary.revision++;s.dictionary.tombstones['Open settings']=1;});resolve();assert.equal((await task).translations.length,0);service.close();});
test('session cap and auth circuit bound requests',async()=>{let calls=0;const store=memoryStore();store.set(s=>s.config.limits.sessionRequests=1);const service=M.createService({store,providerTranslate:list=>{calls++;return fakeProvider(list);}});await service.translate(envelope(store.get()));const second=await service.translate(envelope(store.get(),{items:[{id:'two',text:'Open preferences',safeContextKind:'settings'}]}));assert.equal(second.status,'rate_limited');assert.equal(calls,1);service.close();});
function ipcFixture(){const handlers=new Map();const ipcMain={handle:(n,f)=>handlers.set(n,f),removeHandler:n=>handlers.delete(n)};const wc=new EventEmitter();wc.mainFrame={url:'app://ui/index.html'};wc.getURL=()=>wc.mainFrame.url;wc.isDestroyed=()=>false;wc.getLastWebPreferences=()=>({contextIsolation:true,sandbox:true,nodeIntegration:false});return {handlers,ipcMain,wc,event:{sender:wc,senderFrame:wc.mainFrame}};}
test('IPC unregistered windows and subframes denied',async()=>{const f=ipcFixture(),service=M.createService({store:memoryStore()}),ipc=M.installIpc({ipcMain:f.ipcMain,service});const snapshot=f.handlers.get(M.CHANNELS.snapshot);assert.equal((await snapshot(f.event,{version:1})).status,'unauthorized');ipc.registerTrustedWindow(f.wc,f.wc.getURL());assert.equal((await snapshot(f.event,{version:1})).enabled,true);assert.equal((await snapshot({...f.event,senderFrame:{url:f.wc.getURL()}},{version:1})).status,'unauthorized');ipc.dispose();assert.equal(f.handlers.size,0);});
test('navigation revokes trust even same URL',async()=>{const f=ipcFixture(),ipc=M.installIpc({ipcMain:f.ipcMain,service:M.createService({store:memoryStore()})});ipc.registerTrustedWindow(f.wc,f.wc.getURL());f.wc.emit('did-start-navigation',{},f.wc.getURL(),false,true);assert.equal((await f.handlers.get(M.CHANNELS.snapshot)(f.event,{version:1})).status,'unauthorized');ipc.dispose();});
test('returning to the same URL publishes a new page epoch without changing dictionary or configuration', async () => {
 const f=ipcFixture(),service=M.createService({store:memoryStore()}),ipc=M.installIpc({ipcMain:f.ipcMain,service});
 const snapshot=()=>f.handlers.get(M.CHANNELS.snapshot)(f.event,{version:1});
 try {
  ipc.registerTrustedWindow(f.wc,f.wc.getURL());
  const before=await snapshot();
  assert.ok(Number.isSafeInteger(before.pageEpoch)&&before.pageEpoch>0);
  assert.equal((await snapshot()).pageEpoch,before.pageEpoch);
  f.wc.emit('did-start-navigation',{},f.wc.getURL()+'?settingsOpen=true',true,true);
  const denied=await snapshot();
  assert.equal(denied.status,'unauthorized');assert.equal(denied.pageEpoch,undefined);
  ipc.registerTrustedWindow(f.wc,f.wc.getURL());
  const after=await snapshot();
  assert.ok(after.pageEpoch>before.pageEpoch);
  for(const field of ['configRevision','dictionaryRevision','cacheEpoch','enabled','entries']) assert.deepEqual(after[field],before[field]);
  assert.equal((await service.snapshot()).pageEpoch,undefined);
 } finally { ipc.dispose(); }
});
test('unsafe preferences rejected; installation idempotent',()=>{const f=ipcFixture(),ipc=M.installIpc({ipcMain:f.ipcMain,service:M.createService({store:memoryStore()})});assert.equal(M.installIpc({ipcMain:f.ipcMain}),ipc);f.wc.getLastWebPreferences=()=>({contextIsolation:false,sandbox:true,nodeIntegration:false});assert.throws(()=>ipc.registerTrustedWindow(f.wc,f.wc.getURL()),{code:'unsafe_window'});ipc.dispose();});
test('probe uses only fixed text and returns sanitized status',async()=>{let received;assert.deepEqual(await probe({store:memoryStore(),translate:async list=>{received=list;return [{id:'probe',text:'打开设置'}];}}),{ok:true,status:'connected'});assert.equal(received[0].text,'Open settings');assert.deepEqual(await probe({store:memoryStore(),translate:()=>{throw new Error('sensitive');}}),{ok:false,status:'unavailable'});});
test('probe revision mismatch makes zero network calls',async()=>{let calls=0;const result=await probe({store:memoryStore(),expectedRevision:99,translate:()=>calls++});assert.deepEqual(result,{ok:false,status:'configuration_changed'});assert.equal(calls,0);});
test('external cancellation settles non-cooperative transport promptly',async()=>{const c=new AbortController();const work=P.translateBatch(items,{provider:'openai',profile,transport:()=>new Promise(()=>{}),timeoutMs:10000},c.signal);c.abort();await assert.rejects(work,{code:'cancelled'});});
test('public address classifier rejects private and reserved IPv6',()=>{for(const a of ['127.0.0.1','169.254.169.254','10.0.0.1','172.16.1.1','192.168.2.1','100.64.0.1','::1','::ffff:127.0.0.1','fd00::1','fe80::1','2001:db8::1','2002:7f00:1::'])assert.equal(P.isPublicAddress(a),false,a);assert.equal(P.isPublicAddress('2606:4700:4700::1111'),true);});
test('schema rejects unsafe larger limits and credential fields',()=>{for(const modify of [c=>c.limits.concurrency=3,c=>c.providers.extra={},c=>c.limits.extra=1,c=>c.providers.openai.apiKey='a'.repeat(4097),c=>c.providers.openai.model='a\x01',c=>c.enabled=true]){const c=S.defaultConfig();modify(c);assert.throws(()=>S.validateConfig(c));}});
test('auth circuit prevents repeat charge until configuration changes',async()=>{let calls=0;const store=memoryStore(),service=M.createService({store,providerTranslate:()=>{calls++;throw new P.TranslationError('authentication_failed');}});assert.equal((await service.translate(envelope(store.get()))).status,'authentication_failed');assert.equal((await service.translate(envelope(store.get()))).status,'authentication_failed');assert.equal(calls,1);store.set(s=>s.config.revision++);await service.translate(envelope(store.get()));assert.equal(calls,2);service.close();});
test('bounded concurrency and queue',async()=>{const pending=[];let running=0,max=0;const store=memoryStore();store.set(s=>s.config.limits.queueSize=1);const service=M.createService({store,providerTranslate:list=>new Promise(resolve=>{running++;max=Math.max(max,running);pending.push(()=>{running--;resolve(list.map(i=>({id:i.id,text:'打开设置'})));});})});
 const req=n=>envelope(store.get(),{items:[{id:`n${n}`,text:`Open setting ${n}`,safeContextKind:'settings'}]});
 const a=service.translate(req(1)),b=service.translate(req(2));while(pending.length<2)await new Promise(r=>setImmediate(r));const c=service.translate(req(3));await new Promise(r=>setImmediate(r));const d=await service.translate(req(4));assert.equal(d.status,'queue_full');pending.shift()();await new Promise(r=>setImmediate(r));while(pending.length)pending.shift()();await Promise.all([a,b,c]);assert.ok(max<=2);service.close();
});
test('revoked window cannot receive an in-flight response',async()=>{const f=ipcFixture();let done;const service={snapshot:()=>new Promise(r=>done=r),translate:()=>{},close:()=>{}};const ipc=M.installIpc({ipcMain:f.ipcMain,service});ipc.registerTrustedWindow(f.wc,f.wc.getURL());const pending=f.handlers.get(M.CHANNELS.snapshot)(f.event,{version:1});f.wc.emit('did-start-navigation',{},f.wc.getURL(),false,true);done({version:1,entries:{private:'词典'}});assert.equal((await pending).status,'unauthorized');ipc.dispose();});

test('same-URL re-registration cannot receive the previous navigation response', async () => {
 const f=ipcFixture();let done;
 const service={snapshot:()=>new Promise(resolve=>done=resolve),translate:()=>{},close:()=>{}};
 const ipc=M.installIpc({ipcMain:f.ipcMain,service});
 const oldRevoke=ipc.registerTrustedWindow(f.wc,f.wc.getURL());
 const pending=f.handlers.get(M.CHANNELS.snapshot)(f.event,{version:1});
 f.wc.emit('did-start-navigation',{},f.wc.getURL(),false,true);
 ipc.registerTrustedWindow(f.wc,f.wc.getURL());
 oldRevoke(); // A stale revoke handle must not delete the new registration.
 done({version:1,entries:{private:'词典'}});
 assert.equal((await pending).status,'unauthorized');
 const fresh=f.handlers.get(M.CHANNELS.snapshot)(f.event,{version:1});
 done({version:1,entries:{}});assert.deepEqual(await fresh,{version:1,entries:{},pageEpoch:2});
 ipc.dispose();
});

test('service lifetime guard is checked before work and after asynchronous completion', async () => {
 const f=ipcFixture();let alive=true,calls=0,done;
 const service={snapshot:()=>{calls++;return new Promise(resolve=>done=resolve);},translate:()=>{},close:()=>{}};
 const ipc=M.installIpc({ipcMain:f.ipcMain,service});
 assert.throws(()=>ipc.registerTrustedWindow(f.wc,f.wc.getURL(),()=>false),{code:'unsafe_window'});
 ipc.registerTrustedWindow(f.wc,f.wc.getURL(),()=>alive);
 const pending=f.handlers.get(M.CHANNELS.snapshot)(f.event,{version:1});alive=false;done({version:1,entries:{}});
 assert.equal((await pending).status,'unauthorized');
 assert.equal((await f.handlers.get(M.CHANNELS.snapshot)(f.event,{version:1})).status,'unauthorized');
 assert.equal(calls,1);ipc.dispose();
});
test('exact pretty UTF-8 write limit preserves existing original',async(t)=>{const store=await tempStore(t);const target=path.join(store.directory,'personal-dictionary.json');const original=S.defaultDictionary();await S.atomicWrite(target,original);const before=await fs.readFile(target,'utf8');const data=S.defaultDictionary();for(let i=0;i<10000;i++)data.entries[`Source ${i}`]={translation:'中'.repeat(95),source:'ai',updatedAt:'2026-10-26T00:00:00.000Z',context:'ui'};assert.ok(Buffer.byteLength(JSON.stringify(data))<4*1024*1024);assert.ok(Buffer.byteLength(JSON.stringify(data,null,2))>4*1024*1024);await assert.rejects(S.atomicWrite(target,data),{code:'storage_too_large'});assert.equal(await fs.readFile(target,'utf8'),before);assert.deepEqual((await store.read()).dictionary,original);assert.deepEqual((await fs.readdir(store.directory)).sort(),['personal-dictionary.json']);});
test('unpaired Unicode surrogates rejected in config and dictionary',()=>{const c=S.defaultConfig();c.providers.openai.apiKey='x\ud800';assert.throws(()=>S.validateConfig(c));const d=S.defaultDictionary();d.entries.Label={translation:'中\ud800',source:'manual',updatedAt:'now',context:'ui'};assert.throws(()=>S.validateDictionary(d));});
test('failed candidate persistence never exposes transient translation and sanitizes status',async()=>{const store=memoryStore();store.saveCandidates=async()=>{throw new Error('secret path');};const service=M.createService({store,providerTranslate:fakeProvider});const result=await service.translate(envelope(store.get()));assert.equal(result.translations.length,0);assert.equal(result.status,'save_failed');const snapshot=await service.snapshot();assert.equal(snapshot.status,'save_failed');assert.ok(!JSON.stringify(snapshot).includes('secret'));service.close();});

test('candidate snapshots remain reusable with AI disabled and disclose no configuration secrets',async()=>{
 let now=1000,calls=0;const store=memoryStore(),service=M.createService({store,clock:()=>now,providerTranslate:list=>{calls++;return fakeProvider(list);}});
 await service.translate(envelope(store.get()));const first=await service.snapshot();assert.equal(first.candidates['Open settings'].source,'ai');
 assert.equal(first.candidates['Open settings'].createdAt,1000);assert.equal(first.candidates['Open settings'].expiresAt,604801000);
 now+=1000;store.set(s=>{s.config.enabled=false;s.config.revision++;});
 const snap=await service.snapshot(),result=await service.translate(envelope(store.get()));
 assert.equal(snap.enabled,false);assert.deepEqual(snap.candidates,first.candidates);assert.equal(result.translations[0].expiresAt,604801000);assert.equal(calls,1);
 assert.ok(!JSON.stringify(snap).includes('fake-test-key'));assert.equal(snap.providers,undefined);service.close();
});
test('candidate expiry uses first generation time and permits a fresh request after cleanup',async()=>{
 let now=1000,calls=0;const store=memoryStore(),service=M.createService({store,clock:()=>now,providerTranslate:list=>{calls++;return fakeProvider(list);}});
 await service.translate(envelope(store.get()));now=604800999;await service.translate(envelope(store.get()));assert.equal(calls,1);
 const old=envelope(store.get());now=604801000;assert.equal((await service.translate(old)).status,'stale');
 const expired=await service.snapshot();assert.deepEqual({...expired.candidates},{});
 assert.equal((await service.translate(envelope(store.get()))).status,'candidates_updated');assert.equal(calls,2);
 assert.equal(store.get().candidates.entries['Open settings'].createdAt,now);service.close();
});
test('reject suppresses AI until explicit unblock; deletion tombstones alone do not suppress it',async()=>{
 let calls=0;const store=memoryStore();store.set(s=>{s.candidates.rejected['Open settings']={rejectedAt:1000};s.candidates.epochs['Open settings']=1;s.candidates.revision++;s.dictionary.tombstones['Open settings']=0;});
 const service=M.createService({store,providerTranslate:list=>{calls++;return fakeProvider(list);}});
 assert.equal((await service.snapshot()).rejected['Open settings'],true);await service.translate(envelope(store.get()));assert.equal(calls,0);
 store.set(s=>{delete s.candidates.rejected['Open settings'];s.candidates.epochs['Open settings']++;s.candidates.revision++;});
 assert.equal((await service.translate(envelope(store.get()))).status,'candidates_updated');assert.equal(calls,1);service.close();
});
test('candidate rejection, expiry and manual changes invalidate inflight results before persistence',async()=>{
 for(const change of [s=>{s.candidates.rejected['Open settings']={rejectedAt:1000};},s=>{},s=>{s.dictionary.entries['Open settings']={translation:'手工设置'};s.dictionary.revision++;}]){
  let resolve,saves=0;const store=memoryStore(),save=store.saveCandidates;store.saveCandidates=(...args)=>{saves++;return save(...args);};
  const service=M.createService({store,providerTranslate:list=>new Promise(done=>{resolve=()=>done(list.map(i=>({id:i.id,text:'打开设置'})));})});
  const pending=service.translate(envelope(store.get()));while(!resolve)await new Promise(r=>setImmediate(r));
  store.set(s=>{change(s);s.candidates.epochs['Open settings']=(s.candidates.epochs['Open settings']||0)+1;s.candidates.revision++;});
  resolve();assert.equal((await pending).translations.length,0);assert.equal(saves,0);assert.equal(store.get().candidates.entries['Open settings'],undefined);service.close();
 }
});
test('independent concurrent candidate additions both persist without invalidating each other',async()=>{
 const store=memoryStore(),resolvers=[];const service=M.createService({store,providerTranslate:list=>new Promise(resolve=>resolvers.push(()=>resolve(list.map(i=>({id:i.id,text:'打开设置'})))))});
 const one=service.translate(envelope(store.get())),two=service.translate(envelope(store.get(),{items:[{id:'two',text:'Open preferences',safeContextKind:'settings'}]}));
 while(resolvers.length<2)await new Promise(r=>setImmediate(r));resolvers[0]();assert.equal((await one).status,'candidates_updated');resolvers[1]();assert.equal((await two).status,'candidates_updated');
 assert.deepEqual(Object.keys(store.get().candidates.entries).sort(),['Open preferences','Open settings']);service.close();
});
test('old or missing candidate revisions fail closed before provider work',async()=>{
 let calls=0;const store=memoryStore(),service=M.createService({store,providerTranslate:()=>calls++});
 const missing=envelope(store.get());delete missing.candidatesRevision;assert.equal((await service.translate(missing)).status,'invalid_request');
 store.set(s=>s.candidates.revision++);assert.equal((await service.translate(envelope(store.get(),{candidatesRevision:0}))).status,'stale');assert.equal(calls,0);service.close();
 const unavailable=M.createService({store:{read:async()=>({config:enabledConfig(),dictionary:S.defaultDictionary()})},providerTranslate:()=>calls++});
 assert.equal((await unavailable.snapshot()).status,'storage_unavailable');assert.equal(calls,0);unavailable.close();
});
test('component startup and periodic cleanup expire candidates without renderer polling',async()=>{
 let now=604801000,calls=0;const store=memoryStore(),intervals=new Map();store.set(s=>{s.candidates.entries.Label={translation:'标签',createdAt:1000,expiresAt:604801000,context:'ui'};});
 const timers={setInterval(callback,delay){intervals.set(delay,callback);return delay;},clearInterval(handle){intervals.delete(handle);}};
 const service=M.createService({store,clock:()=>now,timers,providerTranslate:()=>calls++});await new Promise(r=>setImmediate(r));
 assert.equal(store.get().candidates.entries.Label,undefined);assert.ok(intervals.has(60000));
 store.set(s=>{s.candidates.entries.Other={translation:'其它',createdAt:now,expiresAt:now+604800000,context:'ui'};});now+=604800000;
 await intervals.get(60000)();assert.equal(store.get().candidates.entries.Other,undefined);assert.equal(calls,0);service.close();assert.equal(intervals.size,0);
});
test('clock rollback hides future candidates without repeating provider calls',async()=>{
 const store=memoryStore();store.set(s=>{s.candidates.entries['Open settings']={translation:'打开设置',createdAt:2000,expiresAt:604802000,context:'ui'};});
 let calls=0;const service=M.createService({store,clock:()=>1000,providerTranslate:()=>calls++});
 assert.deepEqual({...((await service.snapshot()).candidates)},{});
 for(let i=0;i<3;i++)assert.equal((await service.translate(envelope(store.get()))).translations.length,0);
 assert.equal(calls,0);assert.equal(store.get().candidates.entries['Open settings'].createdAt,2000);service.close();
});
