'use strict';
const fs=require('node:fs/promises');
const path=require('node:path');
const os=require('node:os');
const crypto=require('node:crypto');
const {DEFAULTS,PROVIDERS,TranslationError,endpoint}=require('./providers.cjs');
const DEFAULT_LIMITS=Object.freeze({concurrency:2,batchSize:8,batchCharacters:2000,textLength:160,timeoutMs:15000,requestsPerMinute:12,queueSize:128,sessionRequests:100});
const LIMIT_BOUNDS=Object.freeze({concurrency:[1,2],batchSize:[1,8],batchCharacters:[1,2000],textLength:[1,160],timeoutMs:[1000,15000],requestsPerMinute:[1,12],queueSize:[1,128],sessionRequests:[1,100]});
const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
const record=o=>!!o&&typeof o==='object'&&!Array.isArray(o);
const validUnicode=s=>Array.from(s).every(c=>c.codePointAt(0)<0xD800||c.codePointAt(0)>0xDFFF);
const revision=n=>Number.isSafeInteger(n)&&n>=0;
function userDirectory({platform=process.platform,env=process.env,home=os.homedir()}={}) {
  if(platform==='win32') {if(!env.APPDATA || !path.isAbsolute(env.APPDATA)) throw new TranslationError('invalid_user_directory');return path.join(env.APPDATA,'Antigravity-zh-CN');}
  if(platform==='darwin') return path.join(home,'Library','Application Support','Antigravity-zh-CN');
  return path.join(env.XDG_CONFIG_HOME&&path.isAbsolute(env.XDG_CONFIG_HOME)?env.XDG_CONFIG_HOME:path.join(home,'.config'),'Antigravity-zh-CN');
}
function defaultConfig(){return {schemaVersion:1,revision:0,enabled:false,autoSave:false,cacheEpoch:0,provider:'openai',providers:Object.fromEntries(PROVIDERS.map(p=>[p,{baseUrl:DEFAULTS[p],model:'',apiKey:''}])),limits:{...DEFAULT_LIMITS}};}
function defaultDictionary(){return {schemaVersion:1,revision:0,entries:{},tombstones:{}};}
function validateConfig(v) {
  if(!record(v)||v.schemaVersion!==1||!revision(v.revision)||!revision(v.cacheEpoch)||typeof v.enabled!=='boolean'||typeof v.autoSave!=='boolean'||!PROVIDERS.includes(v.provider)||!record(v.providers)||!record(v.limits)) throw new TranslationError('invalid_configuration');
  if(Object.keys(v.providers).sort().join(',')!==[...PROVIDERS].sort().join(',')||Object.keys(v.limits).sort().join(',')!==Object.keys(LIMIT_BOUNDS).sort().join(','))throw new TranslationError('invalid_configuration');
  for(const provider of PROVIDERS){
    const p=v.providers[provider];
    if(!record(p))throw new TranslationError('invalid_configuration');
    for(const [key,max] of [['baseUrl',2048],['model',200],['apiKey',4096]])if(typeof p[key]!=='string'||p[key].length>max||!validUnicode(p[key])||/[\x00-\x1f]/.test(p[key]))throw new TranslationError('invalid_configuration');
    if(p.baseUrl)endpoint(provider,{baseUrl:p.baseUrl,model:'validation',apiKey:'validation'});
  }
  for(const [key,[min,max]] of Object.entries(LIMIT_BOUNDS)){if(!Number.isSafeInteger(v.limits[key])||v.limits[key]<min||v.limits[key]>max)throw new TranslationError('invalid_configuration');}
  if(v.enabled&&!['baseUrl','model','apiKey'].every(k=>v.providers[v.provider][k].trim()))throw new TranslationError('invalid_configuration');
  return v;
}
function validateDictionary(v) {
  if(!record(v)||v.schemaVersion!==1||!revision(v.revision)||!record(v.entries)||!record(v.tombstones)||Object.keys(v.entries).length>10000||Object.keys(v.tombstones).length>10000) throw new TranslationError('invalid_dictionary');
  for(const [key,entry] of Object.entries(v.entries)) if(['__proto__','constructor','prototype'].includes(key)||own(v.tombstones,key)||!key||!validUnicode(key)||key.includes('\0')||key.trim()!==key||key.length>500||!record(entry)||typeof entry.translation!=='string'||!entry.translation.trim()||!validUnicode(entry.translation)||entry.translation.includes('\0')||entry.translation.length>2000||!['manual','ai'].includes(entry.source)||typeof entry.updatedAt!=='string'||entry.context!=='ui') throw new TranslationError('invalid_dictionary');
  for(const [key,n] of Object.entries(v.tombstones)) if(['__proto__','constructor','prototype'].includes(key)||!key||!validUnicode(key)||key.includes('\0')||key.trim()!==key||key.length>500||!revision(n)||n>v.revision) throw new TranslationError('invalid_dictionary');
  return v;
}
async function ensureDirectory(directory) {
  await fs.mkdir(directory,{recursive:true,mode:0o700});
  const st=await fs.lstat(directory);
  if(!st.isDirectory()||st.isSymbolicLink()) throw new TranslationError('unsafe_user_directory');
  if(process.platform!=='win32')await fs.chmod(directory,0o700);
}
async function readJson(file,fallback) {
  let handle;
  try {
    const st=await fs.lstat(file);if(!st.isFile()||st.isSymbolicLink()||st.size>4*1024*1024) throw new TranslationError('invalid_storage');
    handle=await fs.open(file,require('node:fs').constants.O_RDONLY|(require('node:fs').constants.O_NOFOLLOW||0));
    const actual=await handle.stat();if(actual.ino!==st.ino||actual.dev!==st.dev||actual.size>4*1024*1024) throw new TranslationError('invalid_storage');
    const data=await handle.readFile({encoding:'utf8'});return JSON.parse(data);
  } catch(e) {if(e.code==='ENOENT')return fallback();throw e instanceof TranslationError?e:new TranslationError('storage_read_failed');}
  finally {await handle?.close();}
}
async function atomicWrite(file,value) {
  const encoded=JSON.stringify(value,null,2)+'\n';
  if(Buffer.byteLength(encoded,'utf8')>4*1024*1024)throw new TranslationError('storage_too_large');
  const temp=path.join(path.dirname(file),`.${path.basename(file)}.${crypto.randomBytes(12).toString('hex')}.tmp`);
  let h;
  try {
    h=await fs.open(temp,'wx',0o600);await h.writeFile(encoded,'utf8');await h.sync();await h.close();h=null;
    await fs.rename(temp,file);
    if(process.platform!=='win32'){const dir=await fs.open(path.dirname(file),'r');try{await dir.sync();}finally{await dir.close();}}
  } finally {await h?.close();await fs.unlink(temp).catch(e=>{if(e.code!=='ENOENT')throw e;});}
}
class Store {
  constructor(directory=userDirectory()){this.directory=directory;}
  async read(){
    // A missing directory is read-only default state; never create files on snapshot.
    try {const st=await fs.lstat(this.directory);if(!st.isDirectory()||st.isSymbolicLink())throw new TranslationError('unsafe_user_directory');}catch(e){if(e.code==='ENOENT')return {config:defaultConfig(),dictionary:defaultDictionary()};throw e;}
    const config=validateConfig(await readJson(path.join(this.directory,'config.json'),defaultConfig));
    const dictionary=validateDictionary(await readJson(path.join(this.directory,'personal-dictionary.json'),defaultDictionary));
    return {config,dictionary};
  }
  async withLock(fn,{timeoutMs=2000}={}) {
    await ensureDirectory(this.directory);
    const lock=path.join(this.directory,'.translation.lock');const start=Date.now();
    while(true){try{await fs.mkdir(lock,{mode:0o700});break;}catch(e){if(e.code!=='EEXIST')throw new TranslationError('storage_write_failed');if(Date.now()-start>=timeoutMs)throw new TranslationError('storage_locked');await new Promise(r=>setTimeout(r,25));}}
    try{return await fn();}finally{await fs.rmdir(lock);}
  }
  async saveAI(items,expectedDictionaryRevision,expectedConfigRevision) {
    return this.withLock(async()=>{
      const {config,dictionary}=await this.read();
      if(!config.enabled||!config.autoSave||config.revision!==expectedConfigRevision||dictionary.revision!==expectedDictionaryRevision)return false;
      let changed=false;
      for(const {source,translation} of items){
        if(typeof source!=='string'||!source||source!==source.trim()||source.length>500||typeof translation!=='string'||!translation||translation.length>2000)continue;
        if(own(dictionary.tombstones,source)||own(dictionary.entries,source))continue;
        Object.defineProperty(dictionary.entries,source,{value:{translation,source:'ai',updatedAt:new Date().toISOString(),context:'ui'},enumerable:true,writable:true,configurable:true});changed=true;
      }
      if(!changed)return false;
      dictionary.revision++;validateDictionary(dictionary);
      await atomicWrite(path.join(this.directory,'personal-dictionary.json'),dictionary);return true;
    });
  }
}
module.exports={Store,userDirectory,defaultConfig,defaultDictionary,validateConfig,validateDictionary,DEFAULT_LIMITS,LIMIT_BOUNDS,atomicWrite};
