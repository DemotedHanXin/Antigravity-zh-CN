'use strict';
const test=require('node:test'), assert=require('node:assert/strict');
const {EventEmitter}=require('node:events');
const path=require('node:path');
const {startBridge,verifyInstallation}=require('../../localization_runtime/bootstrap.cjs');
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
 for(const bad of [{preload:'/wrong.js'},{preload:undefined},{contextIsolation:false},{sandbox:false},{nodeIntegration:true}]){const s=setup(),wc=s.window(bad);s.app.emit('web-contents-created',{},wc);wc.emit('did-finish-load');assert.equal(s.registered.length,0);s.bridge.dispose();}
});
test('wrong exact URL and webview never trusted',()=>{
 const s=setup();for(const kind of ['url','webview']){const wc=s.window();if(kind==='url')wc.getURL=()=> 'https://fixture.invalid/ui/extra';else wc.getType=()=> 'webview';s.app.emit('web-contents-created',{},wc);wc.emit('did-finish-load');}assert.equal(s.registered.length,0);s.bridge.dispose();
});
test('unverified profile installs no IPC',()=>{
 let calls=0;assert.equal(startBridge({profile:{verified:false},runtime:{installIpc:()=>calls++}}),null);assert.equal(calls,0);
});

function hubSetup(environment = {}, switches = []) {
  const appRoot = path.resolve('fixture/resources/app'), app = new EventEmitter();
  app.commandLine = {hasSwitch: name => switches.includes(name), getSwitchValue: name => switches.includes(name) ? 'Ubuntu' : ''};
  const binary = path.resolve(appRoot, '../bin/language_server.exe');
  let proc = {pid: 123, exitCode: null, signalCode: null, killed: false, spawnfile: binary}, port = 23456;
  const ls = {LS_BINARY: binary, getLsProcess: () => proc, getLsPort: () => port};
  const cached = {loaded: true, exports: ls};
  const moduleCache = {[path.resolve(appRoot, 'dist/languageServer.js')]: cached};
  const profile = {verified: true, moduleType: 'commonjs', main: 'dist/main.js', preload: 'dist/preload.js', windowBinding: {kind: 'antigravity-local-hub-v1', paths: ['/onboarding']}};
  const registered = [], owners = new Map(); let revoked = 0;
  const bridge = startBridge({electron: {app, ipcMain: {}, BrowserWindow: {fromWebContents: wc => owners.get(wc)}},
    profile, appRoot, environment, moduleCache, runtime: {installIpc: () => ({
      registerTrustedWindow(wc, url, guard) { registered.push({wc, url, guard}); return () => revoked++; }, dispose() {},
    })}});
  function window() {
    const wc = new EventEmitter(); wc.url = `https://127.0.0.1:${port}/`; wc.isDestroyed = () => false;
    wc.getURL = () => wc.url; wc.getType = () => 'window';
    wc.getLastWebPreferences = () => ({preload: path.join(appRoot, 'dist/preload.js'), contextIsolation: true, sandbox: true, nodeIntegration: false});
    const win = {webContents: wc, isDestroyed: () => false, getParentWindow: () => null};
    owners.set(wc, win); app.emit('web-contents-created', {}, wc);
    return win;
  }
  const register = (win, url = win.webContents.url) => bridge.registerHubWindow(win, url, path.join(appRoot, 'dist/preload.js'));
  const load = win => {win.webContents.url = `https://127.0.0.1:${port}/onboarding`; win.webContents.emit('did-finish-load');};
  return {bridge, window, register, load, registered, ls, cached, owners, app, profile, appRoot, binary,
    process: () => proc, replaceProcess: value => {proc = value;}, setPort: value => {port = value;}, revoked: () => revoked};
}

test('dynamic service origin alone cannot authorize an unregistered window', () => {
  const s = hubSetup(), win = s.window(), unrelated = s.window();
  s.load(unrelated); assert.equal(s.registered.length, 0);
  assert.equal(s.register(win), true);
  assert.equal(s.registered.length, 0);
  win.webContents.emit('did-finish-load'); assert.equal(s.registered.length, 0); // Root is not a reviewed page.
  s.load(win); assert.equal(s.registered.length, 1);
  assert.equal(s.registered[0].guard(), true);
  s.bridge.dispose(); assert.equal(s.registered[0].guard(), false);
  assert.equal(win.webContents.listenerCount('did-finish-load'), 0);
});

test('Electron 44 omitted preload requires exact evidence from the registered factory', () => {
  const s = hubSetup(), win = s.window(), unrelated = s.window();
  const prefs = {contextIsolation: true, sandbox: true, nodeIntegration: false};
  win.webContents.getLastWebPreferences = () => prefs;
  unrelated.webContents.getLastWebPreferences = () => prefs;
  assert.equal(s.bridge.registerHubWindow(win, win.webContents.url), false);
  assert.equal(s.bridge.registerHubWindow(win, win.webContents.url, path.join(s.appRoot, 'wrong.js')), false);
  assert.equal(s.register(win), true); s.load(win); assert.equal(s.registered.length, 1);
  s.load(unrelated); assert.equal(s.registered.length, 1);
  assert.equal(s.registered[0].guard(), true);
  prefs.preload = path.join(s.appRoot, 'wrong.js'); assert.equal(s.registered[0].guard(), false);
  prefs.preload = undefined; assert.equal(s.registered[0].guard(), false);
  delete prefs.preload; assert.equal(s.registered[0].guard(), true);
  s.bridge.dispose();
});

test('SPA main-frame navigation binds only an exact reviewed path without query or fragment', () => {
  const s = hubSetup(), win = s.window(), wc = win.webContents;
  assert.equal(s.register(win), true);
  wc.emit('did-finish-load'); assert.equal(s.registered.length, 0);
  const reviewed = 'https://127.0.0.1:23456/onboarding';
  wc.emit('did-start-navigation', {}, reviewed, true, true); wc.url = reviewed;
  wc.emit('did-navigate-in-page', {}, reviewed, false); assert.equal(s.registered.length, 0);
  wc.emit('did-navigate-in-page', {}, reviewed, true); assert.equal(s.registered.length, 1);
  for (const url of [reviewed + '?token=x', reviewed + '#x', reviewed + '/',
    'https://127.0.0.1:23456/other', 'https://localhost:23456/onboarding', 'https://127.0.0.1:23457/onboarding']) {
    wc.emit('did-start-navigation', {}, url, true, true); wc.url = url;
    wc.emit('did-navigate-in-page', {}, url, true); assert.equal(s.registered.length, 1);
  }
  wc.emit('did-start-navigation', {}, reviewed, true, true); wc.url = reviewed;
  wc.emit('did-navigate-in-page', {}, reviewed, true); assert.equal(s.registered.length, 2);
  assert.ok(s.revoked() >= 1); s.bridge.dispose();
  assert.equal(wc.listenerCount('did-navigate-in-page'), 0);
});

test('dynamic bindings require a bounded exact route list and the audited preload', () => {
  for (const paths of [undefined, [], ['/onboarding', '/onboarding'], ['//other'], ['/../other'],
    ['/onboarding?x'], ['/onboarding#x'], ['/on%62oarding'], ['https://host/'], Array(33).fill('/onboarding')]) {
    let calls = 0;
    const profile = {verified: true, moduleType: 'commonjs', preload: 'dist/preload.js', windowBinding: {kind: 'antigravity-local-hub-v1', paths}};
    assert.equal(startBridge({profile, runtime: {installIpc: () => calls++}}), null);
    assert.equal(calls, 0);
  }
  for (const change of [p => p.preload = 'dist/other.js', p => p.windowBinding.allowAny = true]) {
    const profile = {verified: true, moduleType: 'commonjs', preload: 'dist/preload.js', windowBinding: {kind: 'antigravity-local-hub-v1', paths: ['/onboarding']}};
    change(profile); assert.equal(startBridge({profile}), null);
  }
});

test('hub registration requires exact origin, live local process and actual top-level BrowserWindow', () => {
  const cases = [
    s => s.cached.loaded = false,
    s => s.ls.LS_BINARY = path.join(s.appRoot, 'wrong.exe'),
    s => s.process().spawnfile = path.join(s.appRoot, 'wsl.exe'),
    s => s.process().exitCode = 0,
    s => s.process().signalCode = 'SIGTERM',
    s => s.process().killed = true,
    s => s.process().pid = 0,
    s => s.setPort(0),
    s => s.setPort(65536),
    (s, win) => win.getParentWindow = () => ({}),
    (s, win) => s.owners.set(win.webContents, {}),
    (s, win) => win.webContents.getType = () => 'webview',
    (s, win) => win.webContents.getLastWebPreferences = () => ({contextIsolation: true, sandbox: false, nodeIntegration: false, preload: path.join(s.appRoot, 'dist/preload.js')}),
  ];
  for (const change of cases) {
    const s = hubSetup(), win = s.window(); change(s, win);
    assert.equal(s.register(win), false);
    win.webContents.emit('did-finish-load'); assert.equal(s.registered.length, 0); s.bridge.dispose();
  }
  for (const url of ['https://localhost:23456/', 'https://127.0.0.1:23457/', 'http://127.0.0.1:23456/',
    'https://127.0.0.1:23456/?q=1', 'https://127.0.0.1:23456/other', 'https://127.0.0.1:23456/#other']) {
    const s = hubSetup(), win = s.window(); assert.equal(s.register(win, url), false); s.bridge.dispose();
  }
});

test('developer, WSL, external service and unsandboxed launch modes are excluded', () => {
  for (const [environment, switches] of [
    [{DEV_URL: 'https://example.invalid'}, []], [{WSL_DISTRO: 'Ubuntu'}, []],
    [{ANTIGRAVITY_WSL_DISTRO: 'Ubuntu'}, []], [{JETSKI_LS_PORT: '23456'}, []],
    [{ELECTRON_OZONE_PLATFORM_HINT: 'headless'}, []], [{}, ['no-sandbox']], [{}, ['wsl-distro']],
  ]) {
    const s = hubSetup(environment, switches), win = s.window();
    assert.equal(s.register(win), false); s.bridge.dispose();
  }
  const s = hubSetup({ANTIGRAVITY_WSL_DISTRO: 'Ubuntu'}, ['wsl-distro']), win = s.window();
  s.app.commandLine.getSwitchValue = () => '';
  assert.equal(s.register(win), true);
  s.bridge.dispose();
});

test('service lifetime guard expires before navigation and renewed trust binds to the new process', () => {
  const s = hubSetup(), win = s.window(), wc = win.webContents;
  assert.equal(s.register(win), true); s.load(win);
  const old = s.registered[0]; assert.equal(old.guard(), true);
  s.process().exitCode = 0; assert.equal(old.guard(), false);
  s.replaceProcess({pid: 124, exitCode: null, signalCode: null, killed: false, spawnfile: s.binary});
  assert.equal(old.guard(), false); // Even a replacement at the same port is new.
  s.setPort(23457); wc.emit('did-start-navigation', {}, 'https://127.0.0.1:23457/', false, true);
  s.load(win);
  assert.equal(s.registered.length, 2); assert.equal(s.registered[1].guard(), true);
  assert.ok(s.revoked() >= 1); s.bridge.dispose();
});

test('installed byte and external resource fingerprints are enforced before bridge loading', t => {
  const fs = require('node:fs'), os = require('node:os'), crypto = require('node:crypto');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'bridge-integrity-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const appRoot = path.join(root, 'app'); fs.mkdirSync(appRoot);
  const profile = {windowBinding: {kind: 'antigravity-local-hub-v1'}, main: 'dist/main.js', preload: 'dist/preload.js', runtimeIntegrity: {}, resourcesFiles: {}};
  const names = ['package.json', profile.main, profile.preload, 'dist/utils.js', 'dist/languageServer.js',
    'dist/constants.js', '.dragongirl/bootstrap.cjs', '.dragongirl/main.cjs', '.dragongirl/providers.cjs',
    '.dragongirl/network.cjs', '.dragongirl/storage.cjs', '.dragongirl/credentials.cjs'];
  function add(base, name, manifest) {
    const file = path.join(base, name), content = 'fixture: ' + name;
    fs.mkdirSync(path.dirname(file), {recursive: true}); fs.writeFileSync(file, content);
    manifest[name] = crypto.createHash('sha256').update(content).digest('hex');
  }
  for (const name of names) add(appRoot, name, profile.runtimeIntegrity);
  add(root, 'bin/language_server.exe', profile.resourcesFiles);
  assert.equal(verifyInstallation(appRoot, profile), true);
  assert.throws(() => verifyInstallation(appRoot, {...profile, runtimeIntegrity: {}}), /Missing installation/);
  assert.throws(() => verifyInstallation(appRoot, {...profile, resourcesFiles: {}}), /Missing installation/);
  fs.writeFileSync(path.join(root, 'bin/language_server.exe'), 'changed');
  assert.throws(() => verifyInstallation(appRoot, profile), /Installation changed/);
  add(root, 'bin/language_server.exe', profile.resourcesFiles);
  fs.writeFileSync(path.join(appRoot, 'dist/preload.js'), 'changed');
  assert.throws(() => verifyInstallation(appRoot, profile), /Installation changed/);
  assert.throws(() => verifyInstallation(appRoot, {runtimeIntegrity: {'../outside': 'a'.repeat(64)}}), /Invalid integrity path/);
});
