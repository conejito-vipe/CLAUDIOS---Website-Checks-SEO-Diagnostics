"""Klartext-Titel der Prüfungen für die Listen (statt der Kennung wie CSS-VAL-001; die Kennung steht in den Daten der Zelle
und im Titel der Erklärung)."""
from __future__ import annotations

from .finding_detail import meta_for, meta_text


def check_title(check_id: str, lang: str) -> str:
    title = meta_text(meta_for(check_id), "title", lang)
    return title or check_id
