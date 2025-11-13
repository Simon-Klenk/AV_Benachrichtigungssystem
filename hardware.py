# hardware.py

import machine
import uasyncio as asyncio
import utime

# interne globale Variablen (nur hier sichtbar)
_LED_ALERT_PIN = 2
_BUTTON_ACCEPT_PIN = 15
_BUTTON_REJECT_PIN = 14

_latest_event = None
_event_ready = False

def _button_irq_handler(pin):
    global _latest_event, _event_ready
    ts = utime.ticks_ms()
    _latest_event = (pin.id(), pin.value(), ts)
    _event_ready = True

class Hardware:
    def __init__(self, event_queue):
        self._event_queue = event_queue
        self._led_alert = machine.Pin(_LED_ALERT_PIN, machine.Pin.OUT)
        self._button_accept = machine.Pin(_BUTTON_ACCEPT_PIN, machine.Pin.IN, machine.Pin.PULL_DOWN)
        self._button_reject = machine.Pin(_BUTTON_REJECT_PIN, machine.Pin.IN, machine.Pin.PULL_DOWN)
        self._button_accept.irq(trigger=machine.Pin.IRQ_FALLING | machine.Pin.IRQ_RISING, handler=_button_irq_handler)
        self._button_reject.irq(trigger=machine.Pin.IRQ_FALLING | machine.Pin.IRQ_RISING, handler=_button_irq_handler)

    async def _button_task(self):
        global _latest_event, _event_ready
        last_event_time = {}
        DEBOUNCE_MS = 200
        while True:
            if _event_ready:
                _event_ready = False
                pin_id, val, ts = _latest_event
                if pin_id not in last_event_time or (ts - last_event_time[pin_id]) > DEBOUNCE_MS:
                    last_event_time[pin_id] = ts
                    if pin_id == _BUTTON_ACCEPT_PIN:
                        value = "ACCEPT"
                    elif pin_id == _BUTTON_REJECT_PIN:
                        value = "REJECT"
                    else:
                        value = "UNKNOWN"

                    # Event in die Queue
                    await self._event_queue.put({
                        "type": "BUTTON_PRESSED" if val == 0 else "BUTTON_RELEASED",
                        "value": value,
                        "timestamp": ts
                    })
            await asyncio.sleep_ms(100)

    async def run(self):
        asyncio.create_task(self._button_task())
        while True:
            await asyncio.sleep(1)
