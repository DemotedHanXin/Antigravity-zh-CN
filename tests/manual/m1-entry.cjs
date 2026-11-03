'use strict';
// Acceptance harness only. Never copied into a distributed translation runtime.
const fs = require('node:fs');
const path = require('node:path');
const {app, BrowserWindow} = require('electron');
const {captureScript, sanitizeUiEvidence} = require('./m1-ui-audit.cjs');
const {createServiceControl} = require('./m1-service-control.cjs');
const root = process.env.ANTIGRAVITY_M1_LAB;
if (!root || path.resolve(root, 'install/resources/app') !== __dirname) throw new Error('Not an isolated M1 copy');
const evidence = path.join(root, 'evidence');
const packagePath = path.join(__dirname, 'package.json');
const original = fs.readFileSync(path.join(root, 'launch-package.json'));
fs.writeFileSync(packagePath, original); // Restore production bytes before integrity verification.
const entry = JSON.parse(original).main;
// This candidate validates window/IPC wiring first. An in-memory disabled store
// makes this run independent of both real and isolated API configurations.
const bridgeAudit = {mode: 'not_installed', snapshots: 0, authorizedSnapshots: 0, translateCalls: 0, providerCalls: 0};
if (entry === '.dragongirl/bootstrap.cjs' && fs.existsSync(path.join(__dirname, '.dragongirl/profile.json'))) {
  const profile = JSON.parse(fs.readFileSync(path.join(__dirname, '.dragongirl/profile.json'), 'utf8'));
  const controlled = profile.id === 'm1-lab-antigravity-2.28.2-controlled';
  if (!controlled && profile.id !== 'm1-lab-antigravity-2.28.2-navigation') throw new Error('Unexpected lab bridge');
  const mode = process.env.ANTIGRAVITY_M1_TRANSLATION_TEST || 'disabled';
  if (!['disabled', 'success', 'failure'].includes(mode) || (!controlled && mode !== 'disabled')) throw new Error('Unexpected test mode');
  const runtime = require('./.dragongirl/main.cjs');
  const storage = require('./.dragongirl/storage.cjs');
  const candidates = storage.defaultCandidates();
  const service = runtime.createService({store: {async read() {
    const config = storage.defaultConfig();
    if (controlled && mode !== 'disabled') {
      config.enabled = true;
      config.providers.openai.model = 'm1-controlled-fixture';
      config.providers.openai.apiKey = 'fixture-not-a-real-key';
    }
    return {config, dictionary: storage.defaultDictionary(), candidates: JSON.parse(JSON.stringify(candidates))};
  }, async saveCandidates(items, guard, now = Date.now()) {
    if (typeof now === 'function') now = now();
    const state = await this.read();
    if (!state.config.enabled) return {saved: [], candidatesRevision: candidates.revision, status: 'disabled'};
    if (guard.configRevision !== state.config.revision || guard.dictionaryRevision !== state.dictionary.revision) return {saved: [], candidatesRevision: candidates.revision, status: 'stale'};
    const saved = [];
    for (const {source, translation} of items) {
      if (source !== 'Automations' || translation !== '自动化（测试译文）' || guard.epochs[source] !== (candidates.epochs[source] || 0)) continue;
      if (!Object.prototype.hasOwnProperty.call(candidates.entries, source)) {
        candidates.entries[source] = {translation, createdAt: now, expiresAt: now + 604800000, context: 'ui'}; candidates.revision++;
      }
      saved.push({source, ...candidates.entries[source]});
    }
    return {saved, candidatesRevision: candidates.revision, status: 'ok'};
  }}, providerTranslate: async items => {
    if (!controlled || mode === 'disabled') throw new Error('AI disabled in navigation acceptance');
    if (!Array.isArray(items) || !items.length || items.some(item => item.text !== 'Automations')) throw new Error('Unexpected fixture source');
    bridgeAudit.providerCalls++;
    if (mode === 'failure') throw new Error('Controlled provider failure');
    return items.map(item => ({id: item.id, text: '自动化（测试译文）'}));
  }});
  const snapshot = service.snapshot;
  service.snapshot = async () => { bridgeAudit.authorizedSnapshots++; return snapshot(); };
  const originalInstall = runtime.installIpc;
  runtime.installIpc = ({ipcMain}) => {
    const auditedIpc = {handle(channel, handler) { ipcMain.handle(channel, async (...args) => {
      if (channel === 'dragongirl:v1:snapshot') bridgeAudit.snapshots++;
      if (channel === 'dragongirl:v1:translate') bridgeAudit.translateCalls++;
      return handler(...args);
    }); }, removeHandler: channel => ipcMain.removeHandler(channel)};
    return originalInstall({ipcMain: auditedIpc, service});
  };
  bridgeAudit.mode = controlled ? `controlled-${mode}` : 'navigation-only-ai-disabled';
}
app.setName('Antigravity M1 Lab');
for (const [key, relative] of Object.entries({home:'home',appData:'roaming',userData:'electron',sessionData:'session',logs:'logs',temp:'temp'})) {
  const directory = path.join(root, relative); fs.mkdirSync(directory, {recursive:true}); app.setPath(key, directory);
}
fs.writeFileSync(path.join(evidence, 'startup.json'), JSON.stringify({versions:process.versions,home:require('node:os').homedir(),userData:app.getPath('userData'),appData:app.getPath('appData'),entry},null,2));
// Original startup registers a protocol and checks for updates: disable ONLY in this lab.
app.isDefaultProtocolClient = () => true;
app.setAsDefaultProtocolClient = () => false;
const updater = require('./node_modules/electron-updater').autoUpdater;
updater.autoDownload = false; updater.autoInstallOnAppQuit = false;
updater.checkForUpdates = async () => null;
updater.quitAndInstall = () => { throw new Error('Updates disabled in M1 lab'); };
if (process.env.ANTIGRAVITY_M1_LOGIN !== '1') app.on('session-created', session => session.webRequest.onBeforeRequest((details, callback) => {
  const u = new URL(details.url);
  callback({cancel: ['http:','https:','ws:','wss:'].includes(u.protocol) && !['127.0.0.1','localhost'].includes(u.hostname)});
}));
let preloadErrors = 0;
app.on('web-contents-created', (_event, wc) => {
  wc.on('preload-error', () => { preloadErrors++; });
});
function localService() {
  const cached = require.cache[path.join(__dirname, 'dist/languageServer.js')];
  if (!cached?.loaded) return null;
  const ls = cached.exports, child = ls.getLsProcess?.(), port = ls.getLsPort?.();
  const binary = path.resolve(__dirname, '../bin/language_server.exe');
  if (ls.LS_BINARY !== binary || !child || child.spawnfile !== binary || child.killed ||
      child.exitCode !== null || child.signalCode !== null || !Number.isInteger(child.pid) || child.pid < 1 ||
      !Number.isInteger(port) || port < 1 || port > 65535) return null;
  return {child, port, origin: `https://127.0.0.1:${port}`};
}
let capturing = false;
const serviceControl = createServiceControl({root, appRoot: __dirname, appPid: process.pid,
  getService: localService, getWindows: () => BrowserWindow.getAllWindows(),
  getHubWindows: () => {
    const cached = require.cache[path.join(__dirname, 'dist/utils.js')];
    return cached?.loaded ? cached.exports.getHubWindows?.() || [] : [];
  }, getAudit: () => bridgeAudit, isBusy: () => capturing});
async function captureRequested() {
  if (capturing) return;
  const requestFile = path.join(root, 'capture-request.json');
  let request, requestRaw;
  try {
    const stat = fs.lstatSync(requestFile);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 256) return;
    requestRaw = fs.readFileSync(requestFile, 'utf8');
    request = JSON.parse(requestRaw);
    if (!request || Object.keys(request).sort().join(',') !== 'id,schemaVersion' ||
        request.schemaVersion !== 1 || typeof request.id !== 'string' || !/^[a-f0-9]{32}$/.test(request.id)) return;
  } catch (_) { return; }
  capturing = true;
  const target = path.join(evidence, `ui-${request.id}.json`);
  try {
    // A successful write before an interrupted unlink must never be overwritten.
    if (!fs.existsSync(target)) {
      const service = localService();
      const report = {schemaVersion: 1, requestId: request.id, capturedAt: new Date().toISOString(),
        kind: 'fixed-ui-structure-only', status: service ? 'no_eligible_window' : 'service_unavailable',
        preloadErrors, bridge: {...bridgeAudit}, lifecycle: serviceControl.snapshot(), windows: []};
      if (service) for (const win of BrowserWindow.getAllWindows()) {
        const wc = win.webContents;
        if (win.isDestroyed() || win.getParentWindow() || wc.isDestroyed() || wc.getType() !== 'window') continue;
        let url;
        try { url = new URL(wc.getURL()); } catch (_) { continue; }
        if (url.origin !== service.origin || url.username || url.password) continue;
        const prefs = wc.getLastWebPreferences();
        if (prefs.contextIsolation !== true || prefs.sandbox !== true || prefs.nodeIntegration !== false) continue;
        try {
          const ui = sanitizeUiEvidence(await wc.executeJavaScript(captureScript()));
          const live = localService();
          if (!live || live.child !== service.child || live.port !== service.port || wc.isDestroyed() || wc.getURL() !== url.href) continue;
          report.windows.push({windowId: wc.id, port: service.port, security: {contextIsolation: true,
            sandbox: true, nodeIntegration: false, preloadReported: Object.hasOwn(prefs, 'preload'),
            preloadMatches: Object.hasOwn(prefs, 'preload') ? prefs.preload === path.join(__dirname, 'dist/preload.js') : null}, ui});
        } catch (_) { report.status = 'capture_failed'; }
      }
      if (report.windows.length) report.status = 'ok';
      const latest = serviceControl.snapshot();
      if (JSON.stringify(latest) !== JSON.stringify(report.lifecycle)) {
        report.windows = []; report.status = 'service_changed'; report.lifecycle = latest;
      }
      fs.writeFileSync(target, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
    }
    const currentRequest = fs.lstatSync(requestFile);
    if (currentRequest.isFile() && !currentRequest.isSymbolicLink() && currentRequest.size <= 256 &&
        fs.readFileSync(requestFile, 'utf8') === requestRaw) fs.unlinkSync(requestFile);
  } catch (_) { /* Keep the pending marker for diagnosis; never log page exceptions. */ }
  finally { capturing = false; }
}
const stop = setInterval(async () => {
  if (!fs.existsSync(path.join(root, 'stop'))) {
    await captureRequested();
    if (!capturing && !fs.existsSync(path.join(root, 'capture-request.json'))) serviceControl.handleRequest();
    return;
  }
  clearInterval(stop);
  try { await require('./dist/languageServer.js').killLanguageServer(); } finally { app.exit(0); }
}, 500);
const originalModule = require(path.resolve(__dirname, entry));
// require.main remains this development wrapper; the production bootstrap's
// normal CLI guard does not run when required from here.
if (entry === '.dragongirl/bootstrap.cjs') originalModule.launch();
