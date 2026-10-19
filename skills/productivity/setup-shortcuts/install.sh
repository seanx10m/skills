#!/usr/bin/env bash
# install.sh - install (or --uninstall) the Claude Code shell shortcuts.
#
#   ./install.sh              copy shortcuts.zsh to ~/.config/claude-shortcuts/ and
#                             add one delimited `source` block to ~/.zshrc (idempotent)
#   ./install.sh --uninstall  remove that block and the installed file
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${HOME:?}/.config/claude-shortcuts"
DEST="$DEST_DIR/shortcuts.zsh"
ZSHRC="${ZDOTDIR:-$HOME}/.zshrc"
BEGIN="# >>> claude-shortcuts >>>"
END="# <<< claude-shortcuts <<<"

strip_block() {
  # Print $ZSHRC without the delimited block (and the blank line install put before it).
  awk -v b="$BEGIN" -v e="$END" '
    $0 == b { skip = 1; held = 0; next }
    $0 == e { skip = 0; next }
    skip { next }
    held { print ""; held = 0 }
    $0 == "" { held = 1; next }
    { print }
    END { if (held) print "" }
  ' "$ZSHRC"
}

case "${1:-}" in
  --uninstall)
    if [[ -f "$ZSHRC" ]] && grep -qxF "$BEGIN" "$ZSHRC"; then
      tmp="$(mktemp "${ZSHRC}.XXXXXX")"
      strip_block > "$tmp"
      cat "$tmp" > "$ZSHRC"   # keep the original file's inode and permissions
      rm -f "$tmp"
      echo "Removed claude-shortcuts block from $ZSHRC"
    else
      echo "No claude-shortcuts block in $ZSHRC"
    fi
    rm -f "$DEST"
    rmdir "$DEST_DIR" 2>/dev/null || true
    echo "Uninstalled. Open a new shell (functions stay defined in shells that already sourced it)."
    ;;
  "")
    mkdir -p "$DEST_DIR"
    cp "$SRC_DIR/shortcuts.zsh" "$DEST"
    echo "Installed $DEST"
    touch "$ZSHRC"
    if grep -qxF "$BEGIN" "$ZSHRC"; then
      echo "$ZSHRC already sources it - left unchanged"
    else
      {
        printf '\n%s\n' "$BEGIN"
        printf '[[ -r "$HOME/.config/claude-shortcuts/shortcuts.zsh" ]] && source "$HOME/.config/claude-shortcuts/shortcuts.zsh"\n'
        printf '%s\n' "$END"
      } >> "$ZSHRC"
      echo "Added source line to $ZSHRC"
    fi
    echo "Run: source \"$ZSHRC\"  (or open a new terminal)"
    ;;
  -h|--help)
    sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'
    ;;
  *)
    echo "usage: $0 [--uninstall]" >&2
    exit 2
    ;;
esac
