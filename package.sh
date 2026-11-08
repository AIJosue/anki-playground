#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "Packaging study_studio.ankiaddon..."
rm -f study_studio.ankiaddon
zip -r study_studio.ankiaddon __init__.py manifest.json config.json study_studio_web/

# Sync targets: env override, Flatpak Anki, native Linux Anki, macOS Anki
CANDIDATES=(
    "${ANKI_ADDONS_DIR:-}"
    "$HOME/.var/app/net.ankiweb.Anki/data/Anki2/addons21/study_studio"
    "$HOME/.local/share/Anki2/addons21/study_studio"
    "$HOME/Library/Application Support/Anki2/addons21/study_studio"
)

SYNCED=0
for TARGET in "${CANDIDATES[@]}"; do
    if [ -n "$TARGET" ] && [ -d "$TARGET" ]; then
        echo "Syncing directly to Anki addons directory: $TARGET"
        cp -r __init__.py manifest.json config.json study_studio_web "$TARGET/"
        SYNCED=1
    fi
done

if [ "$SYNCED" -eq 1 ]; then
    echo "Synced."
fi

echo "Done."
