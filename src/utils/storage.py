import json
import os

CHAT_HISTORY_FILE = "data/chat_history.json"

def load_chat_history():
    """Loads chat history from a local JSON file."""
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_chat_history(messages):
    """Saves chat history to a local JSON file."""
    os.makedirs("data", exist_ok=True)
    with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)