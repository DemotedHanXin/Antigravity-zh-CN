'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const {createServiceControl} = require('../manual/m1-service-control.cjs');

function fixture(sessionId = 'b'.repeat(32)) {
  const root = path.resolve('.m1-lab-memory'), appRoot = path.join(root,'install/resources/app');
  const evidence = path.join(root,'evidence'), requestFile = path.join(root,'restart-service-request.json');
  const files = new Map(), fds = new Map(), dirs = new Set([root,evidence]);
  let fd = 0, kills = 0, busy = false, syncs = 0;
  const events = [];
  const fs = {
    existsSync: file => files.has(file) || dirs.has(file),
    lstatSync(file) { if (!files.has(file) && !dirs.has(file)) throw Object.assign(new Error('ENOENT'),{code:'ENOENT'});
      return {isFile:()=>files.has(file),isDirectory:()=>dirs.has(file),isSymbolicLink:()=>false,size:files.get(file)?.length||0}; },
    readFileSync(file) { if (!files.has(file)) throw new Error('ENOENT'); return files.get(file); },
    writeFileSync(file,data,options) { const target=fds.get(file)||file;
      if (options?.flag==='wx' && files.has(target)) throw new Error('EEXIST'); files.set(target,data); },
    openSync(file,flag) { assert.equal(flag,'wx'); if (files.has(file)) throw new Error('EEXIST'); files.set(file,''); fds.set(++fd,file); return fd; },
    fsyncSync() { syncs++; events.push('fsync'); }, closeSync(file) { fds.delete(file); },
    unlinkSync(file) { files.delete(file); }
  };
  const binary = path.resolve(appRoot,'../bin/language_server.exe');
  const kill = signal => { assert.equal(signal,'SIGTERM'); kills++; events.push('kill'); return true; };
  let child = {pid:123,spawnfile:binary,killed:false,exitCode:null,signalCode:null,kill};
  let port=43210;
  const wc = {id:1,isDestroyed:()=>false,getType:()=> 'window',getURL:()=>`https://127.0.0.1:${port}/`,
    getLastWebPreferences:()=>({contextIsolation:true,sandbox:true,nodeIntegration:false})};
  const win = {webContents:wc,isDestroyed:()=>false,getParentWindow:()=>null};
  let windows=[win], hubs=[win];
  const audit={mode:'controlled-success',authorizedSnapshots:1};
  const control=createServiceControl({root,appRoot,appPid:50,fs,newSessionId:sessionId === null ? undefined : () => sessionId,
    getService:()=>({child,port,origin:`https://127.0.0.1:${port}`}),getWindows:()=>windows,
    getHubWindows:()=>hubs,getAudit:()=>audit,isBusy:()=>busy});
  const baseline=control.snapshot();
  const request={schemaVersion:1,id:'a'.repeat(32),sessionId:baseline.sessionId,
    expectedGeneration:baseline.service.generation,expectedPid:123,expectedPort:43210,expectedWindowId:1};
  const result=id=>path.join(evidence,`service-restart-${id}.json`);
  const claim=id=>path.join(evidence,`service-restart-${id}.claim.json`);
  return {root,appRoot,fs,files,events,control,wc,win,audit,request,requestFile,result,claim,
    get child(){return child;},get kills(){return kills;},get syncs(){return syncs;},
    setBusy(value){busy=value;},setWindows(value){windows=value;},setHubs(value){hubs=value;},
    replaceChild(next={}){child={...child,...next};},setPort(value){port=value;},
    queue(change={}){const data={...request,...change};files.set(requestFile,JSON.stringify(data));return data;},
    receipt(id=request.id){return JSON.parse(files.get(result(id)));},
    run(){control.handleRequest();}
  };
}

test('no request cannot kill or create receipts and snapshots contain only bounded lifecycle metadata', () => {
  const f=fixture();f.run();assert.equal(f.kills,0);assert.equal(f.files.size,0);
  assert.deepEqual(f.control.snapshot(),{sessionId:'b'.repeat(32),appPid:50,service:{generation:1,pid:123,port:43210}});
  assert.deepEqual(f.control.snapshot(),f.control.snapshot());
});

test('separate harness lifetimes get fresh random session IDs without writing state', () => {
  const first=fixture(null),second=fixture(null);
  assert.match(first.control.snapshot().sessionId,/^[a-f0-9]{32}$/);
  assert.notEqual(first.control.snapshot().sessionId,second.control.snapshot().sessionId);
  assert.equal(first.files.size,0);assert.equal(second.files.size,0);
});

test('explicit matching request fsyncs its exclusive claim before exactly one child signal', () => {
  const f=fixture();f.queue();f.run();f.run();
  assert.equal(f.kills,1);assert.equal(f.syncs,1);assert.deepEqual(f.events,['fsync','kill']);
  assert.equal(f.files.has(f.requestFile),false);
  const receipt=f.receipt();assert.equal(receipt.status,'signal_sent');
  assert.deepEqual(receipt.before,f.control.snapshot());
  assert.doesNotMatch(JSON.stringify(receipt),/https:|spawnfile|language_server/);
  f.queue({id:'c'.repeat(32)});f.run();assert.equal(f.kills,1);
  assert.equal(f.receipt('c'.repeat(32)).reason,'restart_limit');
});

test('object identity advances generation even when PID and port are reused and stale requests cannot kill', () => {
  const f=fixture();f.replaceChild();
  assert.equal(f.control.snapshot().service.generation,2);
  f.queue();f.run();assert.equal(f.kills,0);assert.equal(f.receipt().reason,'target_changed');
});

test('session target mismatch, unsupported modes, inactive service and unrelated windows fail closed', () => {
  const cases=[
    f=>f.queue({sessionId:'c'.repeat(32)}),f=>f.queue({expectedGeneration:2}),
    f=>f.queue({expectedPid:124}),f=>f.queue({expectedPort:43211}),f=>f.queue({expectedWindowId:2}),
    f=>{f.audit.authorizedSnapshots=0;},
    ...['not_installed','navigation-only-ai-disabled','controlled-disabled','controlled-failure'].map(mode=>f=>{f.audit.mode=mode;}),
    f=>{f.child.pid=50;},f=>{f.child.spawnfile=path.join(f.appRoot,'wrong.exe');},f=>{f.child.exitCode=0;},
    f=>{f.child.killed=true;},f=>{f.child.signalCode='SIGTERM';},f=>{f.child.kill=null;},
    f=>f.setPort(0),f=>f.setPort(65536),f=>f.setHubs([]),f=>f.setWindows([]),
    f=>{f.wc.getURL=()=> 'https://127.0.0.1:43210/?settingsOpen=true';},
    f=>{f.wc.getURL=()=> 'https://127.0.0.1:43210/#fragment';},
    f=>{f.wc.getURL=()=> 'https://localhost:43210/';},
    f=>{f.win.getParentWindow=()=>({});},f=>{f.win.isDestroyed=()=>true;},
    f=>{f.wc.isDestroyed=()=>true;},f=>{f.wc.getType=()=> 'webview';},
    f=>{f.wc.getLastWebPreferences=()=>({contextIsolation:false,sandbox:true,nodeIntegration:false});},
    f=>{f.wc.getLastWebPreferences=()=>({contextIsolation:true,sandbox:false,nodeIntegration:false});},
    f=>{f.wc.getLastWebPreferences=()=>({contextIsolation:true,sandbox:true,nodeIntegration:true});},
    f=>{f.wc.getLastWebPreferences=()=>({contextIsolation:true,sandbox:true,nodeIntegration:false,preload:'wrong'});}
  ];
  for(const change of cases){const f=fixture();f.queue();change(f);f.run();assert.equal(f.kills,0);assert.equal(f.receipt().status,'denied');}
});

test('malformed, excessive and non-regular request files are never executed', () => {
  for(const change of [r=>r.extra='private',r=>r.id='../private',r=>r.schemaVersion=2,r=>r.expectedPid=true,
    r=>r.expectedGeneration=0,r=>r.expectedPort=65536,r=>r.expectedWindowId=Number.MAX_SAFE_INTEGER+1]){
    const f=fixture(),r=f.queue();change(r);f.files.set(f.requestFile,JSON.stringify(r));f.run();
    assert.equal(f.kills,0);assert.equal(f.files.has(f.result(f.request.id)),false);
  }
  for(const raw of ['bad json',' '.repeat(1025)]){const f=fixture();f.files.set(f.requestFile,raw);f.run();assert.equal(f.kills,0);}
  const f=fixture();f.queue();const stat=f.fs.lstatSync;
  f.fs.lstatSync=file=>file===f.requestFile?{isFile:()=>true,isSymbolicLink:()=>true,size:10}:stat(file);
  f.run();assert.equal(f.kills,0);
});

test('stop and in-progress capture take priority over restart requests', () => {
  for(const change of [f=>f.files.set(path.join(f.root,'stop'),'stop'),f=>f.setBusy(true)]){
    const f=fixture();f.queue();change(f);f.run();assert.equal(f.kills,0);assert.equal(f.files.has(f.requestFile),true);
    assert.equal(f.files.has(f.claim(f.request.id)),false);
  }
});

test('existing claim or receipt prevents replay even when the prior receipt is missing', () => {
  for(const name of ['claim','result']){
    const f=fixture();f.queue();const target=f[name](f.request.id);f.files.set(target,'prior');f.run();
    assert.equal(f.kills,0);assert.equal(f.files.get(target),'prior');
    if(name==='claim')assert.equal(f.receipt().status,'already_claimed');
  }
});

test('claim creation or fsync failure cannot signal a child', () => {
  for(const method of ['openSync','fsyncSync']){
    const f=fixture();f.queue();f.fs[method]=()=>{throw new Error('private-disk-error');};f.run();
    assert.equal(f.kills,0);assert.equal(f.files.has(f.requestFile),true);
  }
});

test('restoring disk writes after a failed claim cannot retry the same or a new request', () => {
  for(const method of ['openSync','fsyncSync']){
    const f=fixture();f.queue();const original=f.fs[method];
    f.fs[method]=()=>{throw new Error('temporary write failure');};
    f.run();assert.equal(f.kills,0);assert.equal(f.files.has(f.requestFile),true);
    f.fs[method]=original;
    f.run(); // The still-pending original request must not fire after disk recovery.
    assert.equal(f.kills,0);assert.equal(f.receipt().reason,'restart_limit');
    assert.equal(f.receipt().status,method==='fsyncSync'?'already_claimed':'denied');
    f.queue({id:'c'.repeat(32)});f.run();
    assert.equal(f.kills,0);assert.equal(f.receipt('c'.repeat(32)).reason,'restart_limit');
    assert.equal(f.files.has(f.claim('c'.repeat(32))),false);
  }
});

test('failed signal is recorded without exposing errors or retrying the child', () => {
  for(const fail of [()=>false,()=>{throw new Error('private-process-error');}]){
    const f=fixture();let calls=0;f.child.kill=()=>{calls++;return fail();};f.queue();f.run();f.run();
    assert.equal(calls,1);assert.equal(f.receipt().status,'signal_failed');
    assert.doesNotMatch(f.files.get(f.result(f.request.id)),/private-process/);
  }
});

test('receipt or request-unlink failure cannot repeat a previously issued signal', () => {
  for(const operation of ['receipt','unlink']){
    const f=fixture();f.queue();const write=f.fs.writeFileSync,unlink=f.fs.unlinkSync;
    if(operation==='receipt')f.fs.writeFileSync=(file,...args)=>{if(file===f.result(f.request.id))throw new Error('disk');return write(file,...args);};
    else f.fs.unlinkSync=()=>{throw new Error('locked');};
    f.run();assert.equal(f.kills,1);f.fs.writeFileSync=write;f.fs.unlinkSync=unlink;f.run();assert.equal(f.kills,1);
  }
});

test('state or request changes after durable claim prevent signaling and preserve the new request', () => {
  for(const change of [f=>f.replaceChild(),f=>f.files.set(path.join(f.root,'stop'),'stop'),
    f=>f.queue({id:'c'.repeat(32)})]){
    const f=fixture();f.queue();const sync=f.fs.fsyncSync;f.fs.fsyncSync=()=>{sync();change(f);};f.run();
    assert.equal(f.kills,0);assert.equal(f.receipt().status,'denied');
    if(f.files.has(f.requestFile))assert.equal(JSON.parse(f.files.get(f.requestFile)).id,'c'.repeat(32));
  }
});

test('unsafe evidence directory fails before any signal or claim', () => {
  const f=fixture();f.queue();const stat=f.fs.lstatSync;
  f.fs.lstatSync=file=>file===path.join(f.root,'evidence')?{isDirectory:()=>true,isSymbolicLink:()=>true}:stat(file);
  f.run();assert.equal(f.kills,0);assert.equal(f.files.has(f.claim(f.request.id)),false);
});

test('dangling receipt, claim and stop objects are conflicts rather than absent paths', () => {
  for(const kind of ['result','claim','stop']){
    const f=fixture();f.queue();const target=kind==='stop'?path.join(f.root,'stop'):f[kind](f.request.id);
    const stat=f.fs.lstatSync;
    f.fs.lstatSync=file=>file===target?{isFile:()=>false,isDirectory:()=>false,isSymbolicLink:()=>true,size:0}:stat(file);
    assert.equal(f.fs.existsSync(target),false); // Native existsSync also follows dangling links.
    f.run();assert.equal(f.kills,0);
    if(kind!=='claim')assert.equal(f.files.has(f.claim(f.request.id)),false);
  }
});

test('unreadable stop or receipt paths fail closed instead of assuming absence', () => {
  for(const kind of ['result','stop']){
    const f=fixture();f.queue();const target=kind==='stop'?path.join(f.root,'stop'):f.result(f.request.id);
    const stat=f.fs.lstatSync;
    f.fs.lstatSync=file=>{if(file===target)throw Object.assign(new Error('denied'),{code:'EACCES'});return stat(file);};
    f.run();assert.equal(f.kills,0);assert.equal(f.files.has(f.claim(f.request.id)),false);
  }
});
