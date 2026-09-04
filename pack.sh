#!/usr/bin/env bash
# pack.sh — tar up the skill so it can move to another Mac.
#
#   bash ~/.claude/skills/skr/pack.sh [DEST_DIR]
#
# On the other machine:
#   tar xzf skr-skill-*.tar.gz -C ~/.claude/skills/
#   bash ~/.claude/skills/skr/install.sh
#
# Only the skill travels. Your workspaces under ~/Documents/SKR stay put —
# they hold your teacher's sheets, which are not mine to copy around.
set -euo pipefail
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${1:-$HOME/Downloads}"
STAMP="$(date +%Y%m%d)"
OUT="$DEST/skr-skill-$STAMP.tar.gz"
mkdir -p "$DEST"
tar czf "$OUT" -C "$(dirname "$SKILL")" "$(basename "$SKILL")"
printf 'packed → %s (%s)\n' "$OUT" "$(du -h "$OUT" | cut -f1)"
