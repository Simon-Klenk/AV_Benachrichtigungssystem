# filename: display_manager.py
from machine import Pin, I2C
import uasyncio as asyncio
import sh1106
import writer
import spleen_32
import _thread

# --- KONFIGURATION ---
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
I2C_ADDR = 0x3c
SDA_PIN = 16
SCL_PIN = 17
SCROLL_SPEED = 4       # Pixel pro Schritt (so schnell wie möglich)
# ----------------------

class DisplayInitializationError(Exception):
    pass

class DisplayManager:
    def __init__(self):
        self._current_text = ""
        self.display = None
        self.writer = None

        # Multi-Core Variablen
        self._core1_text = ""
        self._core1_lock = _thread.allocate_lock()
        self._core1_running = False

        self.font = spleen_32

        try:
            self.i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=400000)

            devices = self.i2c.scan()
            if not devices or I2C_ADDR not in devices:
                raise DisplayInitializationError("I2C-Adresse nicht gefunden.")

            self.display = sh1106.SH1106_I2C(
                DISPLAY_WIDTH, DISPLAY_HEIGHT, self.i2c, addr=I2C_ADDR, rotate=180
            )
            self.display.fill(0)
            self.display.show()
            self.display.poweroff()

            self.writer = writer.Writer(self.display, self.font)
            self.writer.wrap = False
            self.writer.col_clip = True

        except Exception as e:
            raise DisplayInitializationError(f"Display Init fehlgeschlagen: {e}")

    # -------------------------------------------------------
    # Text setzen
    # -------------------------------------------------------
    def set_text(self, text):
        if text != self._current_text:
            self._current_text = text
            with self._core1_lock:
                self._core1_text = text

            if not self._core1_running:
                _thread.start_new_thread(self._core1_scroll_thread, ())

    # -------------------------------------------------------
    # Berechnung Textmaße
    # -------------------------------------------------------
    def _calculate_dims(self, text):
        y_start = (DISPLAY_HEIGHT - self.font.height()) // 2
        text_width = self.writer.stringlen(text)

        if text_width <= DISPLAY_WIDTH:
            x_start = (DISPLAY_WIDTH - text_width) // 2
            x_end = x_start
        else:
            x_start = DISPLAY_WIDTH
            x_end = -text_width

        return text_width, y_start, x_start, x_end

    # -------------------------------------------------------
    # MAX-SPEED Scroll Thread (Core 1)
    # -------------------------------------------------------
    def _core1_scroll_thread(self):
        self._core1_running = True
        self.display.poweron()

        _text = ""
        text_width = y_start = x_start = x_end = 0
        current_x = 0

        while self._core1_running:

            # Textwechsel prüfen
            with self._core1_lock:
                new_text = self._core1_text

            if new_text != _text:
                _text = new_text
                text_width, y_start, x_start, x_end = self._calculate_dims(_text)
                current_x = x_start

                # statischer Text → einmal zeichnen
                if x_start == x_end:
                    self._render_text(_text, y_start, x_start)
                    continue

            # --- MAXIMALE GESCHWINDIGKEIT ---
            # Keine Delays, keine Timer – einfach nonstop rendern
            self._render_text(_text, y_start, int(current_x))

            current_x -= SCROLL_SPEED
            if current_x <= x_end:
                current_x = x_start

    # -------------------------------------------------------
    # Zeichnen
    # -------------------------------------------------------
    def _render_text(self, text, y_start, x_start):
        devid = id(self.display)
        if devid in writer.Writer.state:
            state = writer.Writer.state[devid]
            state.text_row = y_start
            state.text_col = x_start

        self.display.fill_rect(0, y_start, DISPLAY_WIDTH, self.font.height(), 0)
        self.writer.printstring(text)

        with self._core1_lock:
            self.display.show()

    # -------------------------------------------------------
    async def run(self):
        while True:
            await asyncio.sleep(1)