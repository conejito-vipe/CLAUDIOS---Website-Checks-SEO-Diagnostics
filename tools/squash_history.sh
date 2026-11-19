#!/usr/bin/env bash
# Fasst die ganze Git-Historie zu EINEM Commit zusammen (nur Zweig main) und löscht Zweige, Tags und alte Workflow-Läufe.
# Aufruf im Codespace: bash tools/squash_history.sh
# Sicherung der alten Historie: claudios-alte-historie.bundle (im Repo-Ordner, von git ignoriert).
set -euo pipefail
cd "$(dirname "$0")/.."
say() { printf '\n== %s ==\n' "$1"; }
trap 'echo; echo "ABBRUCH. Falls der Push noch nicht lief, ist GitHub unverändert. Lokal zurück: git checkout -f -B main origin/main"' ERR

say "1 Voraussetzungen"
command -v gh >/dev/null || { echo "gh (GitHub CLI) fehlt"; exit 1; }
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
LOGIN=$(gh api user --jq .login)
USER_ID=$(gh api user --jq .id)
NAME="$LOGIN"
MAIL="${USER_ID}+${LOGIN}@users.noreply.github.com"
echo "Repo: $REPO | Autor der Historie wird: $NAME <$MAIL>"
[ "$LOGIN" = "conejito-vipe" ] || echo "WARNUNG: angemeldet ist '$LOGIN', nicht conejito-vipe"
[ "$(git branch --show-current)" = main ] || { echo "Bitte auf dem Zweig main arbeiten"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "Es gibt lokale Änderungen. Erst committen oder verwerfen (git status)."; exit 1; }
git remote set-url origin "https://github.com/$REPO"
git pull --rebase
PROT=$(gh api "repos/$REPO/branches/main" --jq .protected 2>/dev/null || echo unbekannt)
echo "main geschützt: $PROT"
[ "$PROT" != true ] || { echo "main ist geschützt: Schutzregel unter Settings > Branches vorübergehend löschen"; exit 1; }

say "2 Dateien prüfen"
if git ls-files | grep -E 'pycache|\.pyc$|\.env$|client_secret'; then
  echo "Diese Dateien gehören nicht ins Repo (Liste oben). Bitte entfernen: git rm <Datei>, committen, Skript neu starten."
  exit 1
fi
STRONG='AIza[0-9A-Za-z_-]{30,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|[0-9]{8,}-[a-z0-9]{20,}\.apps\.googleusercontent\.com|GOCSPX-[A-Za-z0-9_-]{20,}'
HITS=$(git grep -IlE "$STRONG" || true)
if [ -n "$HITS" ]; then
  echo "Mögliche Geheimnisse in diesen Dateien (Namen, keine Inhalte):"; echo "$HITS"
  read -r -p "Sind das nur Testbeispiele ohne echte Schlüssel? Tippe ja zum Fortfahren: " ANS
  [ "$ANS" = ja ] || { echo "Abbruch. Erst prüfen."; exit 1; }
fi
echo "Dateien, die noch den alten Namen enthalten (von Hand ändern, falls es echte Dateien sind):"
git grep -Iil 'fuh''fux' || echo "keine"

say "3 Bisherige Autoren"
git log --all --format='%an <%ae>' | sort | uniq -c
echo "Commits jetzt: $(git rev-list --all --count)"
read -r -p "Historie JETZT endgültig durch einen einzigen Commit ersetzen? Tippe ja: " GO
[ "$GO" = ja ] || { echo "Abgebrochen, nichts geändert."; exit 0; }

say "4 Sicherung und Zusammenführen"
echo "claudios-alte-historie.bundle" >> .git/info/exclude
git bundle create claudios-alte-historie.bundle --all
git checkout --orphan neu-main
git add -A
git -c user.name="$NAME" -c user.email="$MAIL" commit -q -m "CLAUDIOS 0.1.0 - clean start"
git branch -M main
git push --force origin main

say "5 Zweige, Tags und alte Läufe löschen"
for b in $(git ls-remote --heads origin | awk '{print $2}' | sed 's#refs/heads/##' | grep -v '^main$' || true); do
  git push origin --delete "$b" || true
done
for t in $(git tag -l); do git push origin --delete "$t" || true; git tag -d "$t" >/dev/null; done
gh run list --limit 1000 --json databaseId -q '.[].databaseId' | xargs -r -n1 gh run delete || true
git reflog expire --expire=now --all
git gc --prune=now -q

say "6 Ergebnis"
git log --all --format='%h %an <%ae> %s'
echo "Commits insgesamt: $(git rev-list --all --count)"
echo "Sichtbarkeit: $(gh repo view --json visibility -q .visibility)"
echo
echo "Fertig. Die Sicherung der alten Historie liegt als claudios-alte-historie.bundle im Datei-Explorer links."
echo "Lade sie herunter (Rechtsklick > Download) und bewahre sie PRIVAT auf. Weiter mit: bash tools/run_all.sh public"
