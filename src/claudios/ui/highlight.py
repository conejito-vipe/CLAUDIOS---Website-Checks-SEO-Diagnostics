"""Syntax-Hervorhebung für die Technik-Doku. Das Dokumentformat erzeugt docs.py: Prosa-Zeilen, dann eine Zeile 'Code:',
danach der Quelltext bis zur Trennlinie aus '-'. Nur im Code-Teil wird als Python eingefärbt."""
from __future__ import annotations

import keyword
import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

STATE_TEXT, STATE_CODE, STATE_TRIPLE_D, STATE_TRIPLE_S = 0, 1, 2, 3
CODE_LABEL = "Code:"
COLORS = {"keyword": "#0B5CAD", "string": "#2E7D32", "comment": "#7A7A7A", "number": "#B25000",
          "deco": "#7B3FA0", "header": "#EE6A12", "label": "#1B2A33", "rule": "#B0B8BF"}
_HEADER = re.compile(r"^\[[A-Z]{3}-[A-Z]{3}-\d{3}\]")
_LABEL = re.compile(r"^(?:Warum\?|Why\?|(?:Behebung|Fix|Referenzen|References|Methode|Method|Bewertung|Rating|"
                    r"Art|Type|Code|Profile|Profiles)(?=:))")
_DECO = re.compile(r"\s*(@[\w.]+)")
_TOKEN = re.compile(
    r"""(?P<comment>\#.*$)|(?P<triple>\"\"\"|''')|"""
    r"""(?P<string>[rbfRBF]{0,2}"(?:[^"\\]|\\.)*"|[rbfRBF]{0,2}'(?:[^'\\]|\\.)*')|"""
    r"""(?P<number>\b\d[\d_.]*\b)|(?P<word>[A-Za-z_]\w*)""")


def _format(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


def _is_rule(text: str) -> bool:
    return len(text) >= 20 and set(text) == {"-"}


class CodeHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._f = {
            "keyword": _format(COLORS["keyword"], bold=True), "string": _format(COLORS["string"]),
            "comment": _format(COLORS["comment"], italic=True), "number": _format(COLORS["number"]),
            "deco": _format(COLORS["deco"]), "header": _format(COLORS["header"], bold=True),
            "label": _format(COLORS["label"], bold=True), "rule": _format(COLORS["rule"])}

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Name von Qt)
        previous = max(self.previousBlockState(), STATE_TEXT)
        if _is_rule(text):
            self.setFormat(0, len(text), self._f["rule"])
            self.setCurrentBlockState(STATE_TEXT)
            return
        if previous == STATE_TEXT:
            self.setCurrentBlockState(STATE_CODE if text.strip() == CODE_LABEL else STATE_TEXT)
            self._prose(text)
            return
        self.setCurrentBlockState(self._code(text, previous))

    def _prose(self, text: str) -> None:
        if _HEADER.match(text):
            self.setFormat(0, len(text), self._f["header"])
            return
        label = _LABEL.match(text)
        if label:
            self.setFormat(0, label.end(), self._f["label"])

    def _code(self, text: str, state: int) -> int:
        size, pos = len(text), 0
        if state in (STATE_TRIPLE_D, STATE_TRIPLE_S):
            quote = '"""' if state == STATE_TRIPLE_D else "'''"
            end = text.find(quote)
            if end < 0:
                self.setFormat(0, size, self._f["string"])
                return state
            pos = end + 3
            self.setFormat(0, pos, self._f["string"])
        else:
            deco = _DECO.match(text)
            if deco:
                self.setFormat(deco.start(1), deco.end(1) - deco.start(1), self._f["deco"])
                pos = deco.end()
        while pos < size:
            match = _TOKEN.search(text, pos)
            if match is None:
                break
            kind = match.lastgroup
            if kind == "comment":
                self.setFormat(match.start(), size - match.start(), self._f["comment"])
                break
            if kind == "triple":
                quote = match.group()
                end = text.find(quote, match.end())
                if end < 0:
                    self.setFormat(match.start(), size - match.start(), self._f["string"])
                    return STATE_TRIPLE_D if quote == '"""' else STATE_TRIPLE_S
                self.setFormat(match.start(), end + 3 - match.start(), self._f["string"])
                pos = end + 3
                continue
            if kind == "word" and keyword.iskeyword(match.group()):
                self.setFormat(match.start(), match.end() - match.start(), self._f["keyword"])
            elif kind in ("string", "number"):
                self.setFormat(match.start(), match.end() - match.start(), self._f[kind])
            pos = match.end()
        return STATE_CODE


def attach(view) -> CodeHighlighter:
    """Hängt die Hervorhebung an ein Textfeld. Der Highlighter gehört dem Dokument und lebt damit so lange wie dieses."""
    return CodeHighlighter(view.document())
