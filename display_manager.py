# filename: display_manager.py
from machine import Pin, SoftI2C
import uasyncio as asyncio
import sh1106
import writer
import roboto_48

# --- KONFIGURATION ---
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
I2C_ADDR = 0x3c
SDA_PIN = 16
SCL_PIN = 17
SCROLL_SPEED = 2  
SCROLL_DELAY = 0.05 
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
        self.font = roboto_48 # <-- OPTIMIERUNG 1: Schriftart cachen
        
        try:
            # 1. SoftI2C-Bus initialisieren
            self.i2c = SoftI2C(scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=400000)
            
            # ... I2C-Scan-Prüfung ...
            devices = self.i2c.scan()
            if not devices or I2C_ADDR not in devices:
                 raise DisplayInitializationError(
                    f"I2C-Adresse {hex(I2C_ADDR)} nicht gefunden. Gefunden: {[hex(d) for d in devices]}"
                )
            
            # 2. Display-Objekt initialisieren
            self.display = sh1106.SH1106_I2C(
                DISPLAY_WIDTH, DISPLAY_HEIGHT, self.i2c, addr=I2C_ADDR, rotate=180
            )
            self.display.fill(0)
            self.display.show()
            self.display.poweroff()
            
            # 3. Writer-Objekt initialisieren
            self.writer = writer.Writer(self.display, self.font) # <-- OPTIMIERUNG 1
            
            # FIX 1: Deaktiviert Word Wrap
            self.writer.wrap = False 
            
            # FIX 2 (NEU): Deaktiviert den horizontalen Zeilenumbruch (col_clip = True)
            # Dadurch wird das ungewollte vertikale Scrollen verhindert.
            self.writer.col_clip = True 
            
        except Exception as e:
            raise DisplayInitializationError(f"Error initializing the display: {e}") 

    def set_text(self, text):
        if text != self._current_text:
            self._current_text = text
            
            if self._scroll_task and self._scroll_task.done() is False:
                self._scroll_task.cancel()
                
            if self.display and text:
                self._scroll_task = asyncio.create_task(self._scroll_task_loop())
            
    def _calculate_dims(self, text):
        y_start = (DISPLAY_HEIGHT - self.font.height()) // 2 # <-- OPTIMIERUNG 1
        text_width = self.writer.stringlen(text)
        
        if text_width <= DISPLAY_WIDTH:
            x_start = (DISPLAY_WIDTH - text_width) // 2
            x_end = x_start
        else:
            x_start = DISPLAY_WIDTH
            x_end = -text_width
            
        return text_width, y_start, x_start, x_end

    async def _scroll_task_loop(self):
        # --- OPTIMIERUNG 3: Methoden-Lookups cachen ---
        _text = self._current_text
        _render = self._render_text
        _sleep = asyncio.sleep
        _scroll_delay = SCROLL_DELAY
        _scroll_speed = SCROLL_SPEED
        # --- Ende Optimierung 3 ---

        text_width, y_start, x_start, x_end = self._calculate_dims(_text)
        current_x = x_start
        
        self.display.poweron()

        # Statischer Text (nicht scrollend)
        if x_start == x_end:
            _render(_text, y_start, x_start)
            return # Task beenden, rendern ist fertig

        # Scrolling-Schleife
        while True:
            _render(_text, y_start, int(current_x))
            current_x -= _scroll_speed
            
            if current_x <= x_end:
                current_x = x_start
                await _sleep(0.5) # Kurze Pause am Ende
            
            await _sleep(_scroll_delay)

    def _render_text(self, text, y_start, x_start):
        """Manipuliert den internen Zustand für negative X-Koordinaten."""
        devid = id(self.display)
        if devid in writer.Writer.state:
            state = writer.Writer.state[devid]
            state.text_row = y_start
            state.text_col = x_start 

        # --- OPTIMIERUNG 2: Nur Textbereich löschen (I2C sparen) ---
        # self.display.fill(0) # <-- ALT: Löscht 1024 Bytes
        self.display.fill_rect(0, y_start, DISPLAY_WIDTH, self.font.height(), 0)
        # --- Ende Optimierung 2 ---

        # printstring wird nun ohne ungewollten Zeilenumbruch ausgeführt
        self.writer.printstring(text)
        
        # show() sendet jetzt dank fill_rect() nur die geänderten 6 Seiten (768 Bytes)
        self.display.show()
        
    async def display_task(self):
        while True:
            await asyncio.sleep(1)

