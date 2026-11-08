"""
Anki Playground - Pure Native Anki Add-on Integration Module
Comprehensive 2-way native integration with Anki's database, scheduler (V3/FSRS),
audio playback (aqt.sound), Deck Browser gear actions, Reviewer bottom bar shortcut,
and addon config.json options.
"""

import base64
import html
import json
import mimetypes
import os
import re
from aqt import mw, gui_hooks
from aqt.qt import QDialog, QVBoxLayout, QAction, QMenu
from aqt.utils import showInfo, tooltip
from aqt.webview import AnkiWebView
from aqt.sound import play


def clean_html(raw_html: str) -> str:
    """Strip HTML tags, sounds, and convert entities for clean study terms."""
    if not raw_html:
        return ""
    # Strip sound tags from displayed text
    text = re.sub(r"\[sound:[^\]]+\]", "", raw_html)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()


def extract_and_resolve_images(raw_html: str, media_dir: str) -> list[str]:
    """Extract and resolve images into base64 Data URIs."""
    if not raw_html:
        return []

    image_srcs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_html, re.IGNORECASE)
    resolved_uris = []

    for src in image_srcs:
        if src.startswith("data:") or src.startswith("http://") or src.startswith("https://"):
            resolved_uris.append(src)
            continue

        filename = os.path.basename(src)
        if media_dir:
            file_path = os.path.join(media_dir, filename)
            if os.path.isfile(file_path):
                try:
                    mime_type, _ = mimetypes.guess_type(file_path)
                    if not mime_type:
                        mime_type = "image/png"
                    with open(file_path, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode("utf-8")
                        resolved_uris.append(f"data:{mime_type};base64,{encoded}")
                        continue
                except Exception as e:
                    print(f"[Anki Playground] Image load error: {e}")

        resolved_uris.append(src)

    return resolved_uris


def extract_sound_filenames(raw_html: str) -> list[str]:
    """Extract native Anki [sound:file.mp3] references."""
    if not raw_html:
        return []
    return re.findall(r"\[sound:([^\]]+)\]", raw_html)


def get_addon_config() -> dict:
    """Retrieve config.json settings managed by Anki's AddonManager."""
    default_config = {
        "max_cards_per_deck": 200,
        "only_due_cards": false if False else False,
        "auto_play_audio": True,
        "default_activity": "flashcards",
    }
    if not mw or not mw.addonManager:
        return default_config
    try:
        conf = mw.addonManager.getConfig(__name__)
        if conf and isinstance(conf, dict):
            default_config.update(conf)
    except Exception:
        pass
    return default_config


def get_native_anki_decks(target_deck_id: int = None, only_due: bool = False) -> dict:
    """
    Fetch native Anki decks with rich card metadata, media images, audio,
    and due status directly from collection.
    """
    if not mw or not mw.col:
        return {}

    decks_result = {}
    config = get_addon_config()
    max_cards = config.get("max_cards_per_deck", 200)

    try:
        media_dir = mw.col.media.dir() if hasattr(mw.col, "media") else ""
        all_deck_items = mw.col.decks.all_names_and_ids()

        for deck_entry in all_deck_items:
            deck_name = deck_entry.name
            deck_id = deck_entry.id

            if target_deck_id is not None and deck_id != target_deck_id:
                continue

            cards_list = []

            escaped_deck = deck_name.replace('"', '\\"')

            # Filter by due cards or all cards
            if only_due:
                # Query cards due for review, learning, or new cards in deck
                cids = mw.col.find_cards(f'deck:"{escaped_deck}" (is:due or is:new or is:learn)')[:max_cards]
                if not cids:
                    # If none due, fall back to general queued cards
                    cids = mw.col.find_cards(f'deck:"{escaped_deck}"')[:max_cards]
            else:
                cids = mw.col.find_cards(f'deck:"{escaped_deck}"')[:max_cards]

            for cid in cids:
                try:
                    card = mw.col.get_card(cid)
                    note = card.note()
                    fields = list(note.values())
                    if len(fields) >= 2:
                        raw_front = fields[0]
                        raw_back = fields[1]
                        term = clean_html(raw_front)
                        definition = clean_html(raw_back)

                        # Extract images & sound files
                        combined_html = raw_front + " " + raw_back
                        images = extract_and_resolve_images(combined_html, media_dir)
                        sounds = extract_sound_filenames(combined_html)

                        if (term or images) and (definition or images):
                            cards_list.append({
                                "id": str(cid),
                                "nid": str(note.id),
                                "did": str(deck_id),
                                "term": term if term else "[Image Card]",
                                "definition": definition if definition else "[See Image]",
                                "images": images,
                                "sounds": sounds,
                                "queue": card.queue,
                                "reps": card.reps,
                                "lapses": card.lapses,
                                "factor": card.factor,
                                "due": card.due,
                                "flag": card.user_flag(),
                                "tags": list(note.tags),
                                "is_marked": note.has_tag("marked"),
                            })
                except Exception:
                    continue

            if cards_list:
                decks_result[deck_name] = {
                    "id": str(deck_id),
                    "name": deck_name,
                    "cards": cards_list,
                }
    except Exception as e:
        print(f"[Anki Playground] Error querying Anki collection: {e}")

    if not decks_result and target_deck_id is not None:
        return get_native_anki_decks(None, only_due)
    return decks_result


class AnkiPlaygroundDialog(QDialog):
    """Native Anki WebView dialog running Anki Playground."""

    def __init__(self, parent=None, initial_deck_id: int = None):
        super().__init__(parent)
        self.initial_deck_id = initial_deck_id
        self.setWindowTitle("Anki Playground • Gamified Learning Suite for Anki")
        self.resize(1180, 820)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = AnkiWebView(self)
        # Prevent Anki from delegating internal dialog navigation to system browser (Chrome)
        self.web_view.set_open_links_externally(False)
        self.web_view.set_bridge_command(self._on_bridge_cmd, self.web_view)
        layout.addWidget(self.web_view)

        gui_hooks.webview_did_receive_js_message.append(self.on_js_message)

        addon_dir = os.path.dirname(__file__)
        addon_pkg = os.path.basename(addon_dir)
        web_dir = os.path.join(addon_dir, "anki_playground_web")
        index_file = os.path.join(web_dir, "index.html")

        if os.path.exists(index_file):
            from aqt.qt import QUrl
            if mw and hasattr(mw, "serverURL"):
                # Serve via Anki's internal media server using registered web exports
                server_url = f"{mw.serverURL()}_addons/{addon_pkg}/anki_playground_web/index.html"
                self.web_view.load_url(QUrl(server_url))
            else:
                url = QUrl.fromLocalFile(index_file)
                self.web_view.load_url(url)
        else:
            self.web_view.stdHtml("<h3>Anki Playground build files not found.</h3>")

    def _on_bridge_cmd(self, cmd: str) -> any:
        handled, res = self.on_js_message((False, None), cmd, self.web_view)
        return res

    def on_js_message(self, handled: tuple[bool, any], message: str, context: any) -> tuple[bool, any]:
        """Direct bridge connecting Flutter activities to native Anki commands."""
        if context is not None and context != self.web_view:
            return handled

        try:
            # 1. Provide all decks (with native cards, images, audio)
            if message == "studystudio:get_decks" or message == "studystudio:ready":
                decks = get_native_anki_decks(target_deck_id=self.initial_deck_id)
                config = get_addon_config()
                payload = {
                    "decks": decks,
                    "config": config,
                }
                js = f"window.receiveNativeAnkiDecks({json.dumps(json.dumps(payload))});"
                self.web_view.eval(js)
                return (True, None)

            # 2. Filter by Due Cards
            if message.startswith("studystudio:filter_due:"):
                flag_str = message[len("studystudio:filter_due:"):].lower()
                only_due = flag_str == "true"
                decks = get_native_anki_decks(target_deck_id=self.initial_deck_id, only_due=only_due)
                config = get_addon_config()
                payload = {"decks": decks, "config": config}
                js = f"window.receiveNativeAnkiDecks({json.dumps(json.dumps(payload))});"
                self.web_view.eval(js)
                tooltip(f"Loaded {'Due Cards' if only_due else 'All Deck Cards'}", parent=self)
                return (True, None)

            # 3. Native Audio Playback
            if message.startswith("studystudio:play_sound:"):
                sound_name = message[len("studystudio:play_sound:"):].strip()
                if mw and mw.col and mw.col.media:
                    media_dir = mw.col.media.dir()
                    audio_path = os.path.join(media_dir, sound_name)
                    if os.path.isfile(audio_path):
                        play(audio_path)
                return (True, None)

            # 4. Answer Card (Ease: 1=Again, 2=Hard, 3=Good, 4=Easy)
            if message.startswith("studystudio:answer_card:"):
                payload_str = message[len("studystudio:answer_card:"):]
                data = json.loads(payload_str)
                cid = int(data["cid"])
                ease = int(data.get("ease", 3))

                if mw and mw.col:
                    card = mw.col.get_card(cid)
                    rating_name = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}.get(ease, str(ease))
                    ivl = ""
                    try:
                        ivl = mw.col.sched.nextIvlStr(card, ease)
                    except Exception:
                        pass
                    card.start_timer()
                    mw.col.sched.answerCard(card, ease)
                    msg = f"Anki: {rating_name} ({ivl})" if ivl else f"Anki: {rating_name}"
                    tooltip(msg, parent=self)
                return (True, None)

            # 5. Toggle Star / Marked Tag
            if message.startswith("studystudio:toggle_star:"):
                cid = int(message[len("studystudio:toggle_star:"):])
                if mw and mw.col:
                    card = mw.col.get_card(cid)
                    note = mw.col.get_note(card.nid)
                    if note.has_tag("marked"):
                        note.remove_tag("marked")
                        status = "Unstarred (tag 'marked' removed)"
                    else:
                        note.add_tag("marked")
                        status = "Starred (tag 'marked' added)"
                    mw.col.update_note(note)
                    tooltip(status, parent=self)
                return (True, None)

            # 6. Set Flag (0-7)
            if message.startswith("studystudio:set_flag:"):
                payload = json.loads(message[len("studystudio:set_flag:"):])
                cid = int(payload["cid"])
                flag = int(payload["flag"])
                if mw and mw.col:
                    mw.col.set_user_flag_for_cards(flag=flag, cids=[cid])
                    tooltip(f"Card flag set to {flag}", parent=self)
                return (True, None)

            # 7. Suspend or Bury Card
            if message.startswith("studystudio:suspend_card:"):
                cid = int(message[len("studystudio:suspend_card:"):])
                if mw and mw.col:
                    mw.col.sched.suspend_cards([cid])
                    tooltip("Card suspended in Anki", parent=self)
                return (True, None)

            if message.startswith("studystudio:bury_card:"):
                cid = int(message[len("studystudio:bury_card:"):])
                if mw and mw.col:
                    mw.col.sched.bury_cards([cid])
                    tooltip("Card buried until tomorrow", parent=self)
                return (True, None)

            # 8. Save updated config from UI
            if message.startswith("studystudio:save_config:"):
                new_conf = json.loads(message[len("studystudio:save_config:"):])
                if mw and mw.addonManager:
                    mw.addonManager.writeConfig(__name__, new_conf)
                    tooltip("Anki Playground preferences saved", parent=self)
                return (True, None)

            # 9. Toast message
            if message.startswith("studystudio:toast:"):
                text = message[len("studystudio:toast:"):]
                tooltip(text, parent=self)
                return (True, None)

        except Exception as e:
            print(f"[Anki Playground] Error handling message {message}: {e}")

        return handled

    def reject(self):
        """Unregister hooks and notify Anki to refresh UI when dialog closes."""
        try:
            gui_hooks.webview_did_receive_js_message.remove(self.on_js_message)
        except Exception:
            pass

        if mw:
            try:
                mw.reset()
            except Exception:
                pass
        super().reject()


_anki_playground_dialog = None


def open_anki_playground(deck_id: int = None):
    """Open Anki Playground modal, optionally focused on a specific deck."""
    global _anki_playground_dialog
    if not mw or not mw.col:
        showInfo("Please open an Anki profile and collection first.")
        return

    _anki_playground_dialog = AnkiPlaygroundDialog(mw, initial_deck_id=deck_id)
    _anki_playground_dialog.show()


# Integration 1: Deck Browser Gear Menu Action
def on_deck_browser_will_show_options_menu(menu: QMenu, deck_id: int):
    action = menu.addAction("🎮 Play in Anki Playground")
    action.triggered.connect(lambda: open_anki_playground(deck_id=deck_id))


# Integration 2: Reviewer Bottom Bar Action Button
def on_reviewer_webview_will_set_content(web_content: any, context: object):
    if "reviewer" in str(context).lower():
        # Add a quick launcher button to reviewer bottom bar
        web_content.body += """
        <div style="position: fixed; right: 14px; bottom: 12px; z-index: 9999;">
            <button onclick="pycmd('studystudio:launch_from_reviewer');" 
                    style="background: #007aff; color: white; border: none; padding: 6px 12px; 
                           border-radius: 12px; font-weight: bold; cursor: pointer; font-size: 12px;
                           box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
                🎮 Anki Playground
            </button>
        </div>
        """


def on_reviewer_js_message(handled: tuple[bool, any], message: str, context: any) -> tuple[bool, any]:
    if message == "studystudio:launch_from_reviewer":
        if mw and mw.col:
            selected_deck_id = mw.col.decks.selected()
            open_anki_playground(deck_id=selected_deck_id)
            return (True, None)
    return handled


def init_addon():
    """Register menu shortcuts, hooks, and web exports."""
    try:
        mw.addonManager.setWebExports(__name__, r"anki_playground_web/.*")
    except Exception:
        pass

    # Tools Menu & Shortcut
    action = QAction("Anki Playground", mw)
    action.setShortcut("Ctrl+Shift+S")
    action.triggered.connect(lambda: open_anki_playground())
    mw.form.menuTools.addAction(action)

    # Hook: Deck Browser Gear Menu
    gui_hooks.deck_browser_will_show_options_menu.append(on_deck_browser_will_show_options_menu)

    # Hook: Reviewer Game Switcher
    gui_hooks.webview_will_set_content.append(on_reviewer_webview_will_set_content)
    gui_hooks.webview_did_receive_js_message.append(on_reviewer_js_message)


if mw:
    init_addon()
