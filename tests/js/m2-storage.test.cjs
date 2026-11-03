'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const os=require('node:os');
const path=require('node:path');
const S=require('../../localization_runtime/storage.cjs');
const NOW=1700000000000;
async function fixture(t) {
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'m2-storage-'));
  t.after(()=>fs.rm(directory,{recursive:true,force:true}));
  return new S.Store(directory,{clock:()=>NOW,lockTimeoutMs:100});
}
function enabled() {
  const config=S.defaultConfig();config.enabled=true;config.revision=4;
  config.providers.openai.model='fixture';config.providers.openai.apiKey='fixture-key';return config;
}
async function seed(store,{config=enabled(),dictionary=S.defaultDictionary(),candidates}={}) {
  await S.atomicWrite(path.join(store.directory,'config.json'),config);
  await S.atomicWrite(path.join(store.directory,'personal-dictionary.json'),dictionary);
  if(candidates){await fs.mkdir(path.join(store.directory,'pending-translations'),{recursive:true});await S.atomicWrite(path.join(store.directory,S.CANDIDATES_FILE),candidates);}
}
function guard(state,sources) {
  return {configRevision:state.config.revision,dictionaryRevision:state.dictionary.revision,
    epochs:Object.fromEntries(sources.map(source=>[source,Object.hasOwn(state.candidates.epochs,source)?state.candidates.epochs[source]:0]))};
}
test('schema2 defaults are read-only and deprecated autosave cannot enable direct dictionary persistence',async t=>{
  const store=await fixture(t),missing=new S.Store(path.join(store.directory,'absent'));
  const state=await missing.read(NOW);assert.equal(state.config.schemaVersion,2);assert.equal(state.dictionary.schemaVersion,2);
  assert.equal(state.candidates.schemaVersion,2);assert.equal(state.config.autoSave,false);
  await assert.rejects(fs.stat(missing.directory),{code:'ENOENT'});
  assert.throws(()=>S.validateConfig({...state.config,autoSave:true}));assert.equal(store.saveAI,undefined);
});
test('migration preserves legacy entries and tombstones while old validators fail closed',async t=>{
  const store=await fixture(t),config={...enabled(),schemaVersion:1,autoSave:true,cacheEpoch:8};
  const dictionary={schemaVersion:1,revision:5,entries:{Manual:{translation:'人工',source:'manual',updatedAt:'old',context:'ui'},AI:{translation:'历史',source:'ai',updatedAt:'old-ai',context:'ui'}},tombstones:{Deleted:3}};
  await seed(store,{config,dictionary});const state=await store.read(NOW);
  assert.equal(state.config.revision,5);assert.equal(state.config.cacheEpoch,9);assert.equal(state.config.autoSave,false);
  assert.deepEqual(state.config.providers,config.providers);assert.equal(state.dictionary.revision,6);
  assert.deepEqual(state.dictionary.entries.Manual,dictionary.entries.Manual);
  assert.deepEqual(state.dictionary.entries.AI,{...dictionary.entries.AI,source:'legacy-ai'});
  assert.deepEqual(state.dictionary.tombstones,{Deleted:3});assert.deepEqual(state.candidates.entries,{});
  assert.throws(()=>S.validateConfig(state.config,1));assert.throws(()=>S.validateDictionary(state.dictionary,1));
  assert.deepEqual(await store.read(NOW),state);await assert.rejects(fs.stat(path.join(store.directory,S.JOURNAL_FILE)),{code:'ENOENT'});
});
test('candidate reuse keeps first value and seven-day deadline; equality expires and invalidates old responses',async t=>{
  const store=await fixture(t);await seed(store);const first=await store.read(NOW),g=guard(first,['Label']);
  const a=await store.saveCandidates([{source:'Label',translation:'首次'}],g,NOW);
  const b=await store.saveCandidates([{source:'Label',translation:'重复'}],g,NOW+5000);
  assert.deepEqual(b.saved,a.saved);assert.equal(b.candidatesRevision,a.candidatesRevision);
  assert.equal(a.saved[0].expiresAt,NOW+S.CANDIDATE_TTL_MS);
  assert.ok((await store.read(NOW+S.CANDIDATE_TTL_MS-1)).candidates.entries.Label);
  const expired=await store.read(NOW+S.CANDIDATE_TTL_MS);
  assert.deepEqual(expired.candidates.entries,{});assert.equal(expired.candidates.epochs.Label,1);
  assert.equal((await store.saveCandidates([{source:'Label',translation:'旧响应'}],g,NOW+S.CANDIDATE_TTL_MS)).status,'stale');
  const fresh=await store.saveCandidates([{source:'Label',translation:'新响应'}],guard(expired,['Label']),NOW+S.CANDIDATE_TTL_MS);
  assert.equal(fresh.saved[0].createdAt,NOW+S.CANDIDATE_TTL_MS);assert.equal(fresh.saved[0].translation,'新响应');
});
test('concurrent disjoint results share original guard without losing either candidate',async t=>{
  const store=await fixture(t);await seed(store);const state=await store.read(NOW),g=guard(state,['One','Two']);
  const other=new S.Store(store.directory,{clock:()=>NOW});
  const results=await Promise.all([store.saveCandidates([{source:'One',translation:'一'}],g),other.saveCandidates([{source:'Two',translation:'二'}],g)]);
  assert.deepEqual(results.map(result=>result.status),['ok','ok']);
  const final=await store.read(NOW);assert.deepEqual(Object.keys(final.candidates.entries).sort(),['One','Two']);
  assert.equal(final.candidates.revision,2);assert.deepEqual(final.candidates.epochs,{});assert.deepEqual(final.dictionary.entries,{});
});
test('candidate creation and expiry use the live clock after lock contention',async t=>{
  const store=await fixture(t);await seed(store);const state=await store.read(NOW),lock=path.join(store.directory,'.translation.lock');
  await fs.mkdir(lock);
  let now=NOW,seen;
  const observed=new Promise(resolve=>{seen=resolve;}),clock=()=>{seen();return now;};
  const pending=store.saveCandidates([{source:'Label',translation:'延后创建'}],guard(state,['Label']),clock);
  await observed;now+=5000;await fs.rmdir(lock);
  const result=await pending;assert.equal(result.saved[0].createdAt,now);assert.equal(result.saved[0].expiresAt,now+S.CANDIDATE_TTL_MS);
  await fs.mkdir(lock);now+=S.CANDIDATE_TTL_MS-1;
  let readClock;const reading=new Promise(resolve=>{readClock=resolve;});
  const read=store.read(()=>{readClock();return now;});await reading;now++;await fs.rmdir(lock);
  assert.deepEqual((await read).candidates.entries,{});
});
test('malformed UTF-8 in config dictionary candidates or journal is never replaced during migration',async t=>{
  const store=await fixture(t);
  for(const name of ['config.json','personal-dictionary.json',S.CANDIDATES_FILE,S.JOURNAL_FILE]){
    await seed(store);await fs.mkdir(path.join(store.directory,'pending-translations'),{recursive:true});
    const candidate={...S.defaultCandidates(),extension:'UTF8_SENTINEL'};
    const value=name==='config.json'?{...enabled(),schemaVersion:1,autoSave:true,extension:'UTF8_SENTINEL'}:
      name==='personal-dictionary.json'?{...S.defaultDictionary(),schemaVersion:1,extension:'UTF8_SENTINEL'}:
      name===S.CANDIDATES_FILE?candidate:{schemaVersion:1,kind:'dragongirl-state-transaction',id:'a'.repeat(32),files:{[S.CANDIDATES_FILE]:candidate}};
    const [start,end]=JSON.stringify(value).split('UTF8_SENTINEL');
    const file=path.join(store.directory,name),bytes=Buffer.concat([Buffer.from(start),Buffer.from([255]),Buffer.from(end)]);
    await fs.writeFile(file,bytes);await assert.rejects(store.read(NOW));assert.deepEqual(await fs.readFile(file),bytes);
    await fs.unlink(file);
  }
  const file=path.join(store.directory,'config.json'),bom=Buffer.concat([Buffer.from([239,187,191]),Buffer.from(JSON.stringify(enabled()))]);
  await fs.writeFile(file,bom);await assert.rejects(store.read(NOW));assert.deepEqual(await fs.readFile(file),bom);
});
test('candidate reuse rechecks lazy time when locked state reading crosses the deadline',async t=>{
  const store=await fixture(t);await seed(store);const state=await store.read(NOW),g=guard(state,['Label']);
  await store.saveCandidates([{source:'Label',translation:'候选'}],g,NOW);
  let now=NOW+S.CANDIDATE_TTL_MS-1;
  const original=store.readLocked;
  store.readLocked=async function(value){const result=await original.call(this,value);now++;return result;};
  const result=await store.saveCandidates([{source:'Label',translation:'不得延长'}],g,()=>now);
  assert.equal(result.status,'stale');assert.deepEqual(result.saved,[]);
  store.readLocked=original;
  const final=await store.read(now);assert.deepEqual(final.candidates.entries,{});assert.equal(final.candidates.epochs.Label,1);
});
test('candidate source capacity leaves room for expiry epochs and rejects growth before commit',async t=>{
  const store=await fixture(t),candidates=S.defaultCandidates();
  candidates.epochs=Object.fromEntries(Array.from({length:9999},(_,index)=>['Old '+index,1]));
  candidates.entries.Label={translation:'候选',createdAt:NOW,expiresAt:NOW+S.CANDIDATE_TTL_MS,context:'ui'};
  await seed(store,{candidates});const state=await store.read(NOW),file=path.join(store.directory,S.CANDIDATES_FILE),before=await fs.readFile(file);
  await assert.rejects(store.saveCandidates([{source:'One more',translation:'不能提交'}],guard(state,['One more']),NOW),{code:'candidate_capacity'});
  assert.deepEqual(await fs.readFile(file),before);await assert.rejects(fs.stat(path.join(store.directory,S.JOURNAL_FILE)),{code:'ENOENT'});
  const final=await store.read(NOW+S.CANDIDATE_TTL_MS);assert.equal(Object.keys(final.candidates.epochs).length,10000);assert.deepEqual(final.candidates.entries,{});
});
test('nonfinite JSON numbers cannot silently become null during migration or writes',async t=>{
  const store=await fixture(t),config={...enabled(),schemaVersion:1,autoSave:true};await seed(store,{config});
  const file=path.join(store.directory,'config.json');
  for(const value of ['NaN','Infinity','-Infinity','1e400']) {
    const raw=JSON.stringify(config).slice(0,-1)+',"extension":'+value+'}';await fs.writeFile(file,raw);
    await assert.rejects(store.read(NOW));assert.equal(await fs.readFile(file,'utf8'),raw);
  }
  await assert.rejects(S.atomicWrite(file,{extension:Infinity}),{code:'invalid_storage'});
});
test('rejected personal and stale revision sources cannot persist; deletion tombstones alone do not reject',async t=>{
  const store=await fixture(t),dictionary=S.defaultDictionary(),candidates=S.defaultCandidates();
  dictionary.entries.Personal={translation:'个人',source:'manual',updatedAt:'now',context:'ui'};dictionary.tombstones.Restored=0;
  candidates.rejected.Rejected={rejectedAt:NOW};candidates.epochs.Rejected=3;
  await seed(store,{dictionary,candidates});const state=await store.read(NOW);
  const result=await store.saveCandidates([{source:'Personal',translation:'覆盖'},{source:'Rejected',translation:'恢复'},{source:'Restored',translation:'新候选'}],guard(state,['Personal','Rejected','Restored']),NOW);
  assert.deepEqual(result.saved.map(item=>item.source),['Restored']);
  assert.equal((await store.saveCandidates([{source:'New',translation:'无效'}],{...guard(state,['New']),configRevision:3},NOW)).status,'stale');
  assert.equal((await store.read(NOW+S.CANDIDATE_TTL_MS)).candidates.rejected.Rejected.rejectedAt,NOW);
});
test('durable afterimage journal survives an interrupted candidate write and replays idempotently',async t=>{
  const store=await fixture(t);await seed(store);const state=await store.read(NOW),original=store.writeFile;
  store.writeFile=async function(name,...args){if(name===S.CANDIDATES_FILE)throw new Error('fixture interruption');return original.call(this,name,...args);};
  await assert.rejects(store.saveCandidates([{source:'Label',translation:'持久'}],guard(state,['Label']),NOW),/fixture interruption/);
  assert.ok(await fs.stat(path.join(store.directory,S.JOURNAL_FILE)));store.writeFile=original;
  const restored=await store.read(NOW);assert.equal(restored.candidates.entries.Label.translation,'持久');
  assert.deepEqual(await store.read(NOW),restored);await assert.rejects(fs.stat(path.join(store.directory,S.JOURNAL_FILE)),{code:'ENOENT'});
});
test('invalid or traversal journals fail closed and remain untouched',async t=>{
  const store=await fixture(t);await seed(store);const before=await fs.readFile(path.join(store.directory,'config.json'),'utf8');
  for(const value of [null,{schemaVersion:1,kind:'dragongirl-state-transaction',id:'a'.repeat(32),files:{'../outside.json':S.defaultCandidates()}},
    {schemaVersion:1,kind:'dragongirl-state-transaction',id:'a'.repeat(32),files:{[S.CANDIDATES_FILE]:{...S.defaultCandidates(),schemaVersion:3}}}]){
    await fs.writeFile(path.join(store.directory,S.JOURNAL_FILE),JSON.stringify(value));
    await assert.rejects(store.read(NOW));assert.equal(await fs.readFile(path.join(store.directory,S.JOURNAL_FILE),'utf8'),JSON.stringify(value));
    assert.equal(await fs.readFile(path.join(store.directory,'config.json'),'utf8'),before);
  }
});
test('unsafe candidate format and source tokens are rejected before a journal is committed',async t=>{
  const store=await fixture(t);await seed(store);const state=await store.read(NOW);
  for(const source of ['__proto__','constructor','prototype',' padded ','bad\0source','\ud800'])await assert.rejects(store.saveCandidates([{source,translation:'测试'}],guard(state,[source]),NOW));
  const invalid=S.defaultCandidates();invalid.entries.Label={translation:'测试',createdAt:NOW,expiresAt:NOW+S.CANDIDATE_TTL_MS+1,context:'ui'};
  assert.throws(()=>S.validateCandidates(invalid));
  assert.throws(()=>S.validateCandidates({...S.defaultCandidates(),entries:{Label:{translation:'测试',createdAt:Number.MAX_SAFE_INTEGER-S.CANDIDATE_TTL_MS,expiresAt:Number.MAX_SAFE_INTEGER,context:'ui'}}}));
  await assert.rejects(store.read(S.MAX_TIMESTAMP_MS),{code:'invalid_time'});
  await assert.rejects(store.saveCandidates([{source:'Label',translation:'测试'}],{...guard(state,['Label']),epochs:{}},NOW));
  await assert.rejects(fs.stat(path.join(store.directory,S.JOURNAL_FILE)),{code:'ENOENT'});
});
test('existing lock is never stolen even when a recoverable journal exists',async t=>{
  const store=await fixture(t);await seed(store);await fs.mkdir(path.join(store.directory,'.translation.lock'));
  await fs.writeFile(path.join(store.directory,S.JOURNAL_FILE),JSON.stringify({schemaVersion:1,kind:'dragongirl-state-transaction',id:'a'.repeat(32),files:{[S.CANDIDATES_FILE]:S.defaultCandidates()}}));
  await assert.rejects(store.read(NOW),{code:'storage_locked'});assert.ok(await fs.stat(path.join(store.directory,S.JOURNAL_FILE)));
});
