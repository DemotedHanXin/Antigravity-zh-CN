'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const os=require('node:os');
const path=require('node:path');
const S=require('../../localization_runtime/storage.cjs');
const {FixtureProtector}=require('../credential_fixture.cjs');
const {WindowsProtector}=require('../../localization_runtime/credentials.cjs');
const {probe}=require('../../localization_runtime/probe.cjs');

async function fixture(t){
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'m3-credentials-'));
  t.after(()=>fs.rm(directory,{recursive:true,force:true}));
  return new S.Store(directory,{protector:new FixtureProtector()});
}
function config(){const value=S.defaultConfig();value.enabled=true;value.providers.openai.model='fixture';value.providers.openai.apiKey='isolated-credential-123';return value;}

test('legacy plaintext becomes protected disk v3 exactly once and old validators reject it',async t=>{
  const store=await fixture(t),file=path.join(store.directory,'config.json');
  await S.atomicWrite(file,config());const state=await store.read();
  assert.equal(state.config.revision,1);assert.equal(state.config.cacheEpoch,1);
  assert.equal(state.config.providers.openai.apiKey,'isolated-credential-123');
  const raw=await fs.readFile(file,'utf8');assert.equal(raw.includes('isolated-credential-123'),false);
  const disk=JSON.parse(raw);assert.equal(disk.schemaVersion,3);assert.throws(()=>S.validateConfig(disk));
  assert.deepEqual(await store.read(),state);assert.equal(await fs.readFile(file,'utf8'),raw);
});

test('interrupted migration leaves only protected credential data in journal',async t=>{
  const store=await fixture(t),file=path.join(store.directory,'config.json');
  await S.atomicWrite(file,config());const original=store.writeFile;
  store.writeFile=async function(name,...args){if(name==='config.json')throw Error('fixture');return original.call(this,name,...args);};
  await assert.rejects(store.read());
  const journal=await fs.readFile(path.join(store.directory,S.JOURNAL_FILE),'utf8');
  assert.equal(journal.includes('isolated-credential-123'),false);
  assert.equal(JSON.parse(journal).files['config.json'].schemaVersion,3);
  store.writeFile=original;assert.equal((await store.read()).config.revision,1);
});

test('wrong-account or unavailable protection preserves disk and probe makes zero requests',async t=>{
  const store=await fixture(t),file=path.join(store.directory,'config.json');
  await S.atomicWrite(file,config());await store.read();const before=await fs.readFile(file);
  store.protector.unprotect=async()=>{throw new (require('../../localization_runtime/providers.cjs').TranslationError)('credential_protection_failed');};
  let calls=0;const result=await probe({store,translate:()=>{calls++;}});
  assert.equal(result.ok,false);assert.equal(calls,0);assert.deepEqual(await fs.readFile(file),before);
});

test('protected schema rejects mixed plaintext and noncanonical base64 before calling DPAPI',async t=>{
  const store=await fixture(t),disk=await store.sealConfig(config());
  store.protector.unprotect=()=>{throw Error('must not run');};
  for(const modify of [c=>c.providers.openai.apiKey='plaintext',c=>c.providers.openai.apiKeyProtected='ab=c',c=>c.providers.openai.apiKeyProtected='Zh==']){
    const value=structuredClone(disk);modify(value);await assert.rejects(store.openConfig(value),{code:'invalid_credentials'});
  }
});

test('DPAPI output invalid UTF-8 never becomes replacement characters or enters cache',async()=>{
  const protector=new WindowsProtector();protector.crypt=async()=>'/w==';
  await assert.rejects(protector.unprotect('fixture'),{code:'credential_protection_failed'});
  assert.equal(protector.cache.size,0);
});

test('native Windows protector binds and authenticates ciphertext', {skip:process.platform!=='win32'},async()=>{
  const protector=new WindowsProtector(),protectedValue=await protector.protect('isolated-密钥-123');
  assert.equal(await protector.unprotect(protectedValue),'isolated-密钥-123');
  const bytes=Buffer.from(protectedValue,'base64');bytes[bytes.length-1]^=1;
  await assert.rejects(protector.unprotect(bytes.toString('base64')),{code:'credential_protection_failed'});
});

test('native protection fails closed on unsupported platforms',{skip:process.platform==='win32'},async()=>{
  await assert.rejects(new WindowsProtector().protect('fixture'),{code:'credential_protection_unavailable'});
});
