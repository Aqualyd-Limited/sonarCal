"""Omnisonar calibration program

Provides omni and echogram displays and sphere amplitude plots for use when
calibrating omni-directional sonars.
"""

import tkinter as tk
from functools import partial
import threading
import queue
import sys

from .echogram_plotter import echogramPlotter
from .utils import setupLogging, on_exit, window_closed
from .file_ops import sonar_file_read
from .calibration_gui import calibrationGUI
from .configuration import config

if sys.platform == "win32":
    import win32api

setupLogging()


def main():
    """Omnisonar calibration graphical user interface."""    

    # queue to communicate between two threads
    msg_queue = queue.Queue()
    
    # The GUI
    root = tk.Tk()
    echogram = echogramPlotter(msg_queue, root)
    gui = calibrationGUI(echogram)

    # Start reading of sonar files in a separate thread
    t = threading.Thread(target=sonar_file_read, args=(msg_queue,))

    t.daemon = True  # makes the thread close when main() ends
    t.start()

    # For Windows, catch when the console is closed
    if sys.platform == "win32":
        win32api.SetConsoleCtrlHandler(partial(on_exit, gui.root(), gui.job()), True)

    # And start things...
    root.protocol("WM_DELETE_WINDOW", lambda: window_closed(gui.root(), gui.job()))
    root.mainloop()


