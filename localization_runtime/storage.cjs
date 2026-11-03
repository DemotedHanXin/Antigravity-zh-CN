'use strict';
const fs=require('node:fs/promises');
const path=require('node:path');
const os=require('node:os');
const crypto=require('node:crypto');
const {TextDecoder}=require('node:util');
const {DEFAULTS,PROVIDERS,TranslationError,endpoint}=require('./providers.cjs');
const DEFAULT_LIMITS=Object.freeze({concurrency:2,batchSize:8,batchCharacters:2000,textLength:160,timeoutMs:15000,requestsPerMinute:12,queueSize:128,sessionRequests:100});
const LIMIT_BOUNDS=Object.freeze({concurrency:[1,2],batchSize:[1,8],batchCharacters:[1,2000],textLength:[1,160],timeoutMs:[1000,15000],requestsPerMinute:[1,12],queueSize:[1,128],sessionRequests:[1,100]});
const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
const record=o=>!!o&&typeof o==='object'&&!Array.isArray(o);
const validUnicode=s=>Array.from(s).every(c=>c.codePointAt(0)<0xD800||c.codePointAt(0)>0xDFFF);
const revision=n=>Number.isSafeInteger(n)&&n>=0;
// Union of ECMAScript trim and Python whitespace; keep disk validation identical.
const trim=value=>value.replace(/^[\s\u001c-\u001f\u0085]+|[\s\u001c-\u001f\u0085]+$/g,'');
function finiteJson(value) {
  if(typeof value==='number'&&!Number.isFinite(value))throw new TranslationError('invalid_storage');
  if(Array.isArray(value)||record(value))for(const item of Object.values(value))finiteJson(item);
  return value;
}
function userDirectory({platform=process.platform,env=process.env,home=os.homedir()}={}) {
  if(platform==='win32') {if(!env.APPDATA || !path.isAbsolute(env.APPDATA)) throw new TranslationError('invalid_user_directory');return path.join(env.APPDATA,'Antigravity-zh-CN');}
  if(platform==='darwin') return path.join(home,'Library','Application Support','Antigravity-zh-CN');
  return path.join(env.XDG_CONFIG_HOME&&path.isAbsolute(env.XDG_CONFIG_HOME)?env.XDG_CONFIG_HOME:path.join(home,'.config'),'Antigravity-zh-CN');
}
const CANDIDATE_TTL_MS=604800000, MAX_FILE_BYTES=4*1024*1024, MAX_JOURNAL_BYTES=16*1024*1024;
const MAX_TIMESTAMP_MS=253402300799999;
const CANDIDATES_FILE='pending-translations/state.json', JOURNAL_FILE='.translation-journal.json';
const STATE_FILES=['config.json','personal-dictionary.json',CANDIDATES_FILE];
const MISSING=Symbol('missing');
function defaultConfig(){return {schemaVersion:2,revision:0,enabled:false,autoSave:false,cacheEpoch:0,provider:'openai',providers:Object.fromEntries(PROVIDERS.map(p=>[p,{baseUrl:DEFAULTS[p],model:'',apiKey:''}])),limits:{...DEFAULT_LIMITS}};}
function defaultDictionary(){return {schemaVersion:2,revision:0,entries:{},tombstones:{}};}
function defaultCandidates(){return {schemaVersion:2,revision:0,entries:{},rejected:{},epochs:{}};}
function validateConfig(v,version=2) {
  if(!record(v)||v.schemaVersion!==version||!revision(v.revision)||!revision(v.cacheEpoch)||typeof v.enabled!=='boolean'||typeof v.autoSave!=='boolean'||!PROVIDERS.includes(v.provider)||!record(v.providers)||!record(v.limits)) throw new TranslationError('invalid_configuration');
  if(version===2&&v.autoSave!==false)throw new TranslationError('invalid_configuration');
  if(Object.keys(v.providers).sort().join(',')!==[...PROVIDERS].sort().join(',')||Object.keys(v.limits).sort().join(',')!==Object.keys(LIMIT_BOUNDS).sort().join(','))throw new TranslationError('invalid_configuration');
  for(const provider of PROVIDERS){
    const p=v.providers[provider];
    if(!record(p))throw new TranslationError('invalid_configuration');
    for(const [key,max] of [['baseUrl',2048],['model',200],['apiKey',4096]])if(typeof p[key]!=='string'||p[key].length>max||!validUnicode(p[key])||/[\x00-\x1f]/.test(p[key]))throw new TranslationError('invalid_configuration');
    if(p.baseUrl)endpoint(provider,{baseUrl:p.baseUrl,model:'validation',apiKey:'validation'});
  }
  for(const [key,[min,max]] of Object.entries(LIMIT_BOUNDS)){if(!Number.isSafeInteger(v.limits[key])||v.limits[key]<min||v.limits[key]>max)throw new TranslationError('invalid_configuration');}
  if(v.enabled&&!['baseUrl','model','apiKey'].every(k=>trim(v.providers[v.provider][k])))throw new TranslationError('invalid_configuration');
  return v;
}
function validateDictionary(v,version=2) {
  if(!record(v)||v.schemaVersion!==version||!revision(v.revision)||!record(v.entries)||!record(v.tombstones)||Object.keys(v.entries).length>10000||Object.keys(v.tombstones).length>10000) throw new TranslationError('invalid_dictionary');
  for(const [key,entry] of Object.entries(v.entries)) if(!sourceText(key)||own(v.tombstones,key)||!record(entry)||!translatedText(entry.translation)||!(version===1?['manual','ai']:['manual','accepted','legacy-ai']).includes(entry.source)||typeof entry.updatedAt!=='string'||entry.context!=='ui') throw new TranslationError('invalid_dictionary');
  for(const [key,n] of Object.entries(v.tombstones)) if(!sourceText(key)||!revision(n)||n>v.revision) throw new TranslationError('invalid_dictionary');
  return v;
}
async function ensureDirectory(directory) {
  await fs.mkdir(directory,{recursive:true,mode:0o700});
  const st=await fs.lstat(directory);
  if(!st.isDirectory()||st.isSymbolicLink()) throw new TranslationError('unsafe_user_directory');
  if(process.platform!=='win32')await fs.chmod(directory,0o700);
}
async function readJson(file,fallback,maximum=MAX_FILE_BYTES) {
  let handle;
  try {
    const st=await fs.lstat(file);if(!st.isFile()||st.isSymbolicLink()||st.size>maximum) throw new TranslationError('invalid_storage');
    handle=await fs.open(file,require('node:fs').constants.O_RDONLY|(require('node:fs').constants.O_NOFOLLOW||0));
    const actual=await handle.stat();if(actual.ino!==st.ino||actual.dev!==st.dev||actual.size>maximum) throw new TranslationError('invalid_storage');
    const data=await handle.readFile();if(data.length>maximum)throw new TranslationError('invalid_storage');
    return finiteJson(JSON.parse(new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(data)));
  } catch(e) {if(e.code==='ENOENT')return fallback();throw e instanceof TranslationError?e:new TranslationError('storage_read_failed');}
  finally {await handle?.close();}
}
async function atomicWrite(file,value,maximum=MAX_FILE_BYTES) {
  finiteJson(value);
  const encoded=JSON.stringify(value,null,2)+'\n';
  if(Buffer.byteLength(encoded,'utf8')>maximum)throw new TranslationError('storage_too_large');
  const temp=path.join(path.dirname(file),`.${path.basename(file)}.${crypto.randomBytes(12).toString('hex')}.tmp`);
  let h;
  try {
    h=await fs.open(temp,'wx',0o600);await h.writeFile(encoded,'utf8');await h.sync();await h.close();h=null;
    await fs.rename(temp,file);
    if(process.platform!=='win32'){const dir=await fs.open(path.dirname(file),'r');try{await dir.sync();}finally{await dir.close();}}
  } finally {await h?.close();await fs.unlink(temp).catch(e=>{if(e.code!=='ENOENT')throw e;});}
}

const sourceText = value => typeof value==='string' && !!trim(value) && trim(value)===value &&
  value.length<=500 && validUnicode(value) && !value.includes('\0') && !['__proto__','constructor','prototype'].includes(value);
const translatedText = value => typeof value==='string' && !!trim(value) && value.length<=2000 && validUnicode(value) && !value.includes('\0');
const bump = value => {if(!revision(value)||value>=Number.MAX_SAFE_INTEGER)throw new TranslationError('revision_limit');return value+1;};
const epochFor = (candidates,source) => own(candidates.epochs,source)?candidates.epochs[source]:0;
function validateCandidates(value) {
  if(!record(value)||value.schemaVersion!==2||!revision(value.revision))throw new TranslationError('invalid_candidates');
  for(const key of ['entries','rejected','epochs'])if(!record(value[key])||Object.keys(value[key]).length>10000)throw new TranslationError('invalid_candidates');
  if(new Set(['entries','rejected','epochs'].flatMap(key=>Object.keys(value[key]))).size>10000)throw new TranslationError('candidate_capacity');
  for(const [source,item] of Object.entries(value.entries)) {
    if(!sourceText(source)||own(value.rejected,source)||!record(item)||Object.keys(item).sort().join(',')!=='context,createdAt,expiresAt,translation'||
       !translatedText(item.translation)||item.context!=='ui'||!revision(item.createdAt)||!revision(item.expiresAt)||
       item.createdAt>MAX_TIMESTAMP_MS-CANDIDATE_TTL_MS||item.expiresAt>MAX_TIMESTAMP_MS||
       item.expiresAt-item.createdAt!==CANDIDATE_TTL_MS)throw new TranslationError('invalid_candidates');
  }
  for(const [source,item] of Object.entries(value.rejected))if(!sourceText(source)||!record(item)||
    Object.keys(item).join(',')!=='rejectedAt'||!revision(item.rejectedAt)||item.rejectedAt>MAX_TIMESTAMP_MS)throw new TranslationError('invalid_candidates');
  for(const [source,epoch] of Object.entries(value.epochs))if(!sourceText(source)||!revision(epoch))throw new TranslationError('invalid_candidates');
  return value;
}
async function regular(file,directory=false) {
  const info=await fs.lstat(file);
  if(info.isSymbolicLink()||!(directory?info.isDirectory():info.isFile()))throw new TranslationError('invalid_storage');
}
async function syncDirectory(directory) {
  if(process.platform!=='win32'){const handle=await fs.open(directory,'r');try{await handle.sync();}finally{await handle.close();}}
}
function encodedSize(value,maximum=MAX_FILE_BYTES) {
  finiteJson(value);
  if(Buffer.byteLength(JSON.stringify(value,null,2)+'\n','utf8')>maximum)throw new TranslationError('storage_too_large');
}
function invalidate(candidates,source) {
  candidates.epochs[source]=bump(epochFor(candidates,source));
  delete candidates.entries[source];
}
class Store {
  constructor(directory=userDirectory(),{clock=Date.now,lockTimeoutMs=2000}={}) {
    this.directory=directory;this.clock=clock;this.lockTimeoutMs=lockTimeoutMs;
  }
  now(value) {
    value=value===undefined?this.clock():value;
    if(typeof value==='function')value=value();
    if(!revision(value)||value>MAX_TIMESTAMP_MS-CANDIDATE_TTL_MS)throw new TranslationError('invalid_time');
    return value;
  }
  async parent(name,create=false) {
    if(![...STATE_FILES,JOURNAL_FILE].includes(name))throw new TranslationError('invalid_storage_path');
    await regular(this.directory,true);
    if(name===CANDIDATES_FILE) {
      const directory=path.join(this.directory,'pending-translations');
      if(create)await ensureDirectory(directory);
      else try{await regular(directory,true);}catch(error){if(error.code!=='ENOENT')throw error;}
      return directory;
    }
    return this.directory;
  }
  async readFile(name,fallback,maximum=MAX_FILE_BYTES) {
    await this.parent(name);
    return readJson(path.join(this.directory,name),fallback,maximum);
  }
  async writeFile(name,value,maximum=MAX_FILE_BYTES) {
    await this.parent(name,true);
    const file=path.join(this.directory,name);
    try{await regular(file);}catch(error){if(error.code!=='ENOENT')throw error;}
    return atomicWrite(file,value,maximum);
  }
  async validateImages(images) {
    if(!record(images)||!Object.keys(images).length||Object.keys(images).some(name=>!STATE_FILES.includes(name)))throw new TranslationError('invalid_journal');
    const validators={'config.json':validateConfig,'personal-dictionary.json':validateDictionary,[CANDIDATES_FILE]:validateCandidates};
    for(const [name,value] of Object.entries(images)) {
      validators[name](value);encodedSize(value);await this.parent(name);
      try{await regular(path.join(this.directory,name));}catch(error){if(error.code!=='ENOENT')throw error;}
    }
  }
  async applyImages(images) {
    for(const name of STATE_FILES)if(own(images,name))await this.writeFile(name,images[name]);
    await fs.unlink(path.join(this.directory,JOURNAL_FILE));await syncDirectory(this.directory);
  }
  async recover() {
    const journal=await this.readFile(JOURNAL_FILE,()=>MISSING,MAX_JOURNAL_BYTES);
    if(journal===MISSING)return;
    if(!record(journal)||Object.keys(journal).sort().join(',')!=='files,id,kind,schemaVersion'||journal.schemaVersion!==1||
       journal.kind!=='dragongirl-state-transaction'||typeof journal.id!=='string'||!/^[a-f0-9]{32}$/.test(journal.id))throw new TranslationError('invalid_journal');
    await this.validateImages(journal.files);await this.applyImages(journal.files);
  }
  async commit(images) {
    if(!Object.keys(images).length)return;
    await this.validateImages(images);
    const journal={schemaVersion:1,kind:'dragongirl-state-transaction',id:crypto.randomBytes(16).toString('hex'),files:images};
    encodedSize(journal,MAX_JOURNAL_BYTES);await this.writeFile(JOURNAL_FILE,journal,MAX_JOURNAL_BYTES);
    // A durable journal commits the intended state. Interrupted application is
    // completed under the shared lock before any new reader or writer proceeds.
    await this.applyImages(images);
  }
  async readLocked(now) {
    await this.recover();
    const config=await this.readFile('config.json',defaultConfig);
    const dictionary=await this.readFile('personal-dictionary.json',defaultDictionary);
    const candidates=validateCandidates(await this.readFile(CANDIDATES_FILE,defaultCandidates));
    const images={};
    if(record(config)&&config.schemaVersion===1) {
      validateConfig(config,1);config.schemaVersion=2;config.autoSave=false;
      config.revision=bump(config.revision);config.cacheEpoch=bump(config.cacheEpoch);images['config.json']=config;
    }
    validateConfig(config);
    if(record(dictionary)&&dictionary.schemaVersion===1) {
      validateDictionary(dictionary,1);dictionary.schemaVersion=2;dictionary.revision=bump(dictionary.revision);
      for(const item of Object.values(dictionary.entries))if(item.source==='ai')item.source='legacy-ai';
      images['personal-dictionary.json']=dictionary;
    }
    validateDictionary(dictionary);
    const expired=Object.entries(candidates.entries).filter(([,item])=>now>=item.expiresAt).map(([source])=>source);
    for(const source of expired)invalidate(candidates,source);
    if(expired.length){candidates.revision=bump(candidates.revision);images[CANDIDATES_FILE]=candidates;}
    if(Object.keys(images).length&&!own(images,CANDIDATES_FILE))images[CANDIDATES_FILE]=candidates;
    validateCandidates(candidates);await this.commit(images);
    return {config,dictionary,candidates};
  }
  async read(nowMs) {
    this.now(nowMs);
    try{await regular(this.directory,true);}catch(error){if(error.code==='ENOENT')return {config:defaultConfig(),dictionary:defaultDictionary(),candidates:defaultCandidates()};throw error;}
    return this.withLock(()=>this.readLocked(this.now(nowMs)));
  }
  async withLock(fn,{timeoutMs=this.lockTimeoutMs}={}) {
    await ensureDirectory(this.directory);
    const lock=path.join(this.directory,'.translation.lock'),start=Date.now();
    while(true){try{await fs.mkdir(lock,{mode:0o700});break;}catch(error){if(error.code!=='EEXIST')throw new TranslationError('storage_write_failed');if(Date.now()-start>=timeoutMs)throw new TranslationError('storage_locked');await new Promise(resolve=>setTimeout(resolve,25));}}
    try{return await fn();}finally{await fs.rmdir(lock);}
  }
  async saveCandidates(items,guard,nowMs) {
    this.now(nowMs);
    if(!Array.isArray(items)||items.length>10000||!record(guard)||!revision(guard.configRevision)||!revision(guard.dictionaryRevision)||!record(guard.epochs))throw new TranslationError('invalid_candidate_request');
    const seen=new Set();
    for(const item of items) {
      if(!record(item)||!sourceText(item.source)||!translatedText(item.translation)||seen.has(item.source)||
         !own(guard.epochs,item.source)||!revision(guard.epochs[item.source]))throw new TranslationError('invalid_candidate_request');
      seen.add(item.source);
    }
    return this.withLock(async()=>{
      const {config,dictionary,candidates}=await this.readLocked(this.now(nowMs));
      const now=this.now(nowMs);
      const expired=Object.entries(candidates.entries).filter(([,item])=>now>=item.expiresAt).map(([source])=>source);
      for(const source of expired)invalidate(candidates,source);
      let changed=expired.length>0;
      const finish=async(saved,status)=>{
        if(changed){candidates.revision=bump(candidates.revision);validateCandidates(candidates);await this.commit({[CANDIDATES_FILE]:candidates});}
        return {saved,candidatesRevision:candidates.revision,status};
      };
      if(!config.enabled)return finish([],'disabled');
      if(config.revision!==guard.configRevision||dictionary.revision!==guard.dictionaryRevision)return finish([],'stale');
      const saved=[];
      for(const {source,translation} of items) {
        if(epochFor(candidates,source)!==guard.epochs[source]||own(dictionary.entries,source)||own(candidates.rejected,source))continue;
        if(!own(candidates.entries,source)) {
          candidates.entries[source]={translation:trim(translation),createdAt:now,expiresAt:now+CANDIDATE_TTL_MS,context:'ui'};
          changed=true;
        }
        const item=candidates.entries[source];
        saved.push({source,translation:item.translation,createdAt:item.createdAt,expiresAt:item.expiresAt});
      }
      return finish(saved,saved.length||!items.length?'ok':'stale');
    });
  }
}
module.exports={Store,userDirectory,defaultConfig,defaultDictionary,defaultCandidates,validateConfig,validateDictionary,validateCandidates,
  DEFAULT_LIMITS,LIMIT_BOUNDS,CANDIDATE_TTL_MS,MAX_TIMESTAMP_MS,CANDIDATES_FILE,JOURNAL_FILE,atomicWrite};
