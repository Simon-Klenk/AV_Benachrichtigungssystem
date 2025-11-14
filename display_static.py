# filename: display_static.py
# ----------------------------------------------------------------------
# Klasse für statische 2-Zeilen-Anzeige (Core 0 only, kein Scrolling)
# MIT 180 GRAD DREHUNG
# ----------------------------------------------------------------------
from machine import Pin, I2C
import sh1106  # Der korrekte Treiber für Ihr Display
import writer
import spleen_32  # Die optimierte, schmale Schriftart (Muss vorhanden sein)
import utime

# --- KONFIGURATION ---
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
I2C_ADDR = 0x3c
SDA_PIN = 16
SCL_PIN = 17
# Die Schriftart ist 32 Pixel hoch, was 2 Zeilen auf 64px ergibt.
LINE_HEIGHT = 32
# -------------------------------------------------------------

class DisplayInitializationError(Exception):
    """Custom exception for display initialization errors."""
    pass

class StaticDisplayManager:
    def __init__(self):
        self.display = None
        self.writer = None
        
        self.font = spleen_32
        
        try:
            # 1. Hardware-I2C initialisieren
            # Die Pin-Zuweisung für I2C ist (scl=SCL_PIN, sda=SDA_PIN)
            self.i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=400000)

            # 2. Display initialisieren
            # WICHTIG: rotate=2 für 180 Grad Drehung!
            self.display = sh1106.SH1106_I2C(DISPLAY_WIDTH, DISPLAY_HEIGHT, self.i2c, addr=I2C_ADDR, rotate=180)
            self.display.fill(0)
            self.display.show()
            
            # 3. Writer initialisieren
            self.writer = writer.Writer(self.display, self.font)
            
            print("StaticDisplayManager: Display bereit für statische Anzeige (180° gedreht).")

        except Exception as e:
            print(f"StaticDisplayManager Fehler bei Initialisierung: {e}")
            raise DisplayInitializationError(f"I2C- oder Display-Fehler: {e}")
            
    # -------------------------
    # Public API (für Core 0)
    # -------------------------
    
    def show_two_lines(self, line1_text, line2_text):
        """
        Zeigt zwei Textzeilen (32px Höhe) statisch auf dem Display an.
        """
        if not self.display or not self.writer:
            print("Fehler: Display ist nicht initialisiert.")
            return

        # 1. Display Buffer komplett löschen
        self.display.fill(0)
        
        # 2. Zeile 1 rendern (Start bei Y=0)
        self._render_line(line1_text, y_start=0)
        
        # 3. Zeile 2 rendern (Start bei Y=32)
        self._render_line(line2_text, y_start=LINE_HEIGHT)
        
        # 4. Daten an das Display senden
        self.display.show()
        
    def _render_line(self, text, y_start):
        """Hilfsfunktion, um eine einzelne Zeile in den Buffer zu rendern."""
        
        devid = id(self.display)
        if devid in writer.Writer.state:
            state = writer.Writer.state[devid]
            state.text_row = y_start
            state.text_col = 0 # Text beginnt immer links
        
        # Text in den Buffer drucken
        self.writer.printstring(text)