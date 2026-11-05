'use strict';
// Deliberately unencrypted test-only codec, paired with credential_fixture.py.
// Only tests import this module; production has no env/CLI bypass for DPAPI.
const storage=require('../localization_runtime/storage.cjs');
class FixtureProtector {
  async protect(value){return Buffer.from('fixture:'+value,'utf8').toString('base64');}
  async unprotect(value){
    const result=new TextDecoder('utf-8',{fatal:true}).decode(Buffer.from(value,'base64'));
    if(!result.startsWith('fixture:'))throw Error('fixture mismatch');
    return result.slice(8);
  }
}
class Store extends storage.Store {
  constructor(directory,options={}){
    super(directory,{...(process.platform==='win32'?{}:{protector:new FixtureProtector()}),...options});
  }
}
module.exports={...storage,Store,FixtureProtector};
