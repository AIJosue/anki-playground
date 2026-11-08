#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "Packaging anki_playground.ankiaddon..."
rm -f anki_playground.ankiaddon study_studio.ankiaddon
zip -r anki_playground.ankiaddon __init__.py manifest.json config.json anki_playground_web/

# Sync targets: env override, Flatpak Anki, native Linux Anki, macOS Anki
CANDIDATES=(
    "${ANKI_ADDONS_DIR:-}"
    "$HOME/.var/app/net.ankiweb.Anki/data/Anki2/addons21/anki_playground"
    "$HOME/.local/share/Anki2/addons21/anki_playground"
    "$HOME/Library/Application Support/Anki2/addons21/anki_playground"
)

SYNCED=0
for TARGET in "${CANDIDATES[@]}"; do
    if [ -n "$TARGET" ]; then
        PARENT="$(dirname "$TARGET")"
        if [ -d "$TARGET" ] || [ -d "$PARENT" ]; then
            LEGACY="$PARENT/study_studio"
            if [ -d "$LEGACY" ]; then
                echo "Removing legacy addon directory: $LEGACY"
                rm -rf "$LEGACY"
            fi
            mkdir -p "$TARGET"
            echo "Syncing directly to Anki addons directory: $TARGET"
            cp -r __init__.py manifest.json config.json anki_playground_web "$TARGET/"
            SYNCED=1
        fi
    fi
done

if [ "$SYNCED" -eq 1 ]; then
    echo "Synced."
fi

echo "Done."
