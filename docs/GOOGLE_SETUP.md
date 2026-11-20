# Setting up Google access

Deutsche Fassung: [GOOGLE_SETUP.de.md](GOOGLE_SETUP.de.md)

CLAUDIOS needs your own OAuth client. It belongs to you, not to the program. The names of the menus below are from memory and may differ.

1. Open https://console.cloud.google.com and create a **new project**.
2. **APIs & Services → Library:** enable "Google Search Console API".
3. **OAuth consent screen:** type "External", name "CLAUDIOS", enter your e-mail address. Add yourself under "Test users". The scope `.../auth/webmasters.readonly` is the only one CLAUDIOS requests. In the status "Testing", sign-ins expire after 7 days as far as I know; you then sign in again.
4. **Credentials → Create credentials → OAuth client ID:** application type **"Desktop app"** (not "Web").
5. **Download the JSON.** In CLAUDIOS: page "Search Console" → "Import client_secret.json".
6. **Delete the downloaded file afterwards** and never upload it to GitHub (the `.gitignore` blocks `client_secret*.json`). CLAUDIOS stores the client in the Windows Credential Manager.
7. Click "Sign in with Google". Your browser opens. On the "unverified app" warning continue only if it is your own project.
8. Afterwards you see your properties. If you have owner or full access to one, you can switch on level 2.

CLAUDIOS never sees your Google password. It only requests read access: property list, sitemaps, URL inspection and page impressions (no search terms).

## Optional: API key for Safe Browsing

Only needed if you switch on Safe Browsing on the page "External services". Create an API key in the same Google Cloud project and enable the "Safe Browsing API" (menu names from memory). Paste the key on the page "External services". It is kept in the Windows Credential Manager, never in a file or in a report.
