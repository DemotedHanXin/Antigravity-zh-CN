'use strict';
// Fixed script and stdin-only data: credentials never enter argv or a shell.
const {execFile}=require('node:child_process');
const path=require('node:path');
const {TextDecoder}=require('node:util');
const {TranslationError}=require('./providers.cjs');
const SCRIPT=String.raw`$ErrorActionPreference='Stop'
try {
  Add-Type -AssemblyName System.Security
  $request=[Console]::In.ReadToEnd() | ConvertFrom-Json
  $entropy=[Text.Encoding]::UTF8.GetBytes('Antigravity-zh-CN credentials v1')
  $data=[Convert]::FromBase64String($request.data)
  $scope=[Security.Cryptography.DataProtectionScope]::CurrentUser
  if ($request.action -eq 'protect') {
    $result=[Security.Cryptography.ProtectedData]::Protect($data,$entropy,$scope)
  } elseif ($request.action -eq 'unprotect') {
    $result=[Security.Cryptography.ProtectedData]::Unprotect($data,$entropy,$scope)
  } else { exit 1 }
  [Console]::Out.Write([Convert]::ToBase64String($result))
} catch { exit 1 }`;
class WindowsProtector {
  constructor(){this.cache=new Map();}
  async crypt(action,data) {
    if(process.platform!=='win32')throw new TranslationError('credential_protection_unavailable');
    const systemRoot=process.env.SystemRoot;
    if(!systemRoot||!path.isAbsolute(systemRoot))throw new TranslationError('credential_protection_unavailable');
    const executable=path.join(systemRoot,'System32','WindowsPowerShell','v1.0','powershell.exe');
    return new Promise((resolve,reject)=>{
      const child=execFile(executable,['-NoLogo','-NoProfile','-NonInteractive','-Command',SCRIPT],
        {windowsHide:true,timeout:10000,maxBuffer:65536,encoding:'utf8'},(error,stdout)=>{
          if(error||!/^[A-Za-z0-9+/]+={0,2}$/.test(stdout)||stdout.length>32768)reject(new TranslationError('credential_protection_failed'));
          else resolve(stdout);
        });
      child.stdin.on('error',()=>{});
      child.stdin.end(JSON.stringify({action,data}));
    });
  }
  async protect(value){return this.crypt('protect',Buffer.from(value,'utf8').toString('base64'));}
  async unprotect(value){
    if(this.cache.has(value))return this.cache.get(value);
    let result;
    try{result=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(Buffer.from(await this.crypt('unprotect',value),'base64'));}
    catch(_){throw new TranslationError('credential_protection_failed');}
    // Bound retained plaintext to the currently/recently configured providers.
    if(this.cache.size>=8)this.cache.clear();
    this.cache.set(value,result);return result;
  }
}
module.exports={WindowsProtector};
