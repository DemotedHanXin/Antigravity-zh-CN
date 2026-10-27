'use strict';
const test=require('node:test'), assert=require('node:assert/strict');
const {EventEmitter}=require('node:events');
const path=require('node:path');
const {startBridge}=require('../../localization_runtime/bootstrap.cjs');
function setup(){
  const app=new EventEmitter(),registered=[];let disposed=0;
  const profile={verified:true,moduleType:'commonjs',preload:'dist/preload.js',trustedUrls:['https://fixture.invalid/ui']};
  const bridge=startBridge({electron:{app,ipcMain:{}},profile,appRoot:'/fixture',runtime:{installIpc:()=>({registerTrustedWindow:(wc,url)=>registered.push(url),dispose:()=>disposed++})}});
  function window(overrides={}){const wc=new EventEmitter();wc.isDestroyed=()=>false;wc.getURL=()=>profile.trustedUrls[0];wc.getType=()=> 'window';wc.getLastWebPreferences=()=>({preload:path.resolve('/fixture/dist/preload.js'),contextIsolation:true,sandbox:true,nodeIntegration:false,...overrides});return wc;}
  return {app,profile,bridge,window,registered,disposed:()=>disposed};
}
test('no trust until navigation completes, exact preload/security preferences required',()=>{
 const s=setup(),wc=s.window();s.app.emit('web-contents-created',{},wc);assert.equal(s.registered.length,0);wc.emit('did-finish-load');assert.equal(s.registered.length,1);s.bridge.dispose();assert.equal(s.disposed(),1);assert.equal(wc.listenerCount('did-finish-load'),0);
});
test('wrong preload, non-isolated and non-sandboxed windows never trusted',()=>{
 for(const bad of [{preload:'/wrong.js'},{contextIsolation:false},{sandbox:false},{nodeIntegration:true}]){const s=setup(),wc=s.window(bad);s.app.emit('web-contents-created',{},wc);wc.emit('did-finish-load');assert.equal(s.registered.length,0);s.bridge.dispose();}
});
test('wrong exact URL and webview never trusted',()=>{
 const s=setup();for(const kind of ['url','webview']){const wc=s.window();if(kind==='url')wc.getURL=()=> 'https://fixture.invalid/ui/extra';else wc.getType=()=> 'webview';s.app.emit('web-contents-created',{},wc);wc.emit('did-finish-load');}assert.equal(s.registered.length,0);s.bridge.dispose();
});
test('unverified profile installs no IPC',()=>{
 let calls=0;assert.equal(startBridge({profile:{verified:false},runtime:{installIpc:()=>calls++}}),null);assert.equal(calls,0);
});
