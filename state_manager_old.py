import uasyncio as asyncio
import os
from machine import RTC

_lock = asyncio.Lock()
_max_messages = 5
_message_file = 'messages.txt'
_messages = []  # [{"type": "...", "text": "...", "state": "...", "timestamp": "..."}]
_display_callback = None

# --------------------------
# Display Callback
# --------------------------
def set_display_callback(callback):
    global _display_callback
    _display_callback = callback

# --------------------------
# Initialisierung
# --------------------------
def init_state():
    global _messages
    _messages = []

    if _message_file in os.listdir('/'):
        try:
            with open(_message_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-_max_messages:]:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split('|', 3)
                    if len(parts) == 4:
                        t, state, ts, txt = parts
                        _messages.append({
                            "type": t,
                            "state": state,
                            "timestamp": ts,
                            "text": txt
                        })
                    elif len(parts) == 2:
                        t, txt = parts
                        _messages.append({
                            "type": t,
                            "state": "wait",
                            "timestamp": _current_timestamp(),
                            "text": txt
                        })
                    else:
                        _messages.append({
                            "type": "pickup",
                            "state": "wait",
                            "timestamp": _current_timestamp(),
                            "text": line
                        })
        except Exception as e:
            print("❌ Fehler beim Laden der Nachrichten:", e)

# --------------------------
# Hilfsfunktion: Zeitstempel aus RTC
# --------------------------
def _current_timestamp():
    rtc = RTC()
    t = rtc.datetime()  # (year, month, day, weekday, hour, min, sec, ms)
    return f"{t[2]:02d}.{t[1]:02d}.{t[0]} {t[4]:02d}:{t[5]:02d}"

# --------------------------
# Nachricht speichern
# --------------------------
async def set_message(msg):
    global _messages, _display_callback
    async with _lock:
        if isinstance(msg, str):
            msg = {"type": "pickup", "text": msg}

        # Nur Timestamp setzen, wenn noch keiner existiert
        if "timestamp" not in msg or not msg["timestamp"]:
            msg["timestamp"] = _current_timestamp()

        msg.setdefault("type", "pickup")
        msg.setdefault("text", "")
        msg.setdefault("state", "wait")

        _messages.append(msg)
        _messages = _messages[-_max_messages:]
        await _save_to_file()

    if _display_callback:
        _display_callback()

# --------------------------
# Nachrichtenzustand ändern
# --------------------------
async def update_state(index, new_state):
    global _messages, _display_callback
    async with _lock:
        if 0 <= index < len(_messages):
            _messages[index]["state"] = new_state
            await _save_to_file()
    if _display_callback:
        _display_callback()

async def accept_last_message():
    global _messages, _display_callback
    async with _lock:
        if _messages:
            print("Status wird auf ACCEPT gesetzt")
            _messages[-1]["state"] = "accept"
            await _save_to_file()
    if _display_callback:
        _display_callback()

async def reject_last_message():
    global _messages, _display_callback
    async with _lock:
        if _messages:
            print("Status wird auf REJECT gesetzt")
            _messages[-1]["state"] = "reject"
            await _save_to_file()
    if _display_callback:
        _display_callback()

# --------------------------
# Nachricht löschen
# --------------------------
async def clear_message():
    global _messages, _display_callback
    async with _lock:
        if _messages:
            _messages.pop()
            await _save_to_file()
    if _display_callback:
        _display_callback()

# --------------------------
# Nachrichten abrufen
# --------------------------
async def get_message():
    """
    Gibt nur den Text der neuesten Nachricht zurück,
    und nur wenn deren state == 'wait'.
    Ältere Nachrichten werden ignoriert.
    """
    async with _lock:
        if _messages:
            last = _messages[-1]
            if last["state"] == "wait":
                return last["text"]
        return ""

async def get_all_messages():
    async with _lock:
        return list(_messages)

# --------------------------
# Datei speichern
# --------------------------
async def _save_to_file():
    try:
        with open(_message_file, 'w') as f:
            for m in _messages:
                f.write(f"{m['type']}|{m['state']}|{m['timestamp']}|{m['text']}\n")
    except Exception as e:
        print("❌ Fehler beim Schreiben der Nachrichten:", e)

# --------------------------
# Periodischer Task
# --------------------------
async def periodic_task():
    while True:
        await asyncio.sleep(10)
