'use strict';
// Lab-only control. No renderer IPC and no caller-selected executable or PID.
const nativeFs = require('node:fs');
const path = require('node:path');
const {randomBytes} = require('node:crypto');
const REQUEST_KEYS = 'expectedGeneration,expectedPid,expectedPort,expectedWindowId,id,schemaVersion,sessionId';
const token = value => typeof value === 'string' && /^[a-f0-9]{32}$/.test(value);
const positive = value => Number.isSafeInteger(value) && value > 0;

function createServiceControl({root, appRoot, appPid, getService, getWindows, getHubWindows,
  getAudit, isBusy = () => false, fs = nativeFs, newSessionId = () => randomBytes(16).toString('hex')}) {
  if (path.resolve(root, 'install/resources/app') !== appRoot || !positive(appPid)) throw new Error('Invalid lab control');
  const sessionId = newSessionId();
  if (!token(sessionId)) throw new Error('Invalid session identifier');
  const binary = path.resolve(appRoot, '../bin/language_server.exe');
  const evidence = path.join(root, 'evidence');
  const requestFile = path.join(root, 'restart-service-request.json');
  let generation = 0, lastChild = null, attempted = false;

  function liveService() {
    try {
      const service = getService(), child = service?.child;
      if (!child || child.spawnfile !== binary || child.killed || child.exitCode !== null ||
          child.signalCode !== null || !positive(child.pid) || child.pid === appPid ||
          !positive(service.port) || service.port > 65535 ||
          service.origin !== `https://127.0.0.1:${service.port}`) return null;
      if (lastChild !== child) {
        if (generation >= Number.MAX_SAFE_INTEGER) return null;
        lastChild = child; generation++;
      }
      return {...service, generation};
    } catch (_) { return null; }
  }
  const describe = service => ({sessionId, appPid, service: service
    ? {generation: service.generation, pid: service.child.pid, port: service.port} : null});
  const snapshot = () => describe(liveService());
  function readRequest() {
    const stat = fs.lstatSync(requestFile);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 1024) throw new Error('Invalid request file');
    return fs.readFileSync(requestFile, 'utf8');
  }
  function unchanged(raw) { try { return readRequest() === raw; } catch (_) { return false; } }
  function objectExists(file) {
    try { fs.lstatSync(file); return true; }
    catch (error) { if (error.code === 'ENOENT') return false; throw error; }
  }
  function stopped() {
    try { return objectExists(path.join(root, 'stop')) || isBusy(); }
    catch (_) { return true; }
  }
  function validRequest(request) {
    return request && Object.keys(request).sort().join(',') === REQUEST_KEYS &&
      request.schemaVersion === 1 && token(request.id) && token(request.sessionId) &&
      [request.expectedGeneration, request.expectedPid, request.expectedPort, request.expectedWindowId].every(positive) &&
      request.expectedPort <= 65535;
  }
  function guard(request, originalChild) {
    if (stopped()) return {reason: 'stopping_or_busy'};
    const audit = getAudit();
    if (audit.mode !== 'controlled-success' || !(audit.authorizedSnapshots > 0)) return {reason: 'not_authorized'};
    const service = liveService();
    if (!service || request.sessionId !== sessionId || request.expectedGeneration !== service.generation ||
        request.expectedPid !== service.child.pid || request.expectedPort !== service.port ||
        (originalChild && service.child !== originalChild) || typeof service.child.kill !== 'function') return {reason: 'target_changed'};
    const hubWindows = getHubWindows();
    const win = getWindows().find(win => win.webContents?.id === request.expectedWindowId);
    const wc = win?.webContents;
    if (!win || !Array.isArray(hubWindows) || !hubWindows.includes(win) || win.isDestroyed() ||
        win.getParentWindow() || wc.isDestroyed() || wc.getType() !== 'window' ||
        wc.getURL() !== service.origin + '/') return {reason: 'unsafe_window'};
    const prefs = wc.getLastWebPreferences();
    if (prefs?.contextIsolation !== true || prefs.sandbox !== true || prefs.nodeIntegration !== false ||
        (Object.hasOwn(prefs, 'preload') && prefs.preload !== path.join(appRoot, 'dist/preload.js'))) return {reason: 'unsafe_window'};
    return {service};
  }
  function safeEvidenceDirectory() {
    for (const folder of [root, evidence]) {
      const stat = fs.lstatSync(folder);
      if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error('Invalid evidence directory');
    }
  }
  function claim(file, record) {
    // An interrupted attempt must remain claimed even if writing the receipt fails.
    const fd = fs.openSync(file, 'wx', 0o600);
    try { fs.writeFileSync(fd, JSON.stringify(record) + '\n', 'utf8'); fs.fsyncSync(fd); }
    finally { fs.closeSync(fd); }
  }
  function handleRequest() {
    if (stopped()) return;
    let raw, request;
    try { raw = readRequest(); request = JSON.parse(raw); } catch (_) { return; }
    if (!validRequest(request)) return;
    const resultFile = path.join(evidence, `service-restart-${request.id}.json`);
    const claimFile = path.join(evidence, `service-restart-${request.id}.claim.json`);
    let before = null, status = 'denied', reason = null;
    try {
      safeEvidenceDirectory();
      if (objectExists(resultFile)) {
        if (unchanged(raw)) fs.unlinkSync(requestFile);
        return;
      }
      if (objectExists(claimFile)) { attempted = true; status = 'already_claimed'; reason = 'restart_limit'; }
      else if (attempted) reason = 'restart_limit';
      else {
        const checked = guard(request);
        if (!checked.service) reason = checked.reason;
        else if (!unchanged(raw)) return;
        else {
          before = describe(checked.service);
          // Consume this session's attempt before opening or syncing the claim.
          // A disk failure must never turn a later polling tick into a retry.
          attempted = true;
          claim(claimFile, {schemaVersion: 1, requestId: request.id, capturedAt: new Date().toISOString(), before});
          // No await or process-name lookup between final checks and this child handle.
          const current = guard(request, checked.service.child);
          if (!current.service || !unchanged(raw)) reason = current.reason || 'request_changed';
          else {
            try { status = current.service.child.kill('SIGTERM') === true ? 'signal_sent' : 'signal_failed'; }
            catch (_) { status = 'signal_failed'; }
          }
        }
      }
      fs.writeFileSync(resultFile, JSON.stringify({schemaVersion: 1, kind: 'isolated-service-restart',
        requestId: request.id, capturedAt: new Date().toISOString(), sessionId, appPid,
        status, reason, before}, null, 2) + '\n', {flag: 'wx'});
      if (unchanged(raw)) fs.unlinkSync(requestFile);
    } catch (_) { /* No kill retry after a claim; preserve markers for diagnosis. */ }
  }
  return {snapshot, handleRequest};
}
module.exports = {createServiceControl};
