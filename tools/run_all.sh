#!/usr/bin/env bash
# Sammelt alle Prüfergebnisse für CLAUDIOS in einer Ausgabe (auch in /tmp/claudios-ergebnis.txt).
# Aufruf: bash tools/run_all.sh          (nur prüfen)
#         bash tools/run_all.sh public   (zusätzlich das Repo öffentlich machen, falls keine Geheimnisse gefunden werden)
cd "$(dirname "$0")/.." || exit 1
OUT=/tmp/claudios-ergebnis.txt
exec > >(tee "$OUT") 2>&1
h() { printf '\n===== %s =====\n' "$1"; }

h "1 Stand"
git pull --rebase 2>&1 | tail -n 2
git log -1 --oneline
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)
echo "Repo: ${REPO:-unbekannt}"
python --version
echo "LICENSE: $(head -n 1 LICENSE)"
echo "QSizeGrip(widgets): $(grep -c QSizeGrip src/claudios/ui/widgets.py)  skip_btn(splash): $(grep -c skip_btn src/claudios/ui/splash.py)  noscore(report): $(grep -c noscore src/claudios/report/report.py)  conejito(strings): $(grep -c conejito-vipe src/claudios/i18n/strings.py)"
echo "Workflows: $(ls .github/workflows | tr '\n' ' ')"
echo "Manifeste: $(ls tools/manifests | tr '\n' ' ')"

h "2 Geheimnis-Suche (nur Dateinamen, keine Inhalte)"
STRONG='AIza[0-9A-Za-z_-]{30,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|[0-9]{8,}-[a-z0-9]{20,}\.apps\.googleusercontent\.com|GOCSPX-[A-Za-z0-9_-]{20,}'
NOW_LIST=$(git grep -IlE "$STRONG")
HIST_LIST=$(git rev-list --all | xargs -r git grep -IlE "$STRONG" 2>/dev/null | sed 's/^[0-9a-f]*://' | sort -u)
NOW=$(printf '%s' "$NOW_LIST" | grep -c .)
HIST=$(printf '%s' "$HIST_LIST" | grep -c .)
echo "Eindeutige Treffer im aktuellen Stand: $NOW  in der Historie: $HIST"
[ "$NOW" -gt 0 ] && echo "$NOW_LIST"
[ "$HIST" -gt 0 ] && echo "$HIST_LIST"
echo "Dateien mit 'client_secret' (zur Einordnung):"; git grep -Il -i 'client_secret' | head -n 15
echo "Dateien mit dem alten Namen:"; git grep -Iil 'fuh''fux' | head -n 20
echo "Autoren in der Historie (werden mit veröffentlicht):"; git log --all --format='%an <%ae>' | sort | uniq -c

h "3 Sichtbarkeit"
VIS=$(gh repo view --json visibility -q .visibility 2>/dev/null)
echo "Sichtbarkeit jetzt: ${VIS:-unbekannt}"
if [ "$1" = "public" ] && [ "$VIS" != "PUBLIC" ]; then
  if [ "$NOW" -eq 0 ] && [ "$HIST" -eq 0 ]; then
    if gh repo edit "$REPO" --visibility public --accept-visibility-change-consequences; then
      echo "Repo ist jetzt öffentlich."
      gh api -X PUT "repos/$REPO/private-vulnerability-reporting" >/dev/null 2>&1 && echo "Private Schwachstellenmeldung eingeschaltet." || echo "Private Schwachstellenmeldung: bitte unter Settings > Security von Hand einschalten."
    else
      echo "FEHLER: Sichtbarkeit nicht geändert. Vermutlich fehlt die Berechtigung des Codespace-Tokens:"
      echo "  unset GITHUB_TOKEN GH_TOKEN; gh auth login   (GitHub.com, HTTPS, Browser), dann Skript neu starten"
    fi
  else
    echo "NICHT öffentlich gemacht: Es gibt eindeutige Treffer (siehe oben)."
  fi
fi

h "4 Lokale Tests (kosten keine Actions-Minuten)"
sudo apt-get install -y -qq libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1 libglib2.0-0 >/dev/null 2>&1 || true
pip install -q -e ".[dev,gui]" 2>&1 | tail -n 3
export QT_QPA_PLATFORM=offscreen
echo "--- ruff"; ruff check src tests tools 2>&1 | tail -n 30
echo "--- check_files"; python tools/check_files.py 2>&1 | grep -v '^::' | tail -n 30
echo "--- pytest"; pytest -q -p no:cacheprovider 2>&1 | tail -n 60

h "5 Workflows auf GitHub"
run_wf() {  # startet einen Workflow und gibt die Lauf-ID aus
  local old new
  old=$(gh run list --workflow "$1" --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null)
  gh workflow run "$1" --ref main >/dev/null 2>&1 || { echo ""; return; }
  for _ in $(seq 1 12); do
    sleep 5
    new=$(gh run list --workflow "$1" --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null)
    [ -n "$new" ] && [ "$new" != "$old" ] && { echo "$new"; return; }
  done
  echo ""
}
wait_run() {
  for _ in $(seq 1 120); do
    [ "$(gh run view "$1" --json status -q .status 2>/dev/null)" = completed ] && return
    sleep 20
  done
  echo "Zeitlimit beim Warten auf Lauf $1"
}
report() {
  local c
  c=$(gh run view "$1" --json conclusion -q .conclusion 2>/dev/null)
  echo; echo "--- $2: $c  ($(gh run view "$1" --json url -q .url 2>/dev/null))"
  for j in $(gh api "repos/$REPO/actions/runs/$1/jobs" --jq '.jobs[].id' 2>/dev/null); do
    gh api "repos/$REPO/check-runs/$j/annotations" --paginate --jq '.[] | "[\(.annotation_level)] \(.title): \(.message)"' 2>/dev/null | cut -c1-420 | head -n 60
  done
  [ "$c" != success ] && gh run view "$1" --log-failed 2>&1 | tail -n 40
}
declare -A ID
for wf in lock-pruefung security autofix; do
  ID[$wf]=$(run_wf "$wf.yml")
  [ -z "${ID[$wf]}" ] && echo "FEHLER: $wf konnte nicht gestartet werden (Berechtigung oder keine Actions-Minuten)"
done
for wf in lock-pruefung security autofix; do
  [ -n "${ID[$wf]}" ] && { wait_run "${ID[$wf]}"; report "${ID[$wf]}" "$wf"; }
done
git pull --rebase 2>&1 | tail -n 1
for wf in ci build-windows; do
  ID[$wf]=$(run_wf "$wf.yml")
  [ -z "${ID[$wf]}" ] && echo "FEHLER: $wf konnte nicht gestartet werden"
done
for wf in ci build-windows; do
  [ -n "${ID[$wf]}" ] && { wait_run "${ID[$wf]}"; report "${ID[$wf]}" "$wf"; }
done

h "Fertig"
echo "Die ganze Ausgabe steht auch in $OUT"
