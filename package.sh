#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "Packaging study_studio.ankiaddon..."
rm -f study_studio.ankiaddon
zip -r study_studio.ankiaddon __init__.py manifest.json config.json study_studio_web/

ANKI_DIR="/home/admin/.var/app/net.ankiweb.Anki/data/Anki2/addons21/study_studio"
if [ -d "$ANKI_DIR" ]; then
    echo "Syncing directly to Anki addons directory..."
    cp -r __init__.py manifest.json config.json study_studio_web "$ANKI_DIR/"
    echo "Synced."
fi

echo "Done."
