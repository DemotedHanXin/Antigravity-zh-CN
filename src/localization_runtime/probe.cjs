'use strict';
// Explicit GUI action only. No text, key, endpoint, or raw provider response is logged.
const {Store}=require('./storage.cjs');
const {translateBatch}=require('./providers.cjs');
async function probe({store=new Store(),translate=translateBatch,expectedRevision}={}){
  try{const {config}=await store.read();if(expectedRevision!==undefined&&config.revision!==expectedRevision)return {ok:false,status:'configuration_changed'};const result=await translate([{id:'probe',text:'Open settings',safeContextKind:'settings'}],{provider:config.provider,profile:config.providers[config.provider],timeoutMs:config.limits.timeoutMs});return {ok:result.length===1,status:result.length===1?'connected':'invalid_response'};}
  catch(error){return {ok:false,status:['invalid_configuration','invalid_endpoint','unsafe_endpoint','authentication_failed','rate_limited','provider_unavailable','provider_rejected','invalid_response','timeout','cancelled','network_error','proxy_configuration_error','proxy_connection_failed','proxy_authentication_required','credential_protection_failed','credential_protection_unavailable','invalid_credentials'].includes(error.code)?error.code:'unavailable'};}
}
if(require.main===module){
  const args=process.argv;
  const custom=args.length===7&&args[5]==='--data-dir'&&require('node:path').isAbsolute(args[6]);
  if((args.length!==5&&!custom)||args[2]!=='--confirm-network'||args[3]!=='--revision'||!/^\d+$/.test(args[4])||!Number.isSafeInteger(Number(args[4]))){process.stdout.write(JSON.stringify({ok:false,status:'confirmation_required'})+'\n');process.exitCode=2;}
  else Promise.resolve().then(()=>probe({store:custom?new Store(args[6]):new Store(),expectedRevision:Number(args[4])})).catch(()=>({ok:false,status:'unavailable'})).then(result=>{process.stdout.write(JSON.stringify(result)+'\n');process.exitCode=result.ok?0:1;});
}
module.exports={probe};
