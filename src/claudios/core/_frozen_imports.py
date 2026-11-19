"""Sorgt dafür, dass PyInstaller alle Teile von httpx, httpcore und h2 einsammelt, die dnspython für DNS über HTTPS
braucht. dnspython lädt httpcore._backends.sync nur indirekt; fehlt es im gebauten Programm, meldet dnspython NoDOH
und kein Scan kann eine Domain auflösen. Diese Datei wird nur wegen ihrer Importe gebraucht."""
from __future__ import annotations

try:
    import h2.config  # noqa: F401
    import h2.connection  # noqa: F401
    import h2.events  # noqa: F401
    import hpack  # noqa: F401
    import httpcore._backends.sync  # noqa: F401
    import httpx  # noqa: F401
    import hyperframe.frame  # noqa: F401
except ImportError:  # in der Entwicklung nicht schlimm, im gebauten Programm meldet app.py das beim Start
    pass


def doh_available() -> bool:
    """True, wenn dnspython DNS über HTTPS nutzen kann."""
    import dns.query

    flag = getattr(dns.query, "have_doh", None)
    if flag is not None:
        return bool(flag)
    try:
        import httpcore._backends.sync  # noqa: F401
        import httpx  # noqa: F401
    except ImportError:
        return False
    return True
