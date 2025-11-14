# filename: display_manager.py
from machine import Pin, SoftI2C
import uasyncio as asyncio
import sh1106
import writer
import roboto_40

# --- KONFIGURATION ---
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
I2C_ADDR = 0x3c
SDA_PIN = 16
SCL_PIN = 17
SCROLL_SPEED = 4       # Pixel pro Schritt
SCROLL_DELAY = 0.03     # Sekunden zwischen Frames (Trade-off, siehe _render_text)
# ----------------------

class DisplayInitializationError(Exception):
    """Custom exception for display initialization errors."""
    pass

class DisplayManager:
    def __init__(self):
        self._current_text = ""
        self.display = None
        self.writer = None
        self._scroll_task = None
        self.font = roboto_40  # Schriftart cachen

        try:
            # 1. SoftI2C initialisieren
            self.i2c = SoftI2C(scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=400000)

            # I2C-Scan prüfen
            devices = self.i2c.scan()
            if not devices or I2C_ADDR not in devices:
                raise DisplayInitializationError(
                    f"I2C-Adresse {hex(I2C_ADDR)} nicht gefunden. Gefunden: {[hex(d) for d in devices]}"
                )

            # 2. Display initialisieren
            self.display = sh1106.SH1106_I2C(
                DISPLAY_WIDTH, DISPLAY_HEIGHT, self.i2c, addr=I2C_ADDR, rotate=180
            )
            self.display.fill(0)
            self.display.show()
            self.display.poweroff()

            # 3. Writer initialisieren
            self.writer = writer.Writer(self.display, self.font)
            self.writer.wrap = False   # Kein Word Wrap
            self.writer.col_clip = True  # Kein vertikales Scrollen

        except Exception as e:
            raise DisplayInitializationError(f"Error initializing the display: {e}")

    # -------------------------
    # Text setzen
    # -------------------------
    def set_text(self, text):
        """Setzt neuen Text und startet den Scroll-Task asynchron."""
        if text != self._current_text:
            self._current_text = text

            # Stoppe alten Task, falls aktiv
            if self._scroll_task and not self._scroll_task.done():
                self._scroll_task.cancel()

            # Starte neuen Scroll-Task
            if self.display and text:
                self._scroll_task = asyncio.create_task(self._scroll_task_loop())

    # -------------------------
    # Berechne Start/End-Koordinaten
    # -------------------------
    def _calculate_dims(self, text):
        y_start = (DISPLAY_HEIGHT - self.font.height()) // 2
        text_width = self.writer.stringlen(text)

        if text_width <= DISPLAY_WIDTH:
            x_start = (DISPLAY_WIDTH - text_width) // 2
            x_end = x_start  # kein Scrollen nötig
        else:
            x_start = DISPLAY_WIDTH
            x_end = -text_width  # Scrollen von rechts nach links

        return text_width, y_start, x_start, x_end

    # -------------------------
    # Scroll-Task
    # -------------------------
    async def _scroll_task_loop(self):
        _text = self._current_text
        text_width, y_start, x_start, x_end = self._calculate_dims(_text)
        current_x = x_start
        self.display.poweron()

        # Statischer Text (nicht scrollend)
        if x_start == x_end:
            self._render_text(_text, y_start, x_start)
            return

        # Scroll-Loop
        while True:
            # _render_text() enthält den blockierenden display.show() Aufruf
            self._render_text(_text, y_start, int(current_x))
            current_x -= SCROLL_SPEED

            if current_x <= x_end:
                current_x = x_start
                await asyncio.sleep(0.5)  # kurze Pause am Ende

            # Delay + Eventloop-Freigabe
            # Das `await` gibt die Kontrolle an andere Tasks ab (z.B. Webserver)
            await asyncio.sleep(SCROLL_DELAY)
            
            # --- OPTIMIERUNG ---
            # Entfernt: await asyncio.sleep(0)
            # Das vorherige sleep(SCROLL_DELAY) reicht bereits aus,
            # um die Kontrolle an den Scheduler abzugeben.

    # -------------------------
    # Text rendern
    # -------------------------
    def _render_text(self, text, y_start, x_start):
        """Render nur die Zeile, die Text enthält, spart I2C."""
        devid = id(self.display)
        if devid in writer.Writer.state:
            state = writer.Writer.state[devid]
            state.text_row = y_start
            state.text_col = x_start

        # Nur den Bereich der Zeile löschen
        self.display.fill_rect(0, y_start, DISPLAY_WIDTH, self.font.height(), 0)

        # Text drucken
        self.writer.printstring(text)

        # --- HINWEIS ZUR PERFORMANCE ---
        # display.show() ist eine BLOCKIERENDE I2C-Operation.
        # Sie sendet den Puffer an das Display und blockiert währenddessen
        # den gesamten asyncio Event-Loop (ca. 25-30ms bei 400kHz).
        #
        # Der Trade-off:
        # - Niedriger SCROLL_DELAY = Flüssiges Scrollen, aber schlechtere
        #   Reaktionszeit für andere Tasks (z.B. Webserver).
        # - Hoher SCROLL_DELAY = Ruckeliges Scrollen, aber bessere
        #   Reaktionszeit für andere Tasks.
        self.display.show()

    # -------------------------
    # Optionaler Hintergrundtask
    # -------------------------
    async def display_task(self):
        """Nur als Platzhalter für andere Periodik, kann parallel laufen."""
        while True:
            await asyncio.sleep(1)