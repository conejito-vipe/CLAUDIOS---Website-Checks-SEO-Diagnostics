"use strict";
// Messung für Firefox und WebKit (nur auf dem GitHub-Rechner, nicht im Programm).
// Aufruf: node measure_browsers.js <ip von example.com> ausgabe.json
// Prüft: starten die Browser, laden sie eine Seite, und beachtet Firefox die Einstellung network.dns.forceResolve?
// Der Test mit 127.0.0.1 muss scheitern, wenn die Einstellung wirkt. Sie gilt dann für ALLE Hosts, nicht nur für einen.
const fs = require("fs");
const { firefox, webkit } = require("playwright");

const ip = process.argv[2] || "";
const outPath = process.argv[3];
const TARGET = "https://example.com/";

async function load(name, type, options) {
  const rec = { engine: name, ok: false, version: "", status: null, title: "", ms: 0, error: null };
  const started = Date.now();
  let browser = null;
  try {
    browser = await type.launch(options);
    rec.version = browser.version();
    const page = await browser.newPage();
    const response = await page.goto(TARGET, { waitUntil: "load", timeout: 45000 });
    rec.status = response ? response.status() : null;
    rec.title = (await page.title()).slice(0, 80);
    rec.ok = rec.status === 200;
  } catch (e) {
    rec.error = String((e && e.message) || e).slice(0, 200);
  } finally {
    if (browser) { await browser.close().catch(() => {}); }
    rec.ms = Date.now() - started;
  }
  return rec;
}

(async () => {
  const results = [];
  results.push(await load("firefox", firefox, { headless: true }));
  results.push(await load("webkit", webkit, { headless: true }));
  if (ip) {
    results.push(await load("firefox+forceResolve(richtige IP)", firefox,
      { headless: true, firefoxUserPrefs: { "network.dns.forceResolve": ip } }));
    results.push(await load("firefox+forceResolve(127.0.0.1, muss scheitern)", firefox,
      { headless: true, firefoxUserPrefs: { "network.dns.forceResolve": "127.0.0.1" } }));
  }
  fs.writeFileSync(outPath, JSON.stringify(results));
})();
