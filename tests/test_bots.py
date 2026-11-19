from claudios.checks.ai_visibility import AI_BOTS
from claudios.core.engine import run_checks
from claudios.core.guard import normalize_input
from claudios.core.snapshot import Page, Snapshot

CONFIRMED = {"GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "anthropic-ai", "Claude-Web", "CCBot",
             "Google-Extended", "PerplexityBot", "Bytespider", "Applebot-Extended", "Amazonbot",
             "Meta-ExternalAgent", "cohere-ai"}
ADDED = {"Applebot", "Amzn-SearchBot", "Amzn-User", "AI2Bot", "Bravebot"}


def test_the_bot_list_is_unique_and_contains_the_confirmed_and_added_names():
    names = [name for name, _operator in AI_BOTS]
    assert len({name.lower() for name in names}) == len(names)
    assert CONFIRMED <= set(names) and ADDED <= set(names) and len(names) == 19
    assert all(operator.strip() for _name, operator in AI_BOTS)


def test_an_added_bot_is_recognised_in_robots_txt():
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.append(Page(url="https://example.com/", depth=1, status=200, html="<html></html>",
                           content_type="text/html"))
    snap.robots_txt = "User-agent: Applebot\nDisallow: /\n"
    snap.status = "complete"
    found, _ = run_checks(snap, 1, "standard")
    hits = [f for f in found if f.check_id == "SEO-AIC-001"]
    assert len(hits) == 1 and hits[0].evidence == "Applebot"
