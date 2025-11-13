# state_manager.py
import uasyncio as asyncio

_max_messages = 5
_message_file = 'messages.txt'
_messages = []  # [{"type": "...", "text": "...", "state": "...", "timestamp": "..."}]

class StateManager:

    def __init__(self, event_queue):
        self.event_queue = event_queue
        self._current_state = "INITIAL" 

    def update_state(self, index, new_state):
        if 0 <= index < len(_messages):
            _messages[index]["state"] = new_state


    async def run(self):
        while True:
            event = await self.event_queue.get()
            print(f"[StateManager] Empfing Ereignis: '{event}'")
            event_type = event.get("type", "UNKNOWN_TYPE")
            event_value = event.get("value", "UNKNOW_TYPE")

            if event_type == "BUTTON_PRESSED":
                if event_value == "ACCEPT":

                if event_value == "REJECT":


