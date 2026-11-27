"""Erklärung zu einem Befund. Ein Klick auf eine Zeile der Ergebnisliste öffnet einen Dialog mit dem Befund (Meldung, Beleg,
betroffene Adressen aus dem Scan), einem Codefenster (bei gespeicherten HTML-, CSS- und JavaScript-Dateien und Belegen mit
„Line N“: gelb für Hinweis und Warnung, rot für Fehler und kritisch) und der Beschreibung der Prüfung aus der Registry
(warum wichtig, wie beheben, wie geprüft, Quellen als Links). Gibt es kein Codefenster, obwohl der Beleg eine Zeile nennt,
steht der Grund im Dialog, dazu eine Zeile „Technische Angaben“ (auch im Protokoll). Fehlt die Befund-Liste ganz, steht auch
das da.

Die Liste selbst kennt diese Datei nicht: DetailLinker hängt sich an jede Tabelle, jeden Baum und jede Liste, in deren Zeile
eine Prüf-ID wie SEC-HDR-001 steht (Zeilen ohne ID machen nichts). Alles aus dem Scan wird maskiert; nur https-Adressen der
Quellen und der betroffenen Seiten werden zu Links. Zahlen in den Meldungen bekommen den Tausendertrenner der Sprache (nicht
im Beleg und nicht im Quelltext). Die Texte der Prüfung sind allgemein je Prüfung, nicht je Fundstelle."""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from functools import partial
from html import escape

from PySide6.QtCore import QEvent, QObject, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTextBrowser,
    QTextEdit,
    QTreeWidget,
    QWidget,
)

from ..checks import load_all
from ..core.numfmt import format_number
from ..core.numtext import localize_numbers
from ..core.redact import redact_url
from ..core.registry import REGISTRY
from ..i18n import strings_detail2  # noqa: F401 (legt die Texte der technischen Angaben an)
from ..i18n.strings import get_lang, t, text
from .cardbox import MARGIN, CardDialog
from .code_source import source_for

log = logging.getLogger("claudios")
ID = re.compile(r"\b[A-Z]{2,4}-[A-Z]{2,4}-\d{3}\b")
LINE = re.compile(r"\b(?:Line|Zeile)\s+(\d+)\b")
MAX_EVIDENCE = 400
MAX_LINE = 240
FLAG = "cl_detail"
COLORS = {"red": "#8A2B33", "yellow": "#7A6410", "blue": "#2A5A9A"}
HEAD = "font-size:15px;font-weight:700;margin-top:14px;margin-bottom:2px;"  # alle Überschriften gleich
LINK_CSS = "a { color: #FFFFFF; text-decoration: none; }"
HOVER = "#FF8A3D"
_NOCODE = {"result": "detail.nocode_result", "source": "detail.nocode_source", "range": "detail.nocode_range"}
_FACTS = {"result": "detail.facts_result", "source": "detail.facts_source", "range": "detail.facts_range"}


def find_id(texts) -> str | None:
    for item in texts:
        match = ID.search(item or "")
        if match:
            return match.group(0)
    return None


def meta_for(check_id: str):
    load_all()
    try:
        return getattr(REGISTRY[check_id], "meta", None)
    except KeyError:
        return None


def meta_text(meta, name: str, lang: str) -> str:
    """Text einer Prüfung in der Sprache: Wörterbuch {de, en}, Text mit ' ## ' oder einfacher Text."""
    value = getattr(meta, name, "") if meta is not None else ""
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("de") or "").strip()
    raw = str(value or "")
    if " ## " in raw:
        german, _sep, english = raw.partition(" ## ")
        return (german if lang == "de" else english).strip()
    return raw.strip()


def meta_refs(meta) -> list[str]:
    refs = getattr(meta, "refs", ()) if meta is not None else ()
    if isinstance(refs, str):
        refs = (refs,)
    return [str(ref) for ref in refs or () if str(ref).startswith("https://")]


def _severity(value, lang: str) -> str:
    try:
        return text(lang, f"sev.{int(value)}")
    except (KeyError, ValueError, TypeError):
        return str(value)


def _ordered(check_id: str, groups: list[dict], row_texts, lang: str) -> list[dict]:
    """Der angeklickte Befund zuerst, danach die übrigen Befunde derselben Prüfung. Die Zeile der Liste zeigt die Zahlen mit
    Tausendertrenner, deshalb wird auch die so geschriebene Meldung verglichen."""
    key = "msg_" + lang
    own = [g for g in groups if g.get("check_id") == check_id]
    clicked = next((g for g in own if g.get(key)
                    and any(g[key] in cell or localize_numbers(g[key], lang) in cell for cell in row_texts)), None)
    return ([clicked] if clicked is not None else []) + [g for g in own if g is not clicked]


# ------------------------------------------------------------------ Codefenster

def line_of(evidence: str) -> int | None:
    match = LINE.search(evidence or "")
    return int(match.group(1)) if match else None


def _page_html(result, urls) -> tuple[str, str] | None:
    pages = getattr(getattr(result, "snapshot", None), "pages", None) or []
    for url in urls:
        for page in pages:
            body = getattr(page, "html", None)
            if body and (page.url == url or redact_url(page.url) == url):
                return page.url, body
    return None


def _cut(line: str) -> str:
    line = line.rstrip("\r")
    return line[:MAX_LINE] + "…" if len(line) > MAX_LINE else line


def code_excerpt(result, urls, evidence: str, severity: int, context: int = 3,
                 check_id: str = "") -> dict | None:
    """Zeilen um die im Beleg genannte Zeile einer gespeicherten HTML-, CSS- oder JavaScript-Datei, sonst None."""
    number = line_of(evidence)
    found = source_for(result, urls, check_id)
    if number is None or found is None:
        return None
    lines = found[1].split("\n")
    if not 1 <= number <= len(lines):
        return None
    first, last = max(1, number - context), min(len(lines), number + context)
    color = "red" if severity >= 3 else "yellow" if severity >= 1 else "blue"
    return {"url": found[0], "line": number, "color": color,
            "lines": [(i, _cut(lines[i - 1]), i == number) for i in range(first, last + 1)]}


def excerpt_problem(result, urls, evidence: str, check_id: str = "") -> str | None:
    """Warum es kein Codefenster gibt, obwohl der Beleg eine Zeile nennt (result, source, range), sonst None."""
    number = line_of(evidence)
    if number is None:
        return None
    if result is None:
        return "result"
    found = source_for(result, urls, check_id)
    if found is None:
        return "source"
    if not 1 <= number <= len(found[1].split("\n")):
        return "range"
    return None


def excerpt_facts(result, urls, evidence: str, check_id: str = "") -> dict | None:
    """Der Grund aus excerpt_problem mit den Angaben, die zeigen, woran es liegt (Adresse, Zahl der gespeicherten Seiten und
    Dateien, Zeilenzahl). None, wenn es ein Codefenster gibt oder der Beleg keine Zeile nennt. Adressen sind maskiert."""
    reason = excerpt_problem(result, urls, evidence, check_id)
    if reason is None:
        return None
    facts: dict = {"reason": reason, "line": line_of(evidence), "url": redact_url(str(urls[0])) if urls else "-"}
    if reason == "source":
        snapshot = getattr(result, "snapshot", None)
        pages = [p for p in getattr(snapshot, "pages", None) or [] if getattr(p, "html", None)]
        extra = getattr(snapshot, "extra", None)
        assets = extra.get("assets") if isinstance(extra, dict) else None
        facts["pages"] = len(pages)
        facts["samples"] = [redact_url(str(p.url)) for p in pages[:3]]
        facts["assets"] = sum(len(assets.get(kind) or []) for kind in ("css", "js")) if isinstance(assets, dict) else 0
    elif reason == "range":
        found = source_for(result, urls, check_id)
        facts["lines"] = len(found[1].split("\n")) if found else 0
    return facts


def facts_text(facts: dict, lang: str) -> str:
    """Die Zeile „Technische Angaben“ in der Sprache (Zahlen mit Tausendertrenner)."""
    def num(value) -> str:
        return format_number(value, lang)

    line = facts.get("line")
    common = {"url": facts.get("url") or "-", "line": num(line) if line is not None else "-"}
    reason = facts.get("reason", "result")
    if reason == "source":
        return text(lang, _FACTS["source"], pages=num(facts.get("pages", 0)), assets=num(facts.get("assets", 0)),
                    samples=", ".join(facts.get("samples") or []) or "-", **common)
    if reason == "range":
        return text(lang, _FACTS["range"], lines=num(facts.get("lines", 0)), **common)
    return text(lang, _FACTS["result"], **common)


def excerpt_html(excerpt: dict, lang: str) -> str:
    rows = []
    for number, line, marked in excerpt["lines"]:
        row = f"{number:>5} | {escape(line)}"
        if marked:
            row = (f'<span style="background-color:{COLORS[excerpt["color"]]};color:#FFFFFF;font-weight:bold;">'
                   f'{row}</span>')
        rows.append(row)
    title = text(lang, "detail.code", url=redact_url(excerpt["url"]), line=excerpt["line"])
    return (f'<p style="{HEAD}">{escape(title)}</p><p style="color:#9AA7B5;">{escape(text(lang, "detail.legend"))}</p>'
            '<pre style="font-family: Consolas, Menlo, monospace; font-size: 13px; background-color:#05080C;">'
            + "\n".join(rows) + "</pre>")


# ------------------------------------------------------------------ Texte

def _section(title: str, body: str) -> list[str]:
    return [title, "-" * len(title), body, ""]


def _found(groups: list[dict], lang: str) -> str:
    parts = []
    for group in groups:
        head = f"[{_severity(group.get('severity', 0), lang)}] {localize_numbers(group.get('msg_' + lang, ''), lang)}"
        count = int(group.get("count") or 1)
        if count > 1:
            head += " (" + text(lang, "detail.times", count=count) + ")"
        block = [head]
        evidence = str(group.get("evidence") or "").strip()
        if evidence:
            block.append(f"  {text(lang, 'detail.evidence')}: {evidence[:MAX_EVIDENCE]}")
        urls = [str(url) for url in group.get("example_urls") or []]
        if urls:
            block.append(f"  {text(lang, 'detail.where')}: " + ", ".join(urls))
        parts.append("\n".join(block))
    return "\n\n".join(parts)


def explain_text(check_id: str, groups: list[dict], row_texts, lang: str, meta=None, with_title: bool = True) -> str:
    """Der Erklärtext als Klartext. Der angeklickte Befund steht zuerst."""
    ordered = _ordered(check_id, groups, row_texts, lang)
    lines: list[str] = []
    if with_title:
        lines += [f"{meta_text(meta, 'title', lang) or check_id} ({check_id})", ""]
    lines += _section(text(lang, "detail.found"), _found(ordered, lang) if ordered else text(lang, "detail.none"))
    if meta is None:
        lines += [text(lang, "detail.nometa"), ""]
    else:
        for label, name in (("detail.why", "why"), ("detail.fix", "fix"), ("detail.method", "method"),
                            ("detail.logic", "logic")):
            body = meta_text(meta, name, lang)
            if body:
                lines += _section(text(lang, label), body)
        refs = meta_refs(meta)
        if refs:
            lines += _section(text(lang, "detail.refs"), "\n".join(refs))
    return "\n".join(lines).rstrip() + "\n"


def _para(value: str) -> str:
    return "<p>" + escape(value).replace("\n", "<br>") + "</p>"


def _link(url: str) -> str:
    return f'<a href="{escape(url, quote=True)}">{escape(url)}</a>'


URL_RX = re.compile(r"""https://[^\s<>"']+""")


def _linkify(value: str) -> str:
    """Text mit anklickbaren https-Adressen (alles andere wird maskiert, ein Satzzeichen am Ende gehört nicht zur Adresse)."""
    out, last = [], 0
    for match in URL_RX.finditer(value):
        url = match.group(0).rstrip(".,;:!?)")
        out.append(escape(value[last:match.start()]))
        out.append(_link(url))
        last = match.start() + len(url)
    out.append(escape(value[last:]))
    return "".join(out)


def _group_html(group: dict, lang: str) -> str:
    """Ein Befund: Meldung, dann die betroffenen Stellen, danach die Belege."""
    message = localize_numbers(group.get("msg_" + lang, ""), lang)
    head = f"[{_severity(group.get('severity', 0), lang)}] {message}"
    count = int(group.get("count") or 1)
    if count > 1:
        head += " (" + text(lang, "detail.times", count=count) + ")"
    parts = [f"<p>{escape(head)}</p>"]
    urls = [str(url) for url in group.get("example_urls") or []]
    if urls:
        items = "".join("<li>" + (_link(url) if url.startswith("https://") else escape(url)) + "</li>" for url in urls)
        parts.append(f'<p style="{HEAD}">' + escape(text(lang, "detail.where")) + "</p><ul>" + items + "</ul>")
    evidence = str(group.get("evidence") or "").strip()
    if evidence:
        parts.append(f'<p style="{HEAD}">' + escape(text(lang, "detail.evidence")) + "</p><p>"
                     + _linkify(evidence[:MAX_EVIDENCE]) + "</p>")
    return "".join(parts)


def explain_html(check_id: str, groups: list[dict], row_texts, lang: str, meta=None, result=None) -> str:
    ordered = _ordered(check_id, groups, row_texts, lang)
    parts = [f'<p style="{HEAD}margin-top:0px;">{escape(text(lang, "detail.found"))}</p>']
    parts += [_group_html(group, lang) for group in ordered] or [_para(text(lang, "detail.none"))]
    if not ordered and result is not None:  # ein Scan liegt vor, aber die Befund-Liste fehlt: nicht stumm bleiben
        parts.append(_para(text(lang, "detail.nogroups")))
        log.info("no findings list for %s in the detail dialog", check_id)
    shown = False
    if result is not None:
        for group in ordered:
            excerpt = code_excerpt(result, group.get("example_urls") or [], str(group.get("evidence") or ""),
                                   int(group.get("severity") or 0), check_id=check_id)
            if excerpt is not None:
                parts.append(excerpt_html(excerpt, lang))
                shown = True
                break
    if not shown:
        for group in ordered:
            facts = excerpt_facts(result, group.get("example_urls") or [], str(group.get("evidence") or ""), check_id)
            if facts:
                parts.append(_para(text(lang, _NOCODE[facts["reason"]])))
                parts.append(_para(facts_text(facts, lang)))
                log.info("no code window for %s: %s", check_id, facts)
                break
    if meta is None:
        parts.append(_para(text(lang, "detail.nometa")))
    else:
        for label, name in (("detail.why", "why"), ("detail.fix", "fix"), ("detail.method", "method"),
                            ("detail.logic", "logic")):
            body = meta_text(meta, name, lang)
            if body:
                parts += [f'<p style="{HEAD}">{escape(text(lang, label))}</p>', _para(body)]
        refs = meta_refs(meta)
        if refs:
            parts += [f'<p style="{HEAD}">{escape(text(lang, "detail.refs"))}</p>',
                      "<p>" + "<br>".join(_link(r) for r in refs) + "</p>"]
    return "".join(parts)


class LinkHover(QObject):
    """Links in der Erklärung: weiß ohne Unterstreichung, orange unter der Maus (Qt kennt kein :hover für Links)."""

    def __init__(self, browser: QTextBrowser) -> None:
        super().__init__(browser)
        self.browser = browser
        browser.document().setDefaultStyleSheet(LINK_CSS)
        browser.viewport().setMouseTracking(True)
        browser.viewport().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt-Name)
        kind = event.type()
        if kind == QEvent.Type.MouseMove:
            self.mark(event.position().toPoint())
        elif kind == QEvent.Type.Leave:
            self.browser.setExtraSelections([])
        return False

    def mark(self, pos) -> None:
        href = self.browser.anchorAt(pos)
        selections = []
        if href:
            cursor = self.browser.cursorForPosition(pos)
            block = cursor.block()
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                fmt = fragment.charFormat()
                if (fmt.anchorHref() == href and fragment.position() <= cursor.position() <= fragment.position() + fragment.length()):
                    sel = QTextEdit.ExtraSelection()
                    sel.cursor = QTextCursor(self.browser.document())
                    sel.cursor.setPosition(fragment.position())
                    sel.cursor.setPosition(fragment.position() + fragment.length(), QTextCursor.MoveMode.KeepAnchor)
                    sel.format.setForeground(QColor(HOVER))
                    selections.append(sel)
                    break
                it += 1
        self.browser.setExtraSelections(selections)


class FindingDialog(CardDialog):
    """Ein Befund in der Vollansicht. Mit mehreren Zeilen (rows) lässt sich durch die Ergebnisse blättern."""

    def __init__(self, parent, check_id: str, groups: list[dict], row_texts, result=None, rows=None, index: int = 0) -> None:
        super().__init__(parent, t("detail.title"))
        self.groups, self.result = groups, result
        self.rows = list(rows) if rows else [row_texts]
        self.index = index if 0 <= index < len(self.rows) else 0
        self.check_id = check_id
        self.resize(2 * MARGIN + 740, 2 * MARGIN + 620)
        self.heading = QLabel()
        self.heading.setObjectName("h1")
        self.heading.setTextFormat(Qt.TextFormat.PlainText)
        self.heading.setWordWrap(True)
        self.content.addWidget(self.heading)
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.setOpenExternalLinks(False)
        self.view.anchorClicked.connect(self._open)
        self.hover = LinkHover(self.view)
        self.content.addWidget(self.view, 1)
        nav = QHBoxLayout()
        self.prev_btn, self.next_btn = QPushButton(t("detail.prev")), QPushButton(t("detail.next"))
        self.pos = QLabel()
        self.pos.setObjectName("muted")
        close = QPushButton(t("card.close"))
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        for widget in (self.prev_btn, self.pos, self.next_btn):
            nav.addWidget(widget)
        nav.addStretch(1)
        nav.addWidget(close)
        self.prev_btn.clicked.connect(lambda: self.step(-1))
        self.next_btn.clicked.connect(lambda: self.step(1))
        self.content.addLayout(nav)
        self.show_row()

    def step(self, delta: int) -> None:
        target = self.index + delta
        if 0 <= target < len(self.rows):
            self.index = target
            self.show_row()

    def show_row(self) -> None:
        texts = self.rows[self.index]
        lang = get_lang()
        self.check_id = find_id(texts) or self.check_id
        meta = meta_for(self.check_id)
        self.heading.setText(meta_text(meta, "title", lang) or self.check_id)
        self.view.document().setDefaultStyleSheet(LINK_CSS)
        self.view.setHtml(explain_html(self.check_id, self.groups, texts, lang, meta, self.result))
        many = len(self.rows) > 1
        for widget in (self.prev_btn, self.next_btn, self.pos):
            widget.setVisible(many)
        self.prev_btn.setEnabled(self.index > 0)
        self.next_btn.setEnabled(self.index < len(self.rows) - 1)
        self.pos.setText(f"{self.index + 1} / {len(self.rows)}")

    @staticmethod
    def _open(url: QUrl) -> None:
        if url.scheme() == "https":  # nur https, nie ein anderes Schema aus Inhalten
            QDesktopServices.openUrl(url)


def row_texts(table: QTableWidget, row: int) -> list[str]:
    """Texte einer Tabellenzeile; die Prüf-ID steht (für Laien unsichtbar) in den Daten der Zelle."""
    texts = []
    for col in range(table.columnCount()):
        cell = table.item(row, col)
        if cell is not None:
            texts.append(cell.text())
            hidden = cell.data(Qt.ItemDataRole.UserRole)
            if isinstance(hidden, str):
                texts.append(hidden)
    return texts


def _collect(root: QWidget, kind) -> list:
    found = root.findChildren(kind)
    return [root, *found] if isinstance(root, kind) else found


class DetailLinker(QObject):
    """Verbindet Ergebnislisten mit dem Erklär-Dialog. attach() darf beliebig oft aufgerufen werden."""

    def __init__(self, window, get_result: Callable[[], object]) -> None:
        super().__init__(window)
        self._window, self._get_result = window, get_result
        self._cached: tuple = (None, "", [])

    def attach(self, root: QWidget) -> None:
        for table in _collect(root, QTableWidget):
            self._decorate(table)
            if self._mark(table):
                table.cellClicked.connect(partial(self._table_click, table))
        for tree in _collect(root, QTreeWidget):
            if self._mark(tree):
                tree.itemClicked.connect(self._tree_click)
        for items in _collect(root, QListWidget):
            if self._mark(items):
                items.itemClicked.connect(self._list_click)

    @staticmethod
    def _mark(widget) -> bool:
        if widget.property(FLAG):
            return False
        widget.setProperty(FLAG, True)
        return True

    @staticmethod
    def _decorate(table: QTableWidget) -> None:
        """Nur die Befund-Tabelle (Spalte „Prüfung“) bekommt Hinweis und Hand-Zeiger."""
        known = {text("de", "res.col.check"), text("en", "res.col.check")}
        labels = {table.horizontalHeaderItem(c).text() for c in range(table.columnCount())
                  if table.horizontalHeaderItem(c) is not None}
        if known & labels:
            table.setToolTip(t("detail.hint"))
            table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)

    def _table_click(self, table: QTableWidget, row: int, _column: int) -> None:
        self.open_for(row_texts(table, row))

    def _tree_click(self, item, _column: int) -> None:
        self.open_for([item.text(c) for c in range(item.columnCount())])

    def _list_click(self, item) -> None:
        self.open_for([item.text()])

    def attach_results(self, table: QTableWidget) -> None:
        """Die Ergebnistabelle öffnet die Vollansicht; darin lässt sich durch alle Zeilen blättern."""
        self._decorate(table)
        if self._mark(table):
            table.cellClicked.connect(lambda row, _c: self._open_paged(table, row))

    def _open_paged(self, table: QTableWidget, row: int) -> None:
        rows = [row_texts(table, r) for r in range(table.rowCount()) if not table.isRowHidden(r)]
        rows = [texts for texts in rows if find_id(texts)]
        clicked = row_texts(table, row)
        index = next((i for i, texts in enumerate(rows) if texts == clicked), 0)
        self.open_for(clicked, rows, index)

    def _groups(self) -> list[dict]:
        result, lang = self._get_result(), get_lang()
        if result is None:
            return []
        if self._cached[0] is not result or self._cached[1] != lang:
            try:
                from ..report.report import build_report  # erst hier: der Bericht ist nur für die Anzeige nötig

                groups = build_report(result, lang)["findings"]
            except Exception as exc:  # noqa: BLE001 – ohne Einzelheiten zeigt der Dialog trotzdem die Prüfung
                log.warning("finding details unavailable: %r", exc)
                groups = []
            self._cached = (result, lang, groups)
        return self._cached[2]

    def open_for(self, texts, rows=None, index: int = 0) -> bool:
        check_id = find_id(texts)
        if check_id is None:
            return False
        FindingDialog(self._window, check_id, self._groups(), texts, self._get_result(), rows, index).exec()
        return True
