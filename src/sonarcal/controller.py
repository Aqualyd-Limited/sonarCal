"""Omnisonar calibration program

Provides omni and echogram displays and sphere amplitude plots for use when
calibrating omni-directional sonars.
"""
# TODO:
# Choose beam_group based on beam type rather than requiring it in the config file

import tkinter as tk
from functools import partial
import threading
import queue
import sys

from .echogram_plotter import echogramPlotter
from .utils import setupLogging, on_exit, window_closed
from .file_ops import file_listen, file_replay
from .calibration_gui import calibrationGUI
from .configuration import config

if sys.platform == "win32":
    import win32api

setupLogging()


def main():
    """Omnisonar calibration graphical user interface."""    

    ##########################################
    # Start things...

    # queue to communicate between two threads
    msg_queue = queue.Queue()
    
    # Tk GUI
    root = tk.Tk()

    # handle to the function that does the echogram drawing
    # job = None  

    echogram = echogramPlotter(msg_queue, root)
    gui = calibrationGUI(echogram)
    # Check periodically for new echogram data
    # job = root.after(echogram.checkQueueInterval, echogram.newPing, gui.status_label())

    # Start receive in a separate thread
    if config.liveData():
        t = threading.Thread(target=file_listen, args=(config.watchDir(),
                                                       config.horizontalBeamGroup(),
                                                       msg_queue))
    else:
        t = threading.Thread(target=file_replay, args=(config.watchDir(),
                                                       config.horizontalBeamGroup(),
                                                       msg_queue,
                                                       config.replayRate()))
    t.daemon = True  # makes the thread close when main() ends
    t.start()

    # For Windows, catch when the console is closed
    if sys.platform == "win32":
        win32api.SetConsoleCtrlHandler(partial(on_exit, gui.root(), gui.job()), True)

    # And start things...
    root.protocol("WM_DELETE_WINDOW", lambda: window_closed(gui.root(), gui.job()))
    root.mainloop()


