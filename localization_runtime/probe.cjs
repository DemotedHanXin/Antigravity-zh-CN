'use strict';
// Explicit GUI action only. No text, key, endpoint, or raw provider response is logged.
const {Store}=require('./storage.cjs');
const {translateBatch}=require('./providers.cjs');
async function probe({store=new Store(),translate=translateBatch,expectedRevision}={}){
  try{const {config}=await store.read();if(expectedRevision!==undefined&&config.revision!==expectedRevision)return {ok:false,status:'configuration_changed'};const result=await translate([{id:'probe',text:'Open settings',safeContextKind:'settings'}],{provider:config.provider,profile:config.providers[config.provider],timeoutMs:config.limits.timeoutMs});return {ok:result.length===1,status:result.length===1?'connected':'invalid_response'};}
  catch(error){return {ok:false,status:['invalid_configuration','invalid_endpoint','authentication_failed','rate_limited','provider_unavailable','invalid_response','timeout','cancelled','network_error'].includes(error.code)?error.code:'unavailable'};}
}
if(require.main===module){
  if(process.argv.length!==5||process.argv[2]!=='--confirm-network'||process.argv[3]!=='--revision'||!/^\d+$/.test(process.argv[4])||!Number.isSafeInteger(Number(process.argv[4]))){process.stdout.write(JSON.stringify({ok:false,status:'confirmation_required'})+'\n');process.exitCode=2;}
  else probe({expectedRevision:Number(process.argv[4])}).then(result=>{process.stdout.write(JSON.stringify(result)+'\n');process.exitCode=result.ok?0:1;});
}
module.exports={probe};
