"use strict";
// Screenshot-Probe für Claudios: öffnet die Startseite in Chromium und speichert zwei Bilder (Desktop und Mobil).
// Aufruf: node shot_probe.js eingabe.json ausgabe.json
// Sicherheitsregeln wie in browser_probe.js: Zertifikatsfehler werden nie ignoriert, Service Worker sind blockiert,
// Anfragen über unverschlüsseltes HTTP und an lokale Namen oder IP-Adressen werden abgebrochen, der Zielhost ist auf
// die vorher geprüfte öffentliche IP festgelegt. Die Bilder werden nur in den Ordner outdir geschrieben.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const outPath = process.argv[3];
const REG = String(input.registrable || "").toLowerCase();
const VIEWS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844 },
];

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

async function shoot(browser, url, ua, view) {
  const rec = { view: view.name, file: null, error: null };
  const context = await browser.newContext({
    userAgent: ua, viewport: { width: view.width, height: view.height }, serviceWorkers: "block", acceptDownloads: false,
  });
  try {
    await context.route("**/*", async (route) => {
      let u;
      try { u = new URL(route.request().url()); } catch (e) { return route.abort(); }
      const host = u.hostname.toLowerCase();
      if (u.protocol === "http:") { return route.abort(); }
      if (u.protocol === "https:" && await blockedHost(host)) { return route.abort(); }
      return route.continue();
    });
    const page = await context.newPage();
    await page.goto(url, { waitUntil: "load", timeout: 30000 });
    await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {});
    await sleep(800);
    let finalHost = "";
    try { finalHost = new URL(page.url()).hostname.toLowerCase(); } catch (e) { finalHost = ""; }
    if (!sameSite(finalHost)) { rec.error = "offsite_redirect"; return rec; }
    const file = view.name + ".png";
    await page.screenshot({ path: path.join(input.outdir, file), fullPage: false });
    rec.file = file;
  } catch (e) {
    rec.error = message(e);
  } finally {
    await context.close().catch(() => {});
  }
  return rec;
}

(async () => {
  const result = { browser: "", error: null, shots: [] };
  let browser = null;
  try {
    const args = [];
    if (input.ip) { args.push("--host-resolver-rules=MAP " + input.host + " " + input.ip); }
    browser = await chromium.launch({ headless: true, args });
    result.browser = browser.version();
    const ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/" +
      result.browser + " Safari/537.36 " + input.ua_suffix;
    for (const view of VIEWS) {
      result.shots.push(await shoot(browser, input.urls[0], ua, view));
      await sleep(500);
    }
  } catch (e) {
    result.error = message(e);
  } finally {
    if (browser) { await browser.close().catch(() => {}); }
  }
  fs.writeFileSync(outPath, JSON.stringify(result));
})();
