import sys
import os
import re
import threading
from datetime import datetime
from config import LOGS_DIR

class DualLogger:
    def __init__(self, base_filename):
        self.terminal = sys.stdout
        self.base_filename = base_filename
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self._lock = threading.Lock()

        self.current_filename = self._get_filename_for_date(self.current_date)
        self.log_file = open(self.current_filename, "a", encoding="utf-8")

    def _get_filename_for_date(self, date_str):
        # Assumes base_filename is something like 'mia_log.log'
        # Injects date before extension
        name, ext = os.path.splitext(self.base_filename)
        return f"{name}_{date_str}{ext}"

    def _rotate_if_needed(self):
        hoy = datetime.now().strftime("%Y-%m-%d")
        if hoy != self.current_date:
            self.current_date = hoy
            nuevo = self._get_filename_for_date(hoy)
            if nuevo != self.current_filename:
                try:
                    self.log_file.close()
                except:
                    pass
                self.current_filename = nuevo
                self.log_file = open(self.current_filename, "a", encoding="utf-8")

    def write(self, message):
        with self._lock:
            self._rotate_if_needed()
            self.terminal.write(message) 
            self.log_file.write(message) 
            self.log_file.flush()        

    def flush(self):
        with self._lock:
            self.terminal.flush()
            self.log_file.flush()

def setup_logger():
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    nombre_log = os.path.join(LOGS_DIR, f"mia_log.log")
    
    dual_logger = DualLogger(nombre_log)
    sys.stdout = dual_logger
    sys.stderr = dual_logger
    return dual_logger
