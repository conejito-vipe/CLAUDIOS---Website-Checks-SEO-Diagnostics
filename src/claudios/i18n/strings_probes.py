"""Verständliche Namen für Zusatzprüfungen, die im Fortschritt erscheinen (statt des internen Kürzels)."""
from . import strings

strings.TEXTS["de"].update({"probe.extra": "Adress-Varianten, Bilder, Cache-Header und Datenschutzsignal",
                            "probe.cms": "Zusätzliche CMS-Pfade (Stufe 2)", "probe.ct": "Zertifikats-Logs (crt.sh)"})
strings.TEXTS["en"].update({"probe.extra": "Address variants, images, cache headers and privacy signal",
                            "probe.cms": "Extra CMS paths (level 2)", "probe.ct": "Certificate logs (crt.sh)"})
