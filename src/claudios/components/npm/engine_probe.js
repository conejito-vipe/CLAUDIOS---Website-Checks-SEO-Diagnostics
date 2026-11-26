"use strict";
// Engine-Probe für Claudios: lädt wenige Seiten in Firefox und WebKit (Playwright) und schreibt ein JSON-Ergebnis.
// Aufruf: node engine_probe.js eingabe.json ausgabe.json
// Sicherheitsregeln wie in browser_probe.js: Zertifikatsfehler werden nie ignoriert, Service Worker sind blockiert,
// Anfragen über unverschlüsseltes HTTP und an lokale Namen oder IP-Adressen werden abgebrochen. Anders als bei Chromium
// lässt sich der Zielhost hier NICHT an die geprüfte IP festlegen: Claudios prüft die Auflösung vor und nach dem Lauf.
const fs = require("fs");
const { firefox, webkit } = require("playwright");

const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const outPath = process.argv[3];
const REG = String(input.registrable || "").toLowerCase();
const ENGINES = [["firefox", firefox], ["webkit", webkit]];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const sameSite = (host) => host === REG || host.endsWith("." + REG);
// BEGIN-NETGUARD (in allen Browser-Skripten identisch; tests/test_netguard_js.py prüft das)
const dns = require("dns").promises;
const LOCAL_SUFFIXES = [".localhost", ".local", ".internal", ".lan", ".home", ".home.arpa", ".corp", ".intranet", ".private"];
const isLocalName = (raw) => {
  const host = String(raw).toLowerCase().replace(/\.+$/, "");
  return host === "" || host === "localhost" || !host.includes(".") || host.startsWith("[") ||
    /^\d+\.\d+\.\d+\.\d+$/.test(host) || LOCAL_SUFFIXES.some((s) => host.endsWith(s));
};
const privateIp = (ip) => {
  const a = String(ip).toLowerCase();
  const m = a.match(/^(?:::ffff:)?(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
  if (m) {
    const [x, y] = [Number(m[1]), Number(m[2])];
    return x === 0 || x === 10 || x === 127 || (x === 169 && y === 254) || (x === 172 && y >= 16 && y <= 31) ||
      (x === 192 && y === 168) || (x === 100 && y >= 64 && y <= 127) || x >= 224;
  }
  return a === "::" || a === "::1" || a.startsWith("fc") || a.startsWith("fd") || a.startsWith("fe8") ||
    a.startsWith("fe9") || a.startsWith("fea") || a.startsWith("feb") || a.startsWith("::ffff:");
};
const dnsCache = new Map();
const resolvesPrivate = (host) => {
  if (!dnsCache.has(host)) {
    dnsCache.set(host, dns.lookup(host, { all: true }).then((list) => list.some((r) => privateIp(r.address)), () => false));
  }
  return dnsCache.get(host);
};
// Blockiert lokale Namen und Namen, die auf private Adressen zeigen. Der geprüfte Zielhost (input.host) ist per IP festgelegt.
const blockedHost = async (host) => isLocalName(host) || (host !== String(input.host || "").toLowerCase() && await resolvesPrivate(host));
// END-NETGUARD
const message = (e) => String((e && e.message) || e).slice(0, 200);

function userAgent(name, version) {
  const major = String(version || "").split(".")[0] || "0";
  const base = name === "firefox"
    ? "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:" + major + ".0) Gecko/20100101 Firefox/" + major + ".0"
    : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15";
  return base + " " + input.ua_suffix;
}

async function checkPage(browser, url, ua) {
  const rec = {
    url, status: null, error: null, title: "", console_errors: 0, console_first: "", page_errors: [],
    failed: [], bad_status: [], third_party: {}, insecure_blocked: [], overflow: {},
  };
  const context = await browser.newContext({
    userAgent: ua, viewport: { width: 1280, height: 800 }, serviceWorkers: "block", acceptDownloads: false,
  });
  try {
    await context.route("**/*", async (route) => {
      let u;
      try { u = new URL(route.request().url()); } catch (e) { return route.abort(); }
      const host = u.hostname.toLowerCase();
      if (u.protocol === "http:") {
        if (rec.insecure_blocked.length < 10) { rec.insecure_blocked.push(u.href.slice(0, 200)); }
        return route.abort();
      }
      if (u.protocol === "https:" && await blockedHost(host)) { return route.abort(); }
      return route.continue();
    });
    const page = await context.newPage();
    page.on("console", (m) => {
      if (m.type() === "error") {
        rec.console_errors += 1;
        if (!rec.console_first) { rec.console_first = m.text().slice(0, 200); }
      }
    });
    page.on("pageerror", (e) => { if (rec.page_errors.length < 10) { rec.page_errors.push(message(e)); } });
    page.on("requestfailed", (r) => {
      if (r.url().startsWith("http:") || rec.failed.length >= 20) { return; }
      rec.failed.push({ url: r.url().slice(0, 200), reason: ((r.failure() || {}).errorText || "").slice(0, 80) });
    });
    page.on("response", (r) => {
      if (r.status() >= 400 && rec.bad_status.length < 20) {
        rec.bad_status.push({ url: r.url().slice(0, 200), status: r.status() });
      }
      let host = "";
      try { host = new URL(r.url()).hostname.toLowerCase(); } catch (e) { host = ""; }
      if (host && !sameSite(host)) { rec.third_party[host] = (rec.third_party[host] || 0) + 1; }
    });
    const response = await page.goto(url, { waitUntil: "load", timeout: 30000 });
    rec.status = response ? response.status() : null;
    await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {});
    await sleep(1000);
    let finalHost = "";
    try { finalHost = new URL(page.url()).hostname.toLowerCase(); } catch (e) { finalHost = ""; }
    if (!sameSite(finalHost)) { rec.error = "offsite_redirect"; return rec; }
    rec.title = (await page.title()).slice(0, 120);
    for (const width of [360, 1280]) {
      await page.setViewportSize({ width, height: 800 });
      await sleep(300);
      rec.overflow[String(width)] = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth + 1);
    }
  } catch (e) {
    rec.error = message(e);
  } finally {
    await context.close().catch(() => {});
  }
  return rec;
}

(async () => {
  const result = { engines: [] };
  for (const [name, type] of ENGINES) {
    const rec = { engine: name, version: "", error: null, pages: [] };
    let browser = null;
    try {
      browser = await type.launch({ headless: true });
      rec.version = browser.version();
      const ua = userAgent(name, rec.version);
      for (const url of input.urls) {
        rec.pages.push(await checkPage(browser, url, ua));
        await sleep(700);
      }
    } catch (e) {
      rec.error = message(e);
    } finally {
      if (browser) { await browser.close().catch(() => {}); }
    }
    result.engines.push(rec);
  }
  fs.writeFileSync(outPath, JSON.stringify(result));
})();
