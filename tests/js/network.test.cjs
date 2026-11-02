'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const https = require('node:https');
const tls = require('node:tls');
const net = require('node:net');
const dns = require('node:dns');
const childProcess = require('node:child_process');
const N = require('../../localization_runtime/network.cjs');
const {probe} = require('../../localization_runtime/probe.cjs');
const {defaultConfig, defaultDictionary} = require('../../localization_runtime/storage.cjs');
const target = new URL('https://api.example.com/v1');
// Public test-only identity, trusted only by an injected TLS connection in tests.
const cert = fs.readFileSync(path.join(__dirname, '../fixtures/proxy-test-cert.pem'));
const key = fs.readFileSync(path.join(__dirname, '../fixtures/proxy-test-key.pem'));

test('Windows proxy is refreshed and HTTPS-specific entry wins over stale environment', async () => {
  let server = 'http=127.0.0.1:1111;https=127.0.0.1:2222';
  const options = {platform: 'win32', env: {HTTPS_PROXY: 'http://stale.example:3333'},
    readWindows: async () => ({ProxyEnable: '0x1', ProxyServer: server})};
  assert.equal((await N.resolveProxy(target, options)).port, '2222');
  server = '127.0.0.1:4444';
  assert.equal((await N.resolveProxy(target, options)).port, '4444');
  options.readWindows = async () => ({ProxyEnable: '0x0', ProxyServer: server});
  assert.equal(await N.resolveProxy(target, options), null);
});

test('Windows registry output parses only the supported fields', () => {
  assert.deepEqual(N.parseWindowsProxy('HKEY_CURRENT_USER\\ignored\r\n    ProxyEnable    REG_DWORD    0x1\r\n    ProxyServer    REG_SZ    127.0.0.1:10808\r\n    unrelated    REG_SZ    secret'),
    {ProxyEnable: '0x1', ProxyServer: '127.0.0.1:10808'});
});

test('unsupported proxies and PAC return sanitized configuration errors', async () => {
  for (const server of ['', 'socks=127.0.0.1:1080', 'socks5://127.0.0.1:1080', 'http://user:secret@proxy.example:80', 'http://proxy.example/path', 'http://proxy.example:0']) {
    await assert.rejects(N.resolveProxy(target, {platform: 'win32', readWindows: async () => ({ProxyEnable: '0x1', ProxyServer: server})}),
      error => error.code === 'proxy_configuration_error' && !error.message.includes('secret'));
  }
  await assert.rejects(N.resolveProxy(target, {platform: 'win32', readWindows: async () => ({ProxyEnable: '0x0', AutoConfigURL: 'https://proxy.example/script.pac'})}), {code: 'proxy_configuration_error'});
});

test('bypass rules honor host, wildcard and port boundaries', async () => {
  for (const entry of ['*.example.com', 'api.example.com:443', '*', '.example.com']) assert.equal(N.bypassesProxy(target, entry, true), true, entry);
  for (const entry of ['example.com', 'api.example.com:8443', '<local>', 'evil-example.com']) assert.equal(N.bypassesProxy(target, entry, true), false, entry);
  assert.equal(N.bypassesProxy(target, 'example.com'), true);
  assert.equal(N.bypassesProxy(new URL('https://notexample.com'), 'example.com'), false);
  assert.equal(await N.resolveProxy(target, {platform: 'win32', readWindows: async () => ({ProxyEnable: '0x1', ProxyServer: '127.0.0.1:10808', ProxyOverride: '*.example.com'})}), null);
});

test('non-Windows uses HTTPS_PROXY or ALL_PROXY and respects NO_PROXY', async () => {
  assert.equal((await N.resolveProxy(target, {platform: 'linux', env: {HTTPS_PROXY: 'http://127.0.0.1:10808'}})).port, '10808');
  assert.equal((await N.resolveProxy(target, {platform: 'darwin', env: {ALL_PROXY: 'https://proxy.example:443'}})).protocol, 'https:');
  assert.equal(await N.resolveProxy(target, {platform: 'linux', env: {HTTPS_PROXY: 'http://127.0.0.1:10808', NO_PROXY: 'example.com'}}), null);
});

async function listen(t, server) {
  const sockets = new Set();
  server.on('connection', socket => { sockets.add(socket); socket.on('close', () => sockets.delete(socket)); });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  t.after(() => new Promise(resolve => { for (const socket of sockets) socket.destroy(); server.close(resolve); }));
  return server.address().port;
}

async function fixture(t, {proxyStatus = 200, hang = false, hangTls = false, trust = true, addresses, response, proxyTls = false} = {}) {
  const connects = [];
  const requests = [];
  const peers = new Set();
  const origin = https.createServer({key, cert}, (req, res) => {
    const chunks = [];
    req.on('data', chunk => chunks.push(chunk));
    req.on('end', () => {
      requests.push({headers: req.headers, body: Buffer.concat(chunks).toString(), servername: req.socket.servername});
      res.setHeader('content-type', 'application/json');
      res.end(response || JSON.stringify({choices: [{finish_reason: 'stop', message: {content: '[{"id":"probe","text":"打开设置"}]'}}]}));
    });
  });
  const originPort = await listen(t, origin);
  const proxy = proxyTls ? https.createServer({key, cert}) : http.createServer();
  proxy.on('connect', (req, socket) => {
    connects.push({path: req.url, headers: req.headers});
    if (hang) return;
    if (proxyStatus !== 200) { socket.end(`HTTP/1.1 ${proxyStatus} Rejected\r\nContent-Length: 0\r\n\r\n`); return; }
    if (hangTls) { socket.write('HTTP/1.1 200 Connection Established\r\n\r\n'); return; }
    // A local mock proxy maps the checked public destination to our TLS fixture.
    const peer = net.connect(originPort, '127.0.0.1', () => {
      socket.write('HTTP/1.1 200 Connection Established\r\n\r\n');
      peer.pipe(socket); socket.pipe(peer);
    });
    peers.add(peer);
    peer.on('error', () => socket.destroy());
    socket.on('error', () => peer.destroy());
    socket.on('close', () => peer.destroy());
    peer.on('close', () => peers.delete(peer));
  });
  t.after(() => { for (const peer of peers) peer.destroy(); });
  const proxyPort = await listen(t, proxy);
  const server = proxyTls ? `https://proxy.example.com:${proxyPort}` : `127.0.0.1:${proxyPort}`;
  t.mock.method(childProcess, 'execFile', (file, args, options, callback) => {
    assert.match(file, /reg\.exe$/i);
    assert.equal(options.windowsHide, true);
    queueMicrotask(() => callback(null, `    ProxyEnable    REG_DWORD    0x1\r\n    ProxyServer    REG_SZ    ${server}\r\n`));
  });
  const names = ['HTTPS_PROXY', 'https_proxy', 'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy'];
  const old = Object.fromEntries(names.map(name => [name, process.env[name]]));
  for (const name of names) delete process.env[name];
  process.env.HTTPS_PROXY = proxyTls ? server : `http://${server}`;
  t.after(() => { for (const name of names) { if (old[name] === undefined) delete process.env[name]; else process.env[name] = old[name]; } });
  t.mock.method(dns, 'lookup', (hostname, options, callback) => {
    assert.ok(['api.example.com', 'wrong.example.com', 'proxy.example.com'].includes(hostname), hostname);
    const found = hostname === 'proxy.example.com' ? [{address: '127.0.0.1', family: 4}] :
      (addresses || [{address: '93.184.216.34', family: 4}]);
    queueMicrotask(() => options.all ? callback(null, found) : callback(null, found[0].address, found[0].family));
  });
  const connectTls = tls.connect;
  if (trust) t.mock.method(tls, 'connect', options => connectTls({...options, ca: cert}));
  return {connects, requests, proxyPort};
}

const request = {url: target.toString(), headers: {authorization: 'Bearer fixture-only-key'}, body: {text: 'Open settings'}, timeoutMs: 2000};

test('real CONNECT and TLS carry the fixed probe and never expose API headers to the proxy', async t => {
  const f = await fixture(t);
  const config = defaultConfig();
  config.provider = 'compatible';
  config.providers.compatible = {baseUrl: target.toString(), model: 'fixture-model', apiKey: 'fixture-only-key'};
  const result = await probe({store: {read: async () => ({config, dictionary: defaultDictionary()})}});
  assert.deepEqual(result, {ok: true, status: 'connected'});
  assert.equal(f.connects[0].path, '93.184.216.34:443');
  assert.equal(f.requests[0].servername, 'api.example.com');
  assert.equal(f.requests[0].headers.authorization, 'Bearer fixture-only-key');
  assert.ok(f.requests[0].body.includes('Open settings'));
  assert.equal(JSON.stringify(f.connects).includes('fixture-only-key'), false);
});

test('TLS through an HTTPS proxy also succeeds with certificate verification', async t => {
  const f = await fixture(t, {proxyTls: true});
  assert.equal((await N.httpsTransport(request)).status, 200);
  assert.equal(f.requests.length, 1);
});

test('untrusted origin certificates are rejected before API headers are sent', async t => {
  const f = await fixture(t, {trust: false});
  await assert.rejects(N.httpsTransport(request), {code: 'network_error'});
  assert.equal(f.requests.length, 0);
});

test('origin hostname mismatch is rejected even with a trusted certificate', async t => {
  const f = await fixture(t);
  await assert.rejects(N.httpsTransport({...request, url: 'https://wrong.example.com/v1'}), {code: 'network_error'});
  assert.equal(f.requests.length, 0);
});

test('mixed public/private DNS results cannot reach the proxy', async t => {
  const f = await fixture(t, {addresses: [{address: '93.184.216.34', family: 4}, {address: '127.0.0.1', family: 4}]});
  await assert.rejects(N.httpsTransport(request), {code: 'unsafe_endpoint'});
  assert.equal(f.connects.length, 0);
});

for (const [status, code] of [[407, 'proxy_authentication_required'], [502, 'proxy_connection_failed']]) {
  test(`proxy HTTP ${status} is diagnosed without a direct retry`, async t => {
    const f = await fixture(t, {proxyStatus: status});
    await assert.rejects(N.httpsTransport(request), {code});
    assert.equal(f.connects.length, 1);
    assert.equal(f.requests.length, 0);
  });
}

for (const mode of ['hang', 'hangTls']) {
  test(`${mode} remains bounded by the total timeout`, async t => {
    const f = await fixture(t, {[mode]: true});
    await assert.rejects(N.httpsTransport({...request, timeoutMs: 100}), {code: 'timeout'});
    assert.equal(f.requests.length, 0);
  });
}

test('cancellation closes a CONNECT request still waiting for a response', async t => {
  const f = await fixture(t, {hang: true});
  const controller = new AbortController();
  const work = N.httpsTransport({...request, signal: controller.signal});
  const check = setInterval(() => { if (f.connects.length) controller.abort(); }, 5);
  try { await assert.rejects(work, {code: 'cancelled'}); }
  finally { clearInterval(check); }
});

test('response size limit also applies through the proxy', async t => {
  await fixture(t, {response: JSON.stringify({large: 'x'.repeat(128 * 1024)})});
  await assert.rejects(N.httpsTransport(request), {code: 'response_too_large'});
});

test('pre-cancelled calls do not inspect settings or send a request', async t => {
  const f = await fixture(t);
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(N.httpsTransport({...request, signal: controller.signal}), {code: 'cancelled'});
  assert.equal(f.connects.length, 0);
});

test('probe preserves actionable proxy and endpoint errors without raw details', async () => {
  const store = {read: async () => ({config: defaultConfig()})};
  for (const code of ['proxy_configuration_error', 'proxy_connection_failed', 'proxy_authentication_required', 'unsafe_endpoint', 'provider_rejected']) {
    const result = await probe({store, translate: async () => { const error = new Error('fixture-secret'); error.code = code; throw error; }});
    assert.deepEqual(result, {ok: false, status: code});
    assert.equal(JSON.stringify(result).includes('fixture-secret'), false);
  }
});
