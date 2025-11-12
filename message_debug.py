import os
import time

class MessageDebug:
    def __init__(self, message_file='messages.txt', max_messages=5):
        self.message_file = message_file
        self.max_messages = max_messages
        self.messages = []

    def _current_timestamp(self):
        t = time.localtime()
        return f"{t[2]:02d}.{t[1]:02d}.{t[0]} {t[3]:02d}:{t[4]:02d}"

    def load_messages(self):
        self.messages = []
        if self.message_file in os.listdir('/'):
            try:
                with open(self.message_file, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-self.max_messages:]:
                        line = line.strip()
                        if not line:
                            continue

                        parts = line.split('|', 3)
                        if len(parts) == 4:
                            t, state, ts, txt = parts
                            self.messages.append({
                                "type": t,
                                "state": state,
                                "timestamp": ts,
                                "text": txt
                            })
                        elif len(parts) == 2:
                            t, txt = parts
                            self.messages.append({
                                "type": t,
                                "state": "wait",
                                "timestamp": self._current_timestamp(),
                                "text": txt
                            })
                        else:
                            self.messages.append({
                                "type": "pickup",
                                "state": "wait",
                                "timestamp": self._current_timestamp(),
                                "text": line
                            })
            except Exception as e:
                print("❌ Fehler beim Laden der Nachrichten:", e)
        else:
            print("ℹ️ Nachrichtendatei nicht gefunden.")

    def print_messages(self):
        if not self.messages:
            print("ℹ️ Keine Nachrichten gefunden.")
            return

        print("---- Aktuelle Nachrichten ----")
        for idx, m in enumerate(self.messages):
            print(f"[{idx}] Typ: {m['type']}, State: {m['state']}, Zeit: {m['timestamp']}")
            print(f"     Text: {m['text']}")
        print("-----------------------------")


# --------------------------
# Standalone ausführen
# --------------------------
if __name__ == "__main__":
    debugger = MessageDebug()
    debugger.load_messages()
    debugger.print_messages()
