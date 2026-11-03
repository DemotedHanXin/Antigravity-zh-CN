'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const path = require('node:path');
const fs = require('node:fs');
const {EventEmitter} = require('node:events');
const audit = require('../manual/m1-ui-audit.cjs');
const {createServiceControl} = require('../manual/m1-service-control.cjs');
const source = fs.readFileSync(path.join(__dirname, '../manual/m1-entry.cjs'), 'utf8');

function harness(entry = 'dist/main.js', candidate = false, mode = 'disabled') {
  // In-memory filesystem/Electron stubs: these tests never launch an application.
  const root = path.resolve('.m1-lab-fixture'), appRoot = path.join(root, 'install/resources/app');
  const files = new Map([[path.join(root, 'launch-package.json'), JSON.stringify({main: entry})]]);
  const descriptors = new Map(); let descriptor = 0;
  const writes = [];
  let serviceOptions, harnessService;
  if (candidate) files.set(path.join(appRoot, '.dragongirl/profile.json'), JSON.stringify({id: `m1-lab-antigravity-2.28.2-${candidate === 'controlled' ? 'controlled' : 'navigation'}`}));
  const fakeFs = {readFileSync: p => { if (!files.has(p)) throw new Error('ENOENT'); return files.get(p); },
    mkdirSync() {}, existsSync: p => files.has(p),
    writeFileSync(p, data, opts) { p = descriptors.get(p) || p; if (opts?.flag === 'wx' && files.has(p)) throw new Error('EEXIST'); files.set(p, data); writes.push(p); },
    openSync(p) { if (files.has(p)) throw new Error('EEXIST'); files.set(p, ''); descriptors.set(++descriptor, p); return descriptor; },
    closeSync(fd) { descriptors.delete(fd); }, fsyncSync() {},
    unlinkSync: p => files.delete(p), lstatSync(p) {
      if ([root, path.join(root, 'evidence')].includes(p)) return {isFile:()=>false,isDirectory:()=>true,isSymbolicLink:()=>false};
      if (!files.has(p)) throw Object.assign(new Error('ENOENT'),{code:'ENOENT'});
      return {isFile: () => true, isSymbolicLink: () => false, size: String(files.get(p)).length};
    }};
  const app = new EventEmitter(); Object.assign(app, {setName() {}, setPath() {}, getPath: () => root, exit() {}});
  const wc = new EventEmitter(); let executions = 0, launches = 0, originalLoads = 0;
  const ui = {schemaVersion: 1, route: {path: '/', hasQuery: false, hasHash: false,
    query: {known: [], unknownKeys: 0, truncated: false}}, rootFound: true, truncated: false, matches: []};
  Object.assign(wc, {id: 1, isDestroyed: () => false, getType: () => 'window', getURL: () => 'https://127.0.0.1:43210/',
    getLastWebPreferences: () => ({contextIsolation: true, sandbox: true, nodeIntegration: false}),
    async executeJavaScript(script) { executions++; assert.equal(script, audit.captureScript()); return ui; },
    capturePage() { throw new Error('Screenshots are not allowed'); }});
  const win = {webContents: wc, isDestroyed: () => false, getParentWindow: () => null};
  const binary = path.resolve(appRoot, '../bin/language_server.exe');
  let child = {pid: 123, spawnfile: binary, killed: false, exitCode: null, signalCode: null};
  let kills = 0, stops = 0;
  child.kill = signal => { assert.equal(signal,'SIGTERM'); kills++; return true; };
  const ls = {LS_BINARY: binary, getLsProcess: () => child, getLsPort: () => 43210,
    async killLanguageServer() { stops++; }};
  const localRequire = name => {
    if (name === 'electron') return {app, BrowserWindow: {getAllWindows: () => [win]}};
    if (name === 'node:path') return path;
    if (name === 'node:fs') return fakeFs;
    if (name === 'node:os') return {homedir: () => root};
    if (name === './node_modules/electron-updater') return {autoUpdater: {}};
    if (name === './m1-ui-audit.cjs') return audit;
    if (name === './m1-service-control.cjs') return {createServiceControl: options => createServiceControl({...options, fs:fakeFs, newSessionId:()=> 'b'.repeat(32)})};
    if (name === './dist/languageServer.js') return ls;
    if (name === './.dragongirl/storage.cjs') return require('../../localization_runtime/storage.cjs');
    if (name === './.dragongirl/main.cjs') return {createService(options) {
      serviceOptions = options; harnessService = {snapshot: async () => ({enabled: false})}; return harnessService;
    }, installIpc() {}};
    if (name === path.resolve(appRoot, entry)) { originalLoads++; return {launch() { launches++; }}; }
    throw new Error('Unexpected require');
  };
  localRequire.cache = {[path.join(appRoot, 'dist/languageServer.js')]: {loaded: true, exports: ls},
    [path.join(appRoot,'dist/utils.js')]: {loaded:true,exports:{getHubWindows:()=>[win]}}};
  let interval;
  vm.runInNewContext(source, {require: localRequire, __dirname: appRoot,
    process: {pid: 50, env: {ANTIGRAVITY_M1_LAB: root, ANTIGRAVITY_M1_LOGIN: '1', ANTIGRAVITY_M1_TRANSLATION_TEST: mode}, versions: {}}, URL,
    setInterval(fn) { interval = fn; return 1; }, clearInterval() {}}, {timeout: 1000});
  app.emit('web-contents-created', null, wc);
  const id = 'a'.repeat(32), requestFile = path.join(root, 'capture-request.json');
  const resultFile = path.join(root, 'evidence', `ui-${id}.json`);
  return {files, writes, wc, ui, root, tick: () => interval(), requestFile, resultFile,
    replaceChild() { child = {...child}; }, get kills() { return kills; }, get stops() { return stops; },
    request() { files.set(requestFile, JSON.stringify({schemaVersion: 1, id})); },
    get serviceOptions() { return serviceOptions; },
    get service() { return harnessService; },
    get executions() { return executions; }, get launches() { return launches; }, get originalLoads() { return originalLoads; }};
}

test('launch and page loading never collect UI without a manual request', async () => {
  const h = harness(); h.wc.emit('did-finish-load'); await h.tick();
  assert.equal(h.executions, 0); assert.equal(h.originalLoads, 1); assert.equal(h.launches, 0);
  assert.equal(h.writes.length, 2); // original package restoration and startup metadata only
});

test('user capture request produces one sanitized receipt and consumes marker', async () => {
  const h = harness(); h.request(); await h.tick(); await h.tick();
  assert.equal(h.executions, 1); assert.equal(h.files.has(h.requestFile), false);
  const result = JSON.parse(h.files.get(h.resultFile));
  assert.equal(result.status, 'ok'); assert.equal(result.windows[0].security.preloadReported, false);
  assert.equal(result.windows[0].security.preloadMatches, null);
  assert.equal(result.windows[0].ui.route.path, '/');
  assert.deepEqual(result.lifecycle, {sessionId:'b'.repeat(32),appPid:50,service:{generation:1,pid:123,port:43210}});
});

test('capture that crosses a service replacement cannot combine old window evidence with a new lifecycle', async () => {
  const h=harness();
  h.wc.executeJavaScript=async()=>{h.replaceChild();return h.ui;};
  h.request();await h.tick();
  const report=JSON.parse(h.files.get(h.resultFile));
  assert.equal(report.status,'service_changed');assert.deepEqual(report.windows,[]);
  assert.equal(report.lifecycle.service.generation,2);
});

test('capture consumption preserves a concurrently replaced request marker', async () => {
  const h=harness();const replacement=JSON.stringify({schemaVersion:1,id:'c'.repeat(32)});
  h.wc.executeJavaScript=async()=>{h.files.set(h.requestFile,replacement);return h.ui;};
  h.request();await h.tick();
  assert.equal(h.files.get(h.requestFile),replacement);
  assert.equal(JSON.parse(h.files.get(h.resultFile)).status,'ok');
});

function restartRequest(h) {
  const request={schemaVersion:1,id:'d'.repeat(32),sessionId:'b'.repeat(32),
    expectedGeneration:1,expectedPid:123,expectedPort:43210,expectedWindowId:1};
  h.files.set(path.join(h.root,'restart-service-request.json'),JSON.stringify(request));
  return path.join(h.root,'evidence',`service-restart-${request.id}.json`);
}

test('entry rejects a restart if no authorized snapshot reached the controlled service', async () => {
  const h=harness('.dragongirl/bootstrap.cjs','controlled','success');
  h.request();await h.tick(); // baseline, still not sufficient without an authorized snapshot
  await h.serviceOptions.store.read();
  // Capture generation is available, but no main IPC snapshot reached this mock service.
  const receipt=restartRequest(h);await h.tick();
  assert.equal(h.kills,0);assert.equal(JSON.parse(h.files.get(receipt)).status,'denied');
  assert.equal(h.executions,1);
});

test('entry signals the controlled service only after a manual request and prior authorization', async () => {
  const h=harness('.dragongirl/bootstrap.cjs','controlled','success');
  await h.service.snapshot();
  h.request();await h.tick();
  const before=JSON.parse(h.files.get(h.resultFile));assert.equal(before.bridge.authorizedSnapshots,1);
  const receipt=restartRequest(h);await h.tick();await h.tick();
  assert.equal(h.kills,1);assert.equal(JSON.parse(h.files.get(receipt)).status,'signal_sent');
  assert.equal(h.executions,1); // Restart itself never requests DOM evidence.
});

test('pending asynchronous capture and stop marker cannot dispatch a service signal', async () => {
  const h=harness('.dragongirl/bootstrap.cjs','controlled','success');
  await h.service.snapshot();
  let resolve;
  h.wc.executeJavaScript=()=>new Promise(done=>{resolve=done;});
  h.request();restartRequest(h);const pending=h.tick();
  await h.tick();assert.equal(h.kills,0);
  h.files.set(path.join(h.root,'stop'),'stop');
  await h.tick();assert.equal(h.stops,1);assert.equal(h.kills,0);
  resolve(h.ui);await pending;assert.equal(h.kills,0);
});

test('wrong origin or unsafe preferences prevent renderer execution', async () => {
  for (const override of [{getURL: () => 'https://127.0.0.1:43211/'},
    {getLastWebPreferences: () => ({contextIsolation: false, sandbox: true, nodeIntegration: false})}]) {
    const h = harness(); Object.assign(h.wc, override); h.request(); await h.tick();
    assert.equal(h.executions, 0);
    assert.equal(JSON.parse(h.files.get(h.resultFile)).status, 'no_eligible_window');
  }
});

test('query-bearing user capture persists only sanitized route metadata', async () => {
  const h = harness();
  h.wc.getURL = () => 'https://127.0.0.1:43210/?view=settings&tab=private-secret';
  Object.assign(h.ui, {rootFound: false});
  Object.assign(h.ui.route, {hasQuery: true, query: {known: [
    {key: 'view', value: 'settings'}, {key: 'tab', value: null, raw: 'private-secret'}
  ], unknownKeys: 0, truncated: false}});
  h.request(); await h.tick();
  const result = JSON.parse(h.files.get(h.resultFile));
  assert.equal(result.status, 'ok');
  assert.equal(result.windows[0].ui.route.query.known[1].value, null);
  assert.doesNotMatch(h.files.get(h.resultFile), /private-secret|https:/);
});

test('renderer exceptions and arbitrary payload fields are not persisted', async () => {
  const h = harness(); h.wc.executeJavaScript = async () => { throw new Error('secret-token'); };
  h.request(); await h.tick(); assert.doesNotMatch(h.files.get(h.resultFile), /secret-token/);
  assert.equal(JSON.parse(h.files.get(h.resultFile)).status, 'capture_failed');
  const g = harness(); g.ui.html = 'private body'; g.request(); await g.tick();
  assert.doesNotMatch(g.files.get(g.resultFile), /private body/);
});

test('previous receipt is never overwritten or collected a second time', async () => {
  const h = harness(); h.files.set(h.resultFile, 'previous'); h.request(); await h.tick();
  assert.equal(h.executions, 0); assert.equal(h.files.get(h.resultFile), 'previous');
});

test('wrapped production bootstrap explicitly launches exactly once', () => {
  const h = harness('.dragongirl/bootstrap.cjs');
  assert.equal(h.originalLoads, 1); assert.equal(h.launches, 1);
});

test('navigation candidate uses a disabled memory store and rejects provider calls', async () => {
  const h = harness('.dragongirl/bootstrap.cjs', true);
  const state = await h.serviceOptions.store.read();
  assert.equal(state.config.enabled, false); assert.equal(state.config.autoSave, false);
  assert.equal(state.config.providers.openai.apiKey, '');
  assert.deepEqual(state.dictionary.entries, {});
  await assert.rejects(h.serviceOptions.providerTranslate(), /AI disabled/);
  h.request(); await h.tick();
  assert.equal(JSON.parse(h.files.get(h.resultFile)).bridge.mode, 'navigation-only-ai-disabled');
  assert.equal(h.launches, 1);
});

test('controlled modes exercise the real service without disk configuration or network', async () => {
  const {createService} = require('../../localization_runtime/main.cjs');
  for (const mode of ['success', 'failure', 'disabled']) {
    const h = harness('.dragongirl/bootstrap.cjs', 'controlled', mode);
    const service = createService(h.serviceOptions);
    try {
      const snapshot = await service.snapshot();
      const response = await service.translate({version: 1, configRevision: snapshot.configRevision,
        dictionaryRevision: snapshot.dictionaryRevision, candidatesRevision: snapshot.candidatesRevision, cacheEpoch: snapshot.cacheEpoch,
        items: [{id: 'fixture', text: 'Automations', safeContextKind: 'navigation'}]});
      assert.equal(response.translations.length, 0);
      if (mode === 'success') {
        assert.equal(response.status, 'candidates_updated');
        assert.equal((await service.snapshot()).candidates.Automations.translation, '自动化（测试译文）');
      }
      if (mode === 'disabled') assert.equal(response.status, 'disabled');
      h.request(); await h.tick();
      const result = JSON.parse(h.files.get(h.resultFile));
      assert.equal(result.bridge.mode, 'controlled-' + mode);
      assert.equal(result.bridge.providerCalls, mode === 'disabled' ? 0 : 1);
      await assert.rejects(h.serviceOptions.providerTranslate([{id:'x', text:'Private user input'}]));
    } finally { service.close(); }
  }
});

test('non-disabled controlled mode requires the controlled candidate', () => {
  assert.throws(() => harness('.dragongirl/bootstrap.cjs', true, 'success'), /Unexpected test mode/);
});
