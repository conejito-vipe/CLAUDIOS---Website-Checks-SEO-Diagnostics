# Google-Zugang einrichten / Setting up Google access

Claudios braucht einen eigenen OAuth-Client. Er gehört dir, nicht dem Programm. / Claudios needs your own OAuth
client. It belongs to you, not to the program. The names of the menus below are from memory and may differ.

1. Öffne https://console.cloud.google.com und lege ein **neues Projekt** an. / Create a **new project**.
2. **APIs & Dienste → Bibliothek:** „Google Search Console API“ aktivieren. / Enable "Google Search Console API".
3. **OAuth-Zustimmungsbildschirm:** Typ „Extern“, Name „Claudios“, deine E-Mail-Adresse eintragen. Füge dich unter
   „Testnutzer“ hinzu. Der Bereich `.../auth/webmasters.readonly` ist der einzige, den Claudios anfordert.
   Im Status „Testing“ laufen Anmeldungen nach meinem Stand nach 7 Tagen ab. Du meldest dich dann neu an.
4. **Anmeldedaten → Anmeldedaten erstellen → OAuth-Client-ID:** Anwendungstyp **„Desktop-App“** (nicht „Web“).
5. **JSON herunterladen.** In Claudios: Seite „Search Console“ → „client_secret.json importieren“.
6. **Lösche die heruntergeladene Datei danach** und lade sie niemals auf GitHub hoch (die `.gitignore` blockiert
   `client_secret*.json`). Claudios speichert den Client im Windows-Anmeldeinformationsspeicher.
7. „Mit Google anmelden“ klicken. Es öffnet sich dein Browser. Bei der Warnung „nicht verifizierte App“ weiter nur,
   wenn es dein eigenes Projekt ist. / On the "unverified app" warning continue only if it is your own project.
8. Danach siehst du deine Properties. Hast du für eine Inhaber- oder Vollzugriff, kannst du Stufe 2 einschalten.

Claudios sieht dein Google-Passwort nie. Es fragt nur Lesezugriff an: Property-Liste, Sitemaps, URL-Inspektion und
Seiten-Impressionen (keine Suchbegriffe).
