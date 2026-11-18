"""KI-Sichtbarkeit: Regeln der robots.txt für bekannte KI-Crawler (keine neue Anfrage) und die llms.txt (Daten aus der
Probe core/probe_ai.py). Beides sind Entscheidungen des Betreibers, deshalb gibt es höchstens Hinweise."""
from __future__ import annotations

import re

from ..core.registry import check
from ._util import CheckSkipped, F, S
from .seo_extra import _parse_robots

# Namen und Betreiber aus dem Gedächtnis nach öffentlichen Listen, ungeprüft. Bots ändern ihre Namen.
AI_BOTS = (
    ("GPTBot", "OpenAI"), ("OAI-SearchBot", "OpenAI"), ("ChatGPT-User", "OpenAI"),
    ("ClaudeBot", "Anthropic"), ("anthropic-ai", "Anthropic"), ("Claude-Web", "Anthropic"),
    ("CCBot", "Common Crawl"), ("Google-Extended", "Google"), ("PerplexityBot", "Perplexity"),
    ("Bytespider", "ByteDance"), ("Applebot-Extended", "Apple"), ("Amazonbot", "Amazon"),
    ("Meta-ExternalAgent", "Meta"), ("cohere-ai", "Cohere"),
)
_LINK = re.compile(r"\[[^\]\n]{1,200}\]\(([^)\s]{1,500})\)")


def _state(groups, agent: str) -> str:
    """unset | blocked | partial | allowed für einen User-agent-Namen (kleingeschrieben)."""
    if not any(agent in agents for agents, _rules in groups):
        return "unset"
    rules = [rule for agents, group in groups if agent in agents for rule in group]
    block_all = any(d == "disallow" and v.strip() == "/" for d, v in rules)
    allow_all = any(d == "allow" and v.strip() == "/" for d, v in rules)
    if block_all and not allow_all:
        return "blocked"
    if any(d == "disallow" and v.strip() not in ("", "/") for d, v in rules):
        return "partial"
    return "allowed"


@check("SEO-AIC-001",
       title="KI-Crawler in der robots.txt ## AI crawlers in robots.txt",
       why="KI-Dienste lesen Websites für Training und für Antworten. Über die robots.txt entscheidet der Betreiber, "
           "welche Crawler das dürfen. Eine bewusste Entscheidung ist besser als ein Zufall, etwa durch eine "
           "Komplettsperre für alle. ## AI services read websites for training and for answers. With robots.txt the "
           "operator decides which crawlers may do so. A deliberate decision is better than an accident, for example "
           "a full block for everyone.",
       method="Wertet die beim Crawl geholte robots.txt aus (keine neue Anfrage) und sucht Regeln für 14 bekannte "
              "KI-Crawler (zum Beispiel GPTBot, ClaudeBot, CCBot, Google-Extended, PerplexityBot). Die Namen stammen "
              "aus öffentlichen Listen und sind ungeprüft. Google-Extended steuert nur die KI-Nutzung bei Google, "
              "nicht die normale Suche. Die robots.txt ist eine Bitte, keine Sperre: Nicht jeder Crawler hält sich "
              "daran. ## Evaluates the robots.txt fetched during the crawl (no new request) and looks for rules for 14 "
              "known AI crawlers (for example GPTBot, ClaudeBot, CCBot, Google-Extended, PerplexityBot). The names come "
              "from public lists and are unverified. Google-Extended only controls AI use at Google, not normal "
              "search. robots.txt is a request, not a lock: not every crawler obeys it.",
       logic="Nur Info: gesperrt, teilweise gesperrt, ausdrücklich erlaubt, durch die Regel für * mitgesperrt oder "
             "keine Regeln für KI-Crawler. ## Info only: blocked, partly blocked, explicitly allowed, blocked by the "
             "rule for *, or no rules for AI crawlers.",
       fix="Entscheiden, welche KI-Crawler Inhalte nutzen dürfen, und je Crawler einen Block User-agent: GPTBot mit "
           "Allow: / oder Disallow: / eintragen. ## Decide which AI crawlers may use your content and add a block "
           "such as User-agent: GPTBot with Allow: / or Disallow: / for each crawler.",
       refs=["https://www.rfc-editor.org/rfc/rfc9309", "https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers"],
       profiles="sd")
def ai_crawlers(snap):
    if snap.robots_txt is None:
        raise CheckSkipped("no_robots_txt")
    groups = _parse_robots(snap.robots_txt)["groups"]
    states = {name: _state(groups, name.lower()) for name, _operator in AI_BOTS}
    star_blocks = _state(groups, "*") == "blocked"
    url, out = snap.target.url, []

    def names(kind: str) -> list[str]:
        return [name for name, state in states.items() if state == kind]

    blocked, partial, allowed, unset = names("blocked"), names("partial"), names("allowed"), names("unset")
    if blocked:
        out.append(F("SEO-AIC-001", S.INFO, url, f"{len(blocked)} KI-Crawler sind in der robots.txt gesperrt",
                     f"{len(blocked)} AI crawler(s) are blocked in robots.txt", ", ".join(blocked)))
    if partial:
        out.append(F("SEO-AIC-001", S.INFO, url, f"{len(partial)} KI-Crawler sind teilweise eingeschränkt",
                     f"{len(partial)} AI crawler(s) are partly restricted", ", ".join(partial)))
    if allowed:
        out.append(F("SEO-AIC-001", S.INFO, url, f"{len(allowed)} KI-Crawler sind ausdrücklich erlaubt",
                     f"{len(allowed)} AI crawler(s) are explicitly allowed", ", ".join(allowed)))
    if star_blocks and unset:
        out.append(F("SEO-AIC-001", S.INFO, url,
                     f"{len(unset)} weitere KI-Crawler sind durch die Regel für * mitgesperrt",
                     f"{len(unset)} more AI crawler(s) are blocked by the rule for *", ", ".join(unset)))
    elif not (blocked or partial or allowed or star_blocks):
        out.append(F("SEO-AIC-001", S.INFO, url, "Die robots.txt enthält keine Regeln für bekannte KI-Crawler",
                     "The robots.txt contains no rules for known AI crawlers"))
    return out


@check("SEO-LLM-001",
       title="llms.txt (Hinweisdatei für KI-Dienste) ## llms.txt (hint file for AI services)",
       why="Die Datei llms.txt ist ein Vorschlag, KI-Diensten eine knappe Übersicht der wichtigsten Seiten in Markdown "
           "zu geben. Sie ist kein anerkannter Standard, und ob Dienste sie nutzen, ist offen. Ist sie vorhanden, "
           "sollte sie wenigstens der Form entsprechen. ## llms.txt is a proposal to give AI services a short "
           "overview of the most important pages in Markdown. It is not an accepted standard and it is open whether "
           "services use it. If present, it should at least follow the format.",
       method="Ruft /llms.txt einmal über den Gatekeeper ab (höchstens 200.000 Bytes) und prüft: beginnt die Datei mit "
              "einer H1-Überschrift, gibt es Markdown-Links, und ob Links unverschlüsselt sind. Das Format stammt aus "
              "dem Gedächtnis (llmstxt.org) und ist ungeprüft. ## Fetches /llms.txt once through the gatekeeper (at "
              "most 200,000 bytes) and checks: does the file start with an H1 heading, are there Markdown links, and "
              "are links unencrypted. The format comes from memory (llmstxt.org) and is unverified.",
       logic="Fehlt: Info. HTML statt Text, keine H1, keine Links oder unverschlüsselte Links: Hinweis. ## Missing: "
             "info. HTML instead of text, no H1, no links or unencrypted links: note.",
       fix="Optional: /llms.txt mit # Name, einer kurzen Beschreibung und Abschnitten mit Links [Titel](https://...) "
           "anlegen. ## Optional: create /llms.txt with # Name, a short description and sections with links "
           "[title](https://...).",
       refs=["https://llmstxt.org/"], profiles="sd", source="network")
def llms_txt(snap):
    data = snap.extra.get("ai")
    if data is None:
        raise CheckSkipped("no_ai_data")
    rec = data.get("llms")
    if not isinstance(rec, dict) or rec.get("error"):
        raise CheckSkipped("llms_unreachable")
    url, status = snap.target.url, rec.get("status")
    if status in (404, 410):
        return [F("SEO-LLM-001", S.INFO, url, "Keine llms.txt gefunden (optional)", "No llms.txt found (optional)")]
    if status != 200:
        return [F("SEO-LLM-001", S.INFO, url, f"llms.txt antwortet mit HTTP {status}",
                  f"llms.txt answers with HTTP {status}")]
    text, ctype = str(rec.get("text", "")), str(rec.get("content_type", ""))
    if "html" in ctype or text.lstrip().lower().startswith(("<!doctype", "<html")):
        return [F("SEO-LLM-001", S.NOTE, url, "llms.txt liefert HTML statt Text (vermutlich eine Fehlerseite)",
                  "llms.txt returns HTML instead of text (probably an error page)")]
    lines = [line.strip() for line in text.lstrip("\ufeff").splitlines()[:2000]]
    filled = [line for line in lines if line]
    if not filled:
        return [F("SEO-LLM-001", S.NOTE, url, "llms.txt ist leer", "llms.txt is empty")]
    out = []
    if not filled[0].startswith("# "):
        out.append(F("SEO-LLM-001", S.NOTE, url, "llms.txt beginnt nicht mit einer H1-Überschrift (# Name)",
                     "llms.txt does not start with an H1 heading (# name)", filled[0][:60]))
    links = _LINK.findall(text)
    if not links:
        out.append(F("SEO-LLM-001", S.NOTE, url, "llms.txt enthält keine Markdown-Links",
                     "llms.txt contains no Markdown links"))
    else:
        insecure = [link for link in links if link.lower().startswith("http:")]
        if insecure:
            out.append(F("SEO-LLM-001", S.NOTE, url, f"{len(insecure)} Link(s) in der llms.txt ohne HTTPS",
                         f"{len(insecure)} link(s) in llms.txt without HTTPS", insecure[0][:80]))
    if rec.get("truncated"):
        out.append(F("SEO-LLM-001", S.INFO, url, "llms.txt wurde nur teilweise ausgewertet (sehr groß)",
                     "llms.txt was only partly evaluated (very large)"))
    return out
