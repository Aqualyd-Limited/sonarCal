"""Omnisonar calibration program

Provides omni and echogram displays and sphere amplitude plots for use when
calibrating sonars with horizontal beams.
"""

import tkinter as tk
from functools import partial
import threading
import queue
import sys
from importlib.metadata import version
from platform import python_version, uname

from .echogram_plotter import echogramPlotter
from .utils import setupLogging, on_exit, window_closed
from .file_ops import sonar_file_read
from .calibration_gui import calibrationGUI

logger = setupLogging()

def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    logger.critical("Uncaught exception, application will terminate.",
                    exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_uncaught_exception


def main():
    """Omnisonar calibration graphical user interface."""

    logger.info('Running Sonarcal version %s on Python %s', version("sonarcal"), python_version())
    logger.info('Computer is a %s running %s release %s ',
                uname().machine, uname().system, uname().release)

    # queue to communicate between two threads
    msg_queue = queue.Queue()
    
    # This event is used to signal to the file reading thread that the data directory 
    # has changed and it should read files the new data directory
    reload_event = threading.Event()

    # The GUI
    root = tk.Tk()
    echogram = echogramPlotter(msg_queue, root)
    gui = calibrationGUI(echogram, reload_event)

    # Sonar files are read from a separate thread
    t = threading.Thread(target=sonar_file_read, args=(msg_queue, reload_event))

    t.daemon = True  # makes the thread close when main() ends
    t.start()

    # For Windows, catch when the console is closed
    if sys.platform == "win32":
        import win32api
        win32api.SetConsoleCtrlHandler(partial(on_exit, gui.root(), gui.job()), True)

    # And start things...
    root.protocol("WM_DELETE_WINDOW", lambda: window_closed(gui.root(), gui.job()))
    root.mainloop()
