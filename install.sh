#!/usr/bin/env bash
# install.sh — put a new Mac (or a broken one) back into a working state.
#
#   bash ~/.claude/skills/skr/install.sh            # install / repair
#   bash ~/.claude/skills/skr/install.sh --check    # report only, change nothing
#
# What it guarantees:
#   * python3 with pymupdf (read teacher PDFs) and sympy (verify every number)
#   * ~/Documents/SKR/<Subject>/ exists for each subject in play, with the
#     lessons/fig/ folder every figure must live in (Safari will not load one
#     that sits outside lessons/)
#   * every workspace holds the CURRENT shared assets/lesson.css, assets/quiz.js,
#     assets/graph.js and the ธีม สสวท LaTeX files
#     and build.py — one library, fixed once, copied everywhere
set -uo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$HOME/Documents/SKR"
SUBJECTS=(Chemistry Biology Physics Math)
CHECK=0
[[ "${1:-}" == "--check" ]] && CHECK=1

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; }
note() { printf '  · %s\n' "$1"; }

echo "skr install — ${SKILL}"
echo
echo "python"
if ! command -v python3 >/dev/null; then
  bad "python3 not found — install it first"; exit 1
fi
ok "python3 $(python3 -c 'import sys;print(".".join(map(str,sys.version_info[:3])))')"

for pkg in pymupdf sympy; do
  if python3 -c "import $pkg" 2>/dev/null; then
    ok "$pkg"
  elif (( CHECK )); then
    bad "$pkg missing"
  else
    note "installing $pkg…"
    if pip3 install --quiet "$pkg"; then ok "$pkg installed"; else bad "$pkg failed to install"; fi
  fi
done

echo
echo "workspaces"
for s in "${SUBJECTS[@]}"; do
  ws="$BASE/$s"
  # Physics and Math have no content yet; create them only on a real install,
  # and never fail the check because they are absent.
  if [[ ! -d "$ws" ]]; then
    if (( CHECK )); then note "$s — not created yet"; continue; fi
    mkdir -p "$ws"/{lessons/fig,reference,assets,learning-records,Slides}
    ok "$s created"
  fi

  for f in assets/lesson.css assets/quiz.js assets/graph.js \
           assets/ipst-theme.tex assets/ipst-worksheet.tex; do
    src="$SKILL/$f"; dst="$ws/$f"
    mkdir -p "$(dirname "$dst")"
    if [[ -f "$dst" ]] && cmp -s "$src" "$dst"; then
      ok "$s/$f up to date"
    elif (( CHECK )); then
      bad "$s/$f differs from the shared library"
    else
      cp "$src" "$dst"; ok "$s/$f synced"
    fi
  done

  if [[ -f "$ws/build.py" ]] && cmp -s "$SKILL/assets/build.py" "$ws/build.py"; then
    ok "$s/build.py up to date"
  elif (( CHECK )); then
    bad "$s/build.py missing or stale"
  else
    cp "$SKILL/assets/build.py" "$ws/build.py"; ok "$s/build.py synced"
  fi
done

echo
if (( CHECK )); then
  echo "check only — nothing was written"
else
  echo "done. Re-run build.py inside any workspace whose assets changed:"
  for s in "${SUBJECTS[@]}"; do
    [[ -d "$BASE/$s/lessons" ]] && echo "    (cd \"$BASE/$s\" && python3 build.py)"
  done
fi
