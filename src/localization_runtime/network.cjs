'use strict';
// Shared by the explicit connection probe and the main-process translator.
const http = require('node:http');
const https = require('node:https');
const tls = require('node:tls');
const dns = require('node:dns');
const net = require('node:net');
const path = require('node:path');
const childProcess = require('node:child_process');

class TranslationError extends Error {
  constructor(code, retryAfterMs = 0) { super(code); this.name='TranslationError'; this.code=code; this.retryAfterMs=retryAfterMs; }
}

function isPublicAddress(address) {
  const a=address.toLowerCase().replace(/^\[|\]$/g,'');
  if (net.isIPv4(a)) {
    const p=a.split('.').map(Number);
    return !(p[0]===0 || p[0]===10 || p[0]===127 || p[0]>=224 || (p[0]===169&&p[1]===254) || (p[0]===172&&p[1]>=16&&p[1]<=31) || (p[0]===192&&p[1]===168) || (p[0]===100&&p[1]>=64&&p[1]<=127) || (p[0]===198&&(p[1]===18||p[1]===19)));
  }
  if (net.isIPv6(a)) return /^[23][0-9a-f]{3}:/.test(a) && !/^2001:(?:0{1,4}:|:|0?db8:|0{0,2}10:|0{0,2}20:)|^2002:|^3fff:/.test(a) && !a.includes('.');
  return false;
}

function safeLookup(hostname, options, callback) {
  dns.lookup(hostname,{all:true},(error,addresses)=>{
    if (error || !addresses?.length) return callback(new TranslationError('network_error'));
    if (addresses.some(({address})=>!isPublicAddress(address))) return callback(new TranslationError('unsafe_endpoint'));
    if (options.all) callback(null,addresses); else callback(null,addresses[0].address,addresses[0].family);
  });
}

function proxyUrl(value) {
  const raw = value.trim();
  let url;
  try { url = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(raw) ? raw : `http://${raw}`); }
  catch (_) { throw new TranslationError('proxy_configuration_error'); }
  if (!raw || /[\s\\]/.test(raw) || !['http:', 'https:'].includes(url.protocol) || !url.hostname ||
      url.username || url.password || url.search || url.hash || url.port === '0' || url.pathname !== '/') {
    throw new TranslationError('proxy_configuration_error');
  }
  return url;
}

function bypassesProxy(target, bypass, windows = false) {
  const hostname = target.hostname.toLowerCase();
  return String(bypass || '').toLowerCase().split(/[;,\s]+/).some(entry => {
    if (!entry) return false;
    if (entry === '<local>') return !hostname.includes('.');
    const match = entry.match(/^(.*):(\d+)$/);
    if (match) {
      if (Number(match[2]) !== Number(target.port || 443)) return false;
      entry = match[1];
    }
    if (entry.startsWith('.')) return hostname === entry.slice(1) || hostname.endsWith(entry);
    if (!windows && !entry.includes('*') && hostname.endsWith(`.${entry}`)) return true;
    const pattern = entry.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*');
    return new RegExp(`^${pattern}$`).test(hostname);
  });
}

function parseWindowsProxy(output) {
  const settings = {};
  for (const line of output.split(/\r?\n/)) {
    const match = line.match(/^\s*(ProxyEnable|ProxyServer|ProxyOverride|AutoConfigURL)\s+REG_(?:DWORD|SZ|EXPAND_SZ)\s+(.*?)\s*$/);
    if (match) settings[match[1]] = match[2];
  }
  if (settings.ProxyEnable && !/^0x[01]$/i.test(settings.ProxyEnable)) throw new TranslationError('proxy_configuration_error');
  return settings;
}

function readWindowsProxy(signal) {
  return new Promise((resolve, reject) => {
    const executable = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'reg.exe');
    childProcess.execFile(executable, ['query', 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings'],
      {windowsHide: true, encoding: 'utf8', timeout: 2000, maxBuffer: 64 * 1024, signal}, (error, output) => {
        if (error) return reject(new TranslationError('proxy_configuration_error'));
        try { resolve(parseWindowsProxy(output)); } catch (error) { reject(error); }
      });
  });
}

async function resolveProxy(target, {platform = process.platform, env = process.env, signal, readWindows = readWindowsProxy} = {}) {
  if (platform === 'win32') {
    // Re-read on each request; an old launcher environment must not override a
    // proxy port change or the user switching the Windows proxy off.
    const settings = await readWindows(signal);
    if (settings.AutoConfigURL?.trim()) throw new TranslationError('proxy_configuration_error');
    if (parseInt(settings.ProxyEnable || '0', 16) !== 1) return null;
    let server = settings.ProxyServer?.trim();
    if (!server) throw new TranslationError('proxy_configuration_error');
    if (server.includes('=')) {
      const entries = new Map();
      for (const part of server.split(/[;\s]+/).filter(Boolean)) {
        const match = part.match(/^([a-z]+)=(.+)$/i);
        if (!match) throw new TranslationError('proxy_configuration_error');
        entries.set(match[1].toLowerCase(), match[2]);
      }
      server = entries.get('https');
      if (!server) throw new TranslationError('proxy_configuration_error');
    }
    const proxy = proxyUrl(server);
    return bypassesProxy(target, settings.ProxyOverride, true) ? null : proxy;
  }
  const server = env.https_proxy || env.HTTPS_PROXY || env.all_proxy || env.ALL_PROXY;
  if (!server || bypassesProxy(target, env.no_proxy || env.NO_PROXY)) return null;
  return proxyUrl(server);
}

function httpsTransport({url, headers, body, signal, timeoutMs = 15000}) {
  return new Promise((resolve, reject) => {
    const controller = new AbortController();
    const resources = new Set();
    let settled = false;
    let timer;
    const finish = (error, result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal?.removeEventListener('abort', cancel);
      controller.abort();
      for (const resource of resources) resource.destroy();
      if (error) reject(error instanceof TranslationError ? error : new TranslationError('network_error'));
      else resolve(result);
    };
    const cancel = () => finish(new TranslationError('cancelled'));
    if (signal?.aborted) return cancel();
    signal?.addEventListener('abort', cancel, {once: true});
    timer = setTimeout(() => finish(new TranslationError('timeout')), timeoutMs);

    function send(agent) {
      if (settled) return;
      try {
        const bytes = Buffer.from(JSON.stringify(body));
        const request = https.request(url, {
          method: 'POST', headers: {...headers, 'content-length': bytes.length},
          signal: controller.signal, lookup: safeLookup, agent, rejectUnauthorized: true,
        }, response => {
          let size = 0;
          const chunks = [];
          response.on('data', chunk => {
            size += chunk.length;
            if (size > 128 * 1024) finish(new TranslationError('response_too_large'));
            else chunks.push(chunk);
          });
          response.on('end', () => {
            let value;
            try { value = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch (_) { value = null; }
            finish(null, {status: response.statusCode, headers: response.headers, body: value});
          });
          response.on('aborted', () => finish(new TranslationError('network_error')));
          response.on('error', () => finish(new TranslationError('network_error')));
        });
        resources.add(request);
        request.on('error', error => finish(error));
        request.end(bytes);
      } catch (error) { finish(error); }
    }

    async function start() {
      const target = new URL(url);
      const proxy = await resolveProxy(target, {signal: controller.signal});
      if (settled) return;
      // Use a dedicated agent, including for direct requests: do not inherit a
      // global agent's environment-proxy setting on newer Node versions.
      const agent = new https.Agent({keepAlive: false, proxyEnv: {}});
      resources.add(agent);
      if (!proxy) return send(agent);
      safeLookup(target.hostname, {all: true}, (error, addresses) => {
        if (settled) return;
        if (error) return finish(error);
        // Pin the CONNECT destination to a checked public IP. TLS still verifies
        // the original hostname; the proxy never receives API headers in clear.
        const {address, family} = addresses.find(item => item.family === 4) || addresses[0];
        const authority = `${family === 6 ? `[${address}]` : address}:${target.port || 443}`;
        try {
          const transport = proxy.protocol === 'https:' ? https : http;
          const connect = transport.request({
            hostname: proxy.hostname.replace(/^\[|\]$/g, ''), port: proxy.port || (proxy.protocol === 'https:' ? 443 : 80),
            method: 'CONNECT', path: authority, headers: {host: authority}, agent: false,
            signal: controller.signal, rejectUnauthorized: true, maxHeaderSize: 8192,
          });
          resources.add(connect);
          connect.on('error', () => finish(new TranslationError('proxy_connection_failed')));
          connect.on('connect', (response, socket, head) => {
            resources.add(socket);
            // CONNECT detaches the socket from ClientRequest's error handler.
            socket.on('error', () => finish(new TranslationError('proxy_connection_failed')));
            if (settled) { socket.destroy(); return; }
            if (response.statusCode !== 200 || head.length) {
              return finish(new TranslationError(response.statusCode === 407 ? 'proxy_authentication_required' : 'proxy_connection_failed'));
            }
            try {
              const secure = tls.connect({socket, servername: target.hostname, rejectUnauthorized: true});
              resources.add(secure);
              secure.on('error', () => finish(new TranslationError('network_error')));
              secure.once('secureConnect', () => {
                agent.createConnection = () => secure;
                send(agent);
              });
            } catch (error) { finish(error); }
          });
          connect.end();
        } catch (_) { finish(new TranslationError('proxy_connection_failed')); }
      });
    }
    start().catch(error => finish(error));
  });
}

module.exports = {TranslationError, isPublicAddress, httpsTransport, proxyUrl, bypassesProxy, parseWindowsProxy, resolveProxy};
