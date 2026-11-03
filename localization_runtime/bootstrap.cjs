'use strict';
// Only installed for a reviewed application fingerprint. No page supplies trust.
const path = require('node:path');
const fs = require('node:fs');
const crypto = require('node:crypto');
const LOCAL_HUB = 'antigravity-local-hub-v1';
let activeBridge = null;

function samePath(a, b) {
  if (typeof a !== 'string' || !path.isAbsolute(a)) return false;
  const left = path.resolve(a), right = path.resolve(b);
  return process.platform === 'win32' ? left.toLowerCase() === right.toLowerCase() : left === right;
}
function regularFile(root, relative) {
  if (typeof relative !== 'string' || !relative || relative.includes('\\') || relative.includes(':') ||
      path.isAbsolute(relative) || relative.split('/').some(p => !p || p === '.' || p === '..')) throw new Error('Invalid integrity path');
  let target = root;
  const parts = relative.split('/');
  for (let i = 0; i < parts.length; i++) {
    target = path.join(target, parts[i]);
    const info = fs.lstatSync(target);
    if (info.isSymbolicLink() || (i === parts.length - 1 ? !info.isFile() : !info.isDirectory())) throw new Error('Unsafe integrity file');
  }
  return target;
}
function fileDigest(file) {
  const fd = fs.openSync(file, 'r'), hash = crypto.createHash('sha256'), buffer = Buffer.alloc(1024 * 1024);
  try { let n; while ((n = fs.readSync(fd, buffer, 0, buffer.length, null))) hash.update(buffer.subarray(0, n)); }
  finally { fs.closeSync(fd); }
  return hash.digest('hex');
}
function verifyInstallation(appRoot, profile) {
  const dynamic = profile.windowBinding?.kind === LOCAL_HUB;
  const required = dynamic ? ['package.json', profile.main, profile.preload, 'dist/utils.js',
    'dist/languageServer.js', 'dist/constants.js', '.dragongirl/bootstrap.cjs', '.dragongirl/main.cjs',
    '.dragongirl/providers.cjs', '.dragongirl/network.cjs', '.dragongirl/storage.cjs'] : [];
  if (dynamic && (!profile.runtimeIntegrity || !profile.resourcesFiles ||
      !required.every(name => Object.hasOwn(profile.runtimeIntegrity, name)) ||
      !Object.hasOwn(profile.resourcesFiles, 'bin/language_server.exe'))) throw new Error('Missing installation integrity');
  for (const [root, manifest] of [[appRoot, profile.runtimeIntegrity], [path.dirname(appRoot), profile.resourcesFiles]]) {
    if (manifest === undefined && !dynamic) continue;
    if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest) || !Object.keys(manifest).length) throw new Error('Invalid integrity manifest');
    for (const [relative, digest] of Object.entries(manifest)) {
      if (typeof digest !== 'string' || !/^[a-f0-9]{64}$/.test(digest) || fileDigest(regularFile(root, relative)) !== digest) throw new Error('Installation changed');
    }
  }
  return true;
}

function startBridge({electron, profile, appRoot, runtime, environment = process.env, moduleCache = require.cache}) {
  const dynamic = profile?.windowBinding?.kind === LOCAL_HUB;
  const routes = profile?.windowBinding?.paths;
  if (!profile || profile.verified !== true || profile.moduleType !== 'commonjs' ||
      (profile.windowBinding && !dynamic) ||
      (dynamic && (profile.preload !== 'dist/preload.js' ||
        Object.keys(profile.windowBinding).sort().join(',') !== 'kind,paths' ||
        !Array.isArray(routes) || !routes.length || routes.length > 32 || new Set(routes).size !== routes.length ||
        routes.some(route => typeof route !== 'string' || !/^\/(?:[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)*)?$/.test(route)))) ||
      (!dynamic && (!Array.isArray(profile.trustedUrls) || !profile.trustedUrls.length))) return null;
  const {app, ipcMain, BrowserWindow} = electron;
  const controller = runtime.installIpc({ipcMain});
  const listeners = new Map(), hubWindows = new Map();
  let disposed = false;
  function safePreferences(wc, factoryPreload) {
    const prefs = wc.getLastWebPreferences();
    const expectedPreload = path.resolve(appRoot, profile.preload);
    // Electron 44 no longer retains preload in getLastWebPreferences. The
    // fingerprinted factory supplies its constructor's exact preload path.
    const preload = dynamic ? (factoryPreload ?? hubWindows.get(wc)?.preloadPath) : prefs?.preload;
    return !wc.isDestroyed() && prefs?.contextIsolation === true && prefs.sandbox === true &&
      prefs.nodeIntegration === false && samePath(preload, expectedPreload) &&
      (!dynamic || !('preload' in prefs) || samePath(prefs.preload, expectedPreload)) &&
      wc.getType?.() === 'window';
  }
  function localService() {
    const wsl = app.commandLine?.hasSwitch('wsl-distro')
      ? (app.commandLine.getSwitchValue?.('wsl-distro') ?? 'unsupported')
      : (environment.ANTIGRAVITY_WSL_DISTRO || environment.WSL_DISTRO);
    if (environment.DEV_URL || wsl ||
        environment.JETSKI_LS_PORT || environment.ELECTRON_OZONE_PLATFORM_HINT === 'headless' ||
        app.commandLine?.hasSwitch('no-sandbox')) return null;
    // Do not require app modules early and disturb their circular initialization.
    const cached = moduleCache[path.resolve(appRoot, 'dist/languageServer.js')];
    if (!cached?.loaded) return null;
    const ls = cached.exports, proc = ls.getLsProcess?.(), port = ls.getLsPort?.();
    const binary = path.resolve(appRoot, '../bin/language_server.exe');
    if (!samePath(ls.LS_BINARY, binary) || !proc || !Number.isInteger(proc.pid) || proc.pid <= 0 ||
        proc.killed || proc.exitCode !== null || proc.signalCode !== null || !samePath(proc.spawnfile, binary) ||
        !Number.isInteger(port) || port < 1 || port > 65535) return null;
    return {proc, pid: proc.pid, port, url: `https://127.0.0.1:${port}/`};
  }
  function localWindow(wc) {
    const win = hubWindows.get(wc)?.window;
    return win && !win.isDestroyed() && win.webContents === wc &&
      BrowserWindow?.fromWebContents(wc) === win && !win.getParentWindow();
  }
  function reviewedUrl(url, service) {
    return routes.some(route => url === service.url.slice(0, -1) + route);
  }
  function attach(_event, wc) {
    if (disposed || listeners.has(wc)) return;
    let revoke = null;
    function untrust() { if (typeof revoke === 'function') revoke(); revoke = null; }
    function check() {
      untrust();
      try {
        if (!safePreferences(wc)) return;
        const url = wc.getURL();
        if (dynamic) {
          const service = localService();
          if (!localWindow(wc) || !service || !reviewedUrl(url, service)) return;
          const stillTrusted = () => {
            const live = localService();
            return !disposed && safePreferences(wc) && !!localWindow(wc) && !!live &&
              live.proc === service.proc && live.pid === service.pid && live.port === service.port;
          };
          revoke = controller.registerTrustedWindow(wc, url, stillTrusted);
        } else if (profile.trustedUrls.includes(url)) {
          revoke = controller.registerTrustedWindow(wc, url, () => !disposed && safePreferences(wc));
        }
      } catch (_) { /* Unsupported or changed state stays untrusted. */ }
    }
    function navigate(_event, _url, _inPlace, isMainFrame) { if (isMainFrame !== false) untrust(); }
    function inPage(_event, _url, isMainFrame) { if (dynamic && isMainFrame === true) check(); }
    function cleanup() {
      untrust(); hubWindows.delete(wc);
      wc.removeListener('did-finish-load', check);
      wc.removeListener('did-start-navigation', navigate);
      wc.removeListener('did-navigate-in-page', inPage);
      wc.removeListener('destroyed', cleanup);
      listeners.delete(wc);
    }
    listeners.set(wc, cleanup);
    wc.on('did-finish-load', check);
    wc.on('did-start-navigation', navigate);
    wc.on('did-navigate-in-page', inPage);
    wc.on('destroyed', cleanup);
  }
  function registerHubWindow(win, url, preloadPath) {
    if (!dynamic || disposed) return false;
    try {
      const wc = win?.webContents, service = localService();
      if (!service || url !== service.url || !wc || !samePath(preloadPath, path.resolve(appRoot, profile.preload)) ||
          !safePreferences(wc, preloadPath) || win.isDestroyed() ||
          BrowserWindow?.fromWebContents(wc) !== win || win.getParentWindow()) return false;
      hubWindows.set(wc, {window: win, preloadPath}); attach(null, wc);
      // Only did-finish-load may grant trust; factory recording cannot.
      return true;
    } catch (_) { return false; }
  }
  app.on('web-contents-created', attach);
  function dispose() {
    if (disposed) return;
    disposed = true;
    app.removeListener('web-contents-created', attach);
    app.removeListener('will-quit', dispose);
    for (const cleanup of [...listeners.values()]) cleanup();
    controller.dispose();
    if (activeBridge === api) activeBridge = null;
  }
  const api = {dispose, registerHubWindow};
  app.on('will-quit', dispose);
  return api;
}
function registerHubWindow(win, url, preloadPath) { return activeBridge?.registerHubWindow(win, url, preloadPath) || false; }
function launch() {
  const profile = require('./profile.json');
  const appRoot = path.resolve(__dirname, '..');
  const entry = path.resolve(appRoot, profile.main);
  if (!entry.startsWith(appRoot + path.sep) || entry === __filename) throw new Error('Invalid original application entry');
  try {
    verifyInstallation(appRoot, profile);
    const electron = require('electron');
    // Bridge failure leaves the original application's startup intact.
    activeBridge = startBridge({electron, profile, appRoot, runtime: require('./main.cjs')});
  } catch (_) { /* No credentials, page data, or exception contents in logs. */ }
  return require(entry);
}
module.exports = {startBridge, launch, registerHubWindow, verifyInstallation};
if (require.main === module) launch();
