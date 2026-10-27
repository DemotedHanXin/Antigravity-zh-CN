'use strict';
// Only installed for an exact, reviewed CommonJS application fingerprint.
// Never loosens Electron preferences and never grants a page a generic IPC API.
const path = require('node:path');
function startBridge({electron, profile, appRoot, runtime}) {
  if (!profile || profile.verified !== true || profile.moduleType !== 'commonjs' ||
      !Array.isArray(profile.trustedUrls) || !profile.trustedUrls.length) return null;
  const {app, ipcMain} = electron;
  const controller = runtime.installIpc({ipcMain});
  const listeners = new Map();
  function attach(_event, wc) {
    function check() {
      try {
        if (wc.isDestroyed()) return;
        const prefs = wc.getLastWebPreferences();
        const expectedPreload = path.resolve(appRoot, profile.preload);
        if (!prefs || prefs.contextIsolation !== true || prefs.sandbox !== true ||
            prefs.nodeIntegration !== false || typeof prefs.preload !== 'string' ||
            path.resolve(prefs.preload) !== expectedPreload ||
            (wc.getType && wc.getType() !== 'window')) return;
        const url = wc.getURL();
        if (profile.trustedUrls.includes(url)) controller.registerTrustedWindow(wc, url);
      } catch (_) { /* Unsupported runtime/window stays untrusted. */ }
    }
    function cleanup() {
      wc.removeListener('did-finish-load', check);
      wc.removeListener('destroyed', cleanup);
      listeners.delete(wc);
    }
    listeners.set(wc, cleanup);
    wc.on('did-finish-load', check);
    wc.on('destroyed', cleanup);
    // Registration intentionally occurs after exact navigation completion.
  }
  app.on('web-contents-created', attach);
  function dispose() {
    app.removeListener('web-contents-created', attach);
    app.removeListener('will-quit', dispose);
    for (const cleanup of [...listeners.values()]) cleanup();
    controller.dispose();
  }
  app.on('will-quit', dispose);
  return {dispose};
}
function launch() {
  const profile = require('./profile.json');
  const appRoot = path.resolve(__dirname, '..');
  const entry = path.resolve(appRoot, profile.main);
  if (!entry.startsWith(appRoot + path.sep) || entry === __filename) throw new Error('Invalid original application entry');
  try {
    const electron = require('electron');
    // A missing API/runtime module fails closed; original app still loads.
    startBridge({electron,profile,appRoot,runtime:require('./main.cjs')});
  } catch (_) { /* No credentials, page data, or exception contents in logs. */ }
  return require(entry);
}
module.exports = {startBridge, launch};
if (require.main === module) launch();
