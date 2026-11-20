"""Erklärung zu einem Befund. Ein Klick auf eine Zeile der Ergebnisliste öffnet einen Dialog mit dem Befund (Meldung, Beleg,
betroffene Adressen aus dem Scan) und der Beschreibung der Prüfung aus der Registry (warum wichtig, wie beheben, wie geprüft).

Die Liste selbst kennt diese Datei nicht: DetailLinker hängt sich an jede Tabelle, jeden Baum und jede Liste, in deren Zeile eine
Prüf-ID wie SEC-HDR-001 steht (Zeilen ohne ID machen nichts). Alle Texte aus dem Scan werden als Klartext angezeigt, nie als
Rich-Text. Die Texte der Prüfung sind allgemein je Prüfung, nicht je Fundstelle."""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from functools import partial

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QLabel, QListWidget, QPlainTextEdit, QPushButton, QTableWidget, QTreeWidget, QWidget

from ..checks import load_all
from ..core.registry import REGISTRY
from ..i18n.strings import get_lang, t, text
from .cardbox import MARGIN, CardDialog

log = logging.getLogger("claudios")
ID = re.compile(r"\b[A-Z]{2,4}-[A-Z]{2,4}-\d{3}\b")
MAX_EVIDENCE = 400
FLAG = "cl_detail"


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


def _section(title: str, body: str) -> list[str]:
    return [title, "-" * len(title), body, ""]


def _severity(value, lang: str) -> str:
    try:
        return text(lang, f"sev.{int(value)}")
    except (KeyError, ValueError, TypeError):
        return str(value)


def _found(groups: list[dict], lang: str) -> str:
    parts = []
    for group in groups:
        head = f"[{_severity(group.get('severity', 0), lang)}] {group.get('msg_' + lang, '')}"
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
    """Der Erklärtext. Der angeklickte Befund steht zuerst, danach die übrigen Befunde derselben Prüfung."""
    key = "msg_" + lang
    own = [g for g in groups if g.get("check_id") == check_id]
    clicked = next((g for g in own if g.get(key) and any(g[key] in cell for cell in row_texts)), None)
    ordered = ([clicked] if clicked is not None else []) + [g for g in own if g is not clicked]
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


class FindingDialog(CardDialog):
    def __init__(self, parent, check_id: str, groups: list[dict], row_texts) -> None:
        super().__init__(parent, t("detail.title"))
        self.check_id = check_id
        self.resize(2 * MARGIN + 700, 2 * MARGIN + 580)
        lang = get_lang()
        meta = meta_for(check_id)
        heading = QLabel(f"{meta_text(meta, 'title', lang) or check_id} ({check_id})")
        heading.setObjectName("h1")
        heading.setTextFormat(Qt.TextFormat.PlainText)
        heading.setWordWrap(True)
        self.content.addWidget(heading)
        self.view = QPlainTextEdit(explain_text(check_id, groups, row_texts, lang, meta, with_title=False))
        self.view.setReadOnly(True)
        self.content.addWidget(self.view, 1)
        close = QPushButton(t("card.close"))
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        self.content.addWidget(close)


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
        cells = (table.item(row, c) for c in range(table.columnCount()))
        self.open_for([cell.text() if cell is not None else "" for cell in cells])

    def _tree_click(self, item, _column: int) -> None:
        self.open_for([item.text(c) for c in range(item.columnCount())])

    def _list_click(self, item) -> None:
        self.open_for([item.text()])

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

    def open_for(self, texts) -> bool:
        check_id = find_id(texts)
        if check_id is None:
            return False
        FindingDialog(self._window, check_id, self._groups(), texts).exec()
        return True
