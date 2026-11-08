# Study Studio for Anki (`anki-playground`)

Gamified learning suite for Anki desktop. Integrates Flutter Web application inside native Qt `AnkiWebView` modal dialog via two-way bridge.

## Features

- **Direct Collection Access**: Reads decks, notes, cards, flags, tags, and media directly from `mw.col`.
- **Scheduler Integration**: Answers cards via native Anki scheduler (`mw.col.sched.answerCard`, V3/FSRS support).
- **Native Audio & Media**: Resolves collection images to base64 Data URIs; plays card audio tags (`[sound:...]`) via `aqt.sound.play`.
- **Card State Ops**: Star (`marked`), flag (0–7), bury, suspend.
- **Multiple Entry Points**:
  - Main menu: `Tools` → `Study Studio` (`Ctrl+Shift+S`)
  - Deck overview: Deck gear menu → `🎮 Play in Study Studio`
  - Reviewer: Bottom-right launcher button `🎮 Study Studio`

## File Structure

```
├── __init__.py           # Addon entrypoint, bridge dispatch, Anki hooks
├── manifest.json         # Anki addon manifest (package: study_studio)
├── config.json           # Addon user preferences
├── package.sh            # Bundler & sync script
├── study_studio_web/     # Pre-built Flutter Web assets & CanvasKit runtime
└── study_studio.ankiaddon# Packaged distribution zip
```

## Install & Development Workflow

### Option 1: Live Symlink (Recommended for Development)

Symlink repo directory directly to Anki addon directory. Code changes immediately take effect on Anki restart.

**Linux (Native):**
```bash
mkdir -p ~/.local/share/Anki2/addons21
ln -s "$(pwd)" ~/.local/share/Anki2/addons21/study_studio
```

**Linux (Flatpak):**
```bash
mkdir -p ~/.var/app/net.ankiweb.Anki/data/Anki2/addons21
ln -s "$(pwd)" ~/.var/app/net.ankiweb.Anki/data/Anki2/addons21/study_studio
```

**macOS:**
```bash
mkdir -p "$HOME/Library/Application Support/Anki2/addons21"
ln -s "$(pwd)" "$HOME/Library/Application Support/Anki2/addons21/study_studio"
```

**Windows (PowerShell Admin / Developer Mode):**
```powershell
New-Item -ItemType SymbolicLink -Path "$env:APPDATA\Anki2\addons21\study_studio" -Target (Get-Location)
```

### Option 2: Build & Auto-Sync (`package.sh`)

Packages `.ankiaddon` archive and auto-syncs changed files (`__init__.py`, `manifest.json`, `config.json`, `study_studio_web/`) to detected local Anki addon directory:

```bash
chmod +x package.sh
./package.sh
```

Override addon target path:
```bash
ANKI_ADDONS_DIR="/custom/path/to/addons21/study_studio" ./package.sh
```

### Option 3: Manual Install / Anki UI

1. Run `./package.sh` to generate `study_studio.ankiaddon`.
2. Inside Anki: `Tools` → `Add-ons` → `Install from file...` → select `study_studio.ankiaddon`.
3. Restart Anki.

## Configuration (`config.json`)

User configuration exposed through Anki Add-on Manager:

| Key | Type | Default | Description |
|---|---|---|---|
| `max_cards_per_deck` | `int` | `200` | Max cards fetched per deck query |
| `only_due_cards` | `bool` | `false` | Default to due/learning cards only |
| `auto_play_audio` | `bool` | `true` | Auto-play audio when card exposed |
| `default_activity` | `string` | `"flashcards"` | Initial game view loaded |

## Two-Way Bridge Protocol

Flutter Web communicates with Python host via `pycmd(msg)`:

| Direction | Command / Message | Payload | Effect |
|---|---|---|---|
| Web → Python | `studystudio:ready` / `studystudio:get_decks` | - | Request deck data |
| Web → Python | `studystudio:filter_due:<bool>` | `true`/`false` | Reload decks filtered by due status |
| Web → Python | `studystudio:play_sound:<name>` | audio filename | Play sound via `aqt.sound.play` |
| Web → Python | `studystudio:answer_card:<json>` | `{"cid": int, "ease": 1..4}` | Schedule card review in Anki |
| Web → Python | `studystudio:toggle_star:<cid>` | card id | Toggle `marked` tag on note |
| Web → Python | `studystudio:set_flag:<json>` | `{"cid": int, "flag": 0..7}` | Set card color flag |
| Web → Python | `studystudio:suspend_card:<cid>` | card id | Suspend card |
| Web → Python | `studystudio:bury_card:<cid>` | card id | Bury card until tomorrow |
| Web → Python | `studystudio:save_config:<json>` | config dict | Write updated config to disk |
| Python → Web | `window.receiveNativeAnkiDecks(json)` | `{decks, config}` | Dispatch deck & config payload to Flutter |
