"""Klartext-Namen der Prüfbereiche (statt der drei Buchstaben der Prüf-Kennungen) und weitere Texte der Oberfläche,
die auch für Laien auf den ersten Blick verständlich sein sollen."""
from . import strings

CATEGORIES = {
    "ADS": ("Werbedatei", "Ad file"), "BRW": ("Browser", "Browser"), "CSS": ("CSS", "CSS"), "DNS": ("DNS & E-Mail", "DNS & email"),
    "EXP": ("Offene Dateien", "Exposed files"), "GSC": ("Search Console", "Search Console"), "HTM": ("HTML", "HTML"),
    "JSS": ("JavaScript", "JavaScript"), "LNK": ("Links", "Links"), "PRV": ("Datenschutz", "Privacy"),
    "SEC": ("Sicherheit", "Security"), "SEO": ("Suchmaschinen", "Search engines"), "SYS": ("System", "System"),
    "TKO": ("Übernahme", "Takeover"), "TLS": ("Verschlüsselung", "Encryption"), "ZAP": ("ZAP-Scan", "ZAP scan"),
}
strings.TEXTS["de"].update({f"cat.{key}": de for key, (de, _en) in CATEGORIES.items()})
strings.TEXTS["en"].update({f"cat.{key}": en for key, (_de, en) in CATEGORIES.items()})


def category_name(key: str) -> str:
    """Klartext-Name des Bereichs; unbekannte Kürzel bleiben, wie sie sind."""
    try:
        return strings.t(f"cat.{key}")
    except KeyError:
        return key
