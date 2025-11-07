"""Omnisonar calibration program

Provides omni and echogram displays and sphere amplitude plots for use when
calibrating omni-directional sonars.
"""
# TODO:
# Choose beam_group based on beam type rather than requiring it in the config file

import configparser

import tkinter as tk
import tkinter.font as tkFont
import threading
import queue
import logging
import logging.handlers
import sys
from pathlib import Path

import matplotlib as mpl
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .echogram_plotter import echogramPlotter
from .utils import setupLogging
from .file_ops import file_listen, file_replay

if sys.platform == "win32":
    import win32api


# The config file should be in the same directory as this script.
parent = Path(__file__).resolve().parent
configFilename = parent.joinpath('sonar_calibration.ini')

mpl.use('TkAgg')

# queue to communicate between two threads
queue = queue.Queue()
root = tk.Tk()
root.wm_title('Sonar calibrator')

job = None  # handle to the function that does the echogram drawing


def main():
    """Omnisonar calibration user interface."""
    config = configparser.ConfigParser()
    c = config.read(configFilename, encoding='utf8')

    if not c:  # config file not found, so make one
        config['DEFAULT'] = {'numPingsToShow': 100,
                             'maxRange': 50,
                             'maxSv': -20,
                             'minSv': -60,
                             'replayRate': 'realtime',
                             'horizontalBeamGroupPath': 'Sonar/Beam_group1',
                             'watchDir': 'directory where the .nc files are',
                             'liveData': 'yes',
                             'logDir': 'change this!!!!'
                             }

        with open(configFilename, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        print('No config file was found, so ' + str(configFilename) +
              ' was created. You may need to edit this file.')
        sys.exit()

    # Pull out the settings in the config file.
    numPings = config.getint('DEFAULT', 'numPingsToShow')
    maxRange = config.getfloat('DEFAULT', 'maxRange')
    maxSv = config.getfloat('DEFAULT', 'maxSv')
    minSv = config.getfloat('DEFAULT', 'minSv')
    replayRate = config.get('DEFAULT', 'replayRate')
    horizontalBeamGroup = config.get('DEFAULT', 'horizontalBeamGroupPath')
    watchDir = Path(config.get('DEFAULT', 'watchDir'))
    liveData = config.getboolean('DEFAULT', 'liveData')
    logDir = Path(config.get('DEFAULT', 'logDir'))

    setupLogging(logDir, 'sonar_calibration')

    # Does the message parsing and echogram display
    echogram = echogramPlotter(numPings, maxRange, maxSv, minSv)

    # The GUI window
    root.title('Sonar calibration')
    # Put the echogram plot into the GUI window.
    canvas = FigureCanvasTkAgg(echogram.fig, master=root)
    canvas.get_tk_widget().pack(side='top', fill='both', expand=True)

    # and a label to show the last received message time
    fontStyle = tkFont.Font(size=16)
    label = tk.Label(root, font=fontStyle)
    label.pack(side='left')
    label.config(text='Waiting for data...', width=100, anchor=tk.W)

    # Start receive in a separate thread
    if liveData:
        t = threading.Thread(target=file_listen, args=(watchDir, horizontalBeamGroup))
    else:
        t = threading.Thread(target=file_replay, args=(watchDir, horizontalBeamGroup, replayRate))

    t.daemon = True  # makes the thread close when main() ends
    t.start()

    # For Windows, catch when the console is closed
    if sys.platform == "win32":
        win32api.SetConsoleCtrlHandler(on_exit, True)

    # Check periodically for new echogram data
    global job
    job = root.after(echogram.checkQueueInterval, echogram.newPing, label)

    # And start things...
    root.protocol("WM_DELETE_WINDOW", window_closed)
    root.mainloop()


def on_exit(_sig, _func=None):
    """Call when the Windows cmd console closes."""
    window_closed()


def window_closed():
    """Call to nicely end the whole program."""
    root.after_cancel(job)
    logging.info('Program ending...')
    root.quit()


