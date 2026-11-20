# Google-Zugang einrichten

English version: [GOOGLE_SETUP.md](GOOGLE_SETUP.md)

CLAUDIOS braucht einen eigenen OAuth-Client. Er gehört dir, nicht dem Programm. Die Namen der Menüs unten stammen aus dem Gedächtnis und können abweichen.

1. Öffne https://console.cloud.google.com und lege ein **neues Projekt** an.
2. **APIs & Dienste → Bibliothek:** „Google Search Console API“ aktivieren.
3. **OAuth-Zustimmungsbildschirm:** Typ „Extern“, Name „CLAUDIOS“, deine E-Mail-Adresse eintragen. Füge dich unter „Testnutzer“ hinzu. Der Bereich `.../auth/webmasters.readonly` ist der einzige, den CLAUDIOS anfordert. Im Status „Testing“ laufen Anmeldungen nach meinem Stand nach 7 Tagen ab. Du meldest dich dann neu an.
4. **Anmeldedaten → Anmeldedaten erstellen → OAuth-Client-ID:** Anwendungstyp **„Desktop-App“** (nicht „Web“).
5. **JSON herunterladen.** In CLAUDIOS: Seite „Search Console“ → „client_secret.json importieren“.
6. **Lösche die heruntergeladene Datei danach** und lade sie niemals auf GitHub hoch (die `.gitignore` blockiert `client_secret*.json`). CLAUDIOS speichert den Client im Windows-Anmeldeinformationsspeicher.
7. „Mit Google anmelden“ klicken. Es öffnet sich dein Browser. Bei der Warnung „nicht verifizierte App“ weiter nur, wenn es dein eigenes Projekt ist.
8. Danach siehst du deine Properties. Hast du für eine Inhaber- oder Vollzugriff, kannst du Stufe 2 einschalten.

CLAUDIOS sieht dein Google-Passwort nie. Es fragt nur Lesezugriff an: Property-Liste, Sitemaps, URL-Inspektion und Seiten-Impressionen (keine Suchbegriffe).

## Optional: API-Schlüssel für Safe Browsing

Nur nötig, wenn du Safe Browsing auf der Seite „Externe Dienste“ einschaltest. Erstelle im selben Google-Cloud-Projekt einen API-Schlüssel und aktiviere die „Safe Browsing API“ (Menünamen aus dem Gedächtnis). Füge den Schlüssel auf der Seite „Externe Dienste“ ein. Er liegt im Windows-Anmeldeinformationsspeicher, nie in einer Datei oder im Bericht.
