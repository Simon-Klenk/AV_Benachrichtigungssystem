import machine
import uasyncio as asyncio
import state_manager

# Pin-Definitionen
LED_ALERT_PIN = 2
BUTTON_ACCEPT_PIN = 15
BUTTON_REJECT_PIN = 14

# Globale Hardware-Objekte
led_alert = None
button_accept = None
button_reject = None

def init_hardware():
    """Initialisiert LED und Buttons."""
    global led_alert, button_accept, button_reject

    led_alert = machine.Pin(LED_ALERT_PIN, machine.Pin.OUT)
    button_accept = machine.Pin(BUTTON_ACCEPT_PIN, machine.Pin.IN, machine.Pin.PULL_DOWN)
    button_reject = machine.Pin(BUTTON_REJECT_PIN, machine.Pin.IN, machine.Pin.PULL_DOWN)

async def button_task():
    """Überwacht die Buttons und ändert den Nachrichtenstatus."""
    global led_alert, button_accept, button_reject

    while True:
        # LED zeigt an, ob eine wartende Nachricht existiert
        msg = await state_manager.get_message()
        if msg:
            led_alert.value(1)
        else:
            led_alert.value(0)

        # Accept gedrückt?
        if button_accept.value() == 1:
            print("✅ Button ACCEPT gedrückt – Nachricht wird akzeptiert.")
            await state_manager.accept_last_message()
            await asyncio.sleep(0.3)  # Entprellen

        # Reject gedrückt?
        if button_reject.value() == 1:
            print("❌ Button REJECT gedrückt – Nachricht wird abgelehnt.")
            await state_manager.reject_last_message()
            await asyncio.sleep(0.3)  # Entprellen

        await asyncio.sleep(0.05)  # Polling-Intervall