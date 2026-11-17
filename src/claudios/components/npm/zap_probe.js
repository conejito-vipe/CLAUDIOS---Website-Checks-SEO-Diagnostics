"use strict";
// ZAP-Probe für Claudios: lädt eine Stichprobe von Seiten in Chromium, das durch einen lokalen ZAP-Proxy läuft.
// Aufruf: node zap_probe.js eingabe.json ausgabe.json
// Zertifikate: Das Root-Zertifikat von ZAP wird NICHT installiert. Chromium bekommt nur den SPKI-Hash dieses einen
// Zertifikats für diesen einen Lauf (Pin). Andere Zertifikatsfehler werden nie ignoriert.
// Sicherheitsregeln wie in browser_probe.js: Service Worker blockiert, frisches Profil je Seite, Anfragen über
// unverschlüsseltes HTTP und an lokale Namen oder IP-Adressen werden abgebrochen.

const fs = require("fs");
const crypto = require("crypto");
const { chromium } = require("playwright");

const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const outPath = process.argv[3];
const REG = String(input.registrable || "").toLowerCase();

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const sameSite = (host) => host === REG || host.endsWith("." + REG);
const isLocalName = (host) =>
  host === "localhost" || host.endsWith(".local") || host.endsWith(".internal") ||
  host.startsWith("[") || /^\d+\.\d+\.\d+\.\d+$/.test(host);
const message = (e) => String((e && e.message) || e).slice(0, 200);

function spkiHash(pemPath) {
  const cert = new crypto.X509Certificate(fs.readFileSync(pemPath));
  const der = cert.publicKey.export({ type: "spki", format: "der" });
  return crypto.createHash("sha256").update(der).digest("base64");
}

async function visit(browser, url, ua) {
  const rec = { url, status: null, error: null };
  const context = await browser.newContext({ userAgent: ua, serviceWorkers: "block", acceptDownloads: false });
  try {
    await context.route("**/*", async (route) => {
      let u;
      try { u = new URL(route.request().url()); } catch (e) { return route.abort(); }
      const host = u.hostname.toLowerCase();
      if (u.protocol === "http:") { return route.abort(); }
      if (u.protocol === "https:" && isLocalName(host)) { return route.abort(); }
      return route.continue();
    });
    const page = await context.newPage();
    const response = await page.goto(url, { waitUntil: "load", timeout: 30000 });
    rec.status = response ? response.status() : null;
    await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {});
    await sleep(1000);
    let finalHost = "";
    try { finalHost = new URL(page.url()).hostname.toLowerCase(); } catch (e) { finalHost = ""; }
    if (!sameSite(finalHost)) { rec.error = "offsite_redirect"; }
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
    const pin = spkiHash(input.cert_path);
    browser = await chromium.launch({
      headless: true,
      proxy: { server: "http://127.0.0.1:" + input.proxy_port },
      args: ["--ignore-certificate-errors-spki-list=" + pin],
    });
    result.browser = browser.version();
    const ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36 " +
      input.ua_suffix;
    for (const url of input.urls) {
      result.pages.push(await visit(browser, url, ua));
      await sleep(700);
    }
  } catch (e) {
    result.error = message(e);
  } finally {
    if (browser) { await browser.close().catch(() => {}); }
  }
  fs.writeFileSync(outPath, JSON.stringify(result));
})();
