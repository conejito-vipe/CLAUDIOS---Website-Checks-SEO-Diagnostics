"use strict";
// Browser-Probe für Claudios: lädt eine Stichprobe von Seiten in Chromium und schreibt ein JSON-Ergebnis.
// Aufruf: node browser_probe.js eingabe.json ausgabe.json
// Sicherheitsregeln: Zertifikatsfehler werden nie ignoriert, Service Worker sind blockiert, Anfragen über
// unverschlüsseltes HTTP und an lokale Namen oder IP-Adressen werden abgebrochen, der Zielhost ist auf die
// vorher geprüfte öffentliche IP festgelegt, Cookies werden nur mit Namen und Flags gespeichert (nie Werte).

const fs = require("fs");
const { chromium } = require("playwright");

const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const outPath = process.argv[3];
const WIDTHS = [360, 768, 1280];
const REG = String(input.registrable || "").toLowerCase();
const AXE = input.axe ? fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8") : null;

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

async function checkPage(browser, url, ua) {
  const rec = {
    url, final_url: "", status: null, error: null, console: [], page_errors: [], failed: [], bad_status: [],
    third_party: {}, insecure_blocked: [], cookies: [], axe: null, axe_error: null, overflow: {}, metrics: {},
  };
  const context = await browser.newContext({
    userAgent: ua, viewport: { width: 1280, height: 800 }, serviceWorkers: "block", acceptDownloads: false,
  });
  let requests = 0;
  let bytes = 0;
  try {
    await context.addInitScript(() => {
      window.__m = { lcp: 0, cls: 0 };
      try {
        new PerformanceObserver((list) => {
          for (const e of list.getEntries()) { window.__m.lcp = e.startTime; }
        }).observe({ type: "largest-contentful-paint", buffered: true });
        new PerformanceObserver((list) => {
          for (const e of list.getEntries()) { if (!e.hadRecentInput) { window.__m.cls += e.value; } }
        }).observe({ type: "layout-shift", buffered: true });
      } catch (e) { /* Messung nicht verfügbar */ }
    });
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
      if ((m.type() === "error" || m.type() === "warning") && rec.console.length < 20) {
        rec.console.push({ type: m.type(), text: m.text().slice(0, 200) });
      }
    });
    page.on("pageerror", (e) => { if (rec.page_errors.length < 10) { rec.page_errors.push(message(e)); } });
    page.on("requestfailed", (r) => {
      if (r.url().startsWith("http:") || rec.failed.length >= 20) { return; }
      rec.failed.push({ url: r.url().slice(0, 200), reason: ((r.failure() || {}).errorText || "").slice(0, 80) });
    });
    page.on("response", (r) => {
      requests += 1;
      const length = parseInt(r.headers()["content-length"] || "0", 10);
      if (length > 0) { bytes += length; }
      if (r.status() >= 400 && rec.bad_status.length < 20) {
        rec.bad_status.push({ url: r.url().slice(0, 200), status: r.status() });
      }
      let host = "";
      try { host = new URL(r.url()).hostname.toLowerCase(); } catch (e) { host = ""; }
      if (host && !sameSite(host)) { rec.third_party[host] = (rec.third_party[host] || 0) + 1; }
    });

    const response = await page.goto(url, { waitUntil: "load", timeout: 30000 });
    rec.status = response ? response.status() : null;
    rec.final_url = page.url();
    await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {});
    await sleep(1000);
    let finalHost = "";
    try { finalHost = new URL(page.url()).hostname.toLowerCase(); } catch (e) { finalHost = ""; }
    if (!sameSite(finalHost)) { rec.error = "offsite_redirect"; return rec; }

    const cookies = await context.cookies();
    rec.cookies = cookies.slice(0, 100).map((c) => ({
      name: String(c.name).slice(0, 100), secure: c.secure, httpOnly: c.httpOnly, sameSite: c.sameSite,
      domain: String(c.domain).slice(0, 100),
    }));
    const m = await page.evaluate(() => window.__m || { lcp: 0, cls: 0 });
    rec.metrics = { lcp: Math.round(m.lcp), cls: Math.round(m.cls * 1000) / 1000, requests, bytes };

    if (AXE) {
      try {
        await page.evaluate(AXE);
        if (!(await page.evaluate(() => typeof window.axe !== "undefined"))) {
          await page.addScriptTag({ content: AXE });
        }
        rec.axe = await page.evaluate(async () => {
          const result = await window.axe.run(document, {
            runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
            resultTypes: ["violations"],
          });
          return result.violations.map((v) => ({
            id: v.id, impact: v.impact, help: String(v.help).slice(0, 120), url: v.helpUrl, nodes: v.nodes.length,
          }));
        });
      } catch (e) { rec.axe_error = message(e); }
    }

    for (const width of WIDTHS) {
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
  const result = { browser: "", error: null, pages: [] };
  let browser = null;
  try {
    const args = [];
    if (input.ip) { args.push("--host-resolver-rules=MAP " + input.host + " " + input.ip); }
    browser = await chromium.launch({ headless: true, args });
    result.browser = browser.version();
    const ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/" +
      result.browser + " Safari/537.36 " + input.ua_suffix;
    for (const url of input.urls) {
      result.pages.push(await checkPage(browser, url, ua));
      await sleep(700);
    }
  } catch (e) {
    result.error = message(e);
  } finally {
    if (browser) { await browser.close().catch(() => {}); }
  }
  fs.writeFileSync(outPath, JSON.stringify(result));
})();
