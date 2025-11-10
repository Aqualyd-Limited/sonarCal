"""Omnisonar calibration program

Provides omni and echogram displays and sphere amplitude plots for use when
calibrating omni-directional sonars.
"""
# TODO:
# Choose beam_group based on beam type rather than requiring it in the config file

import configparser
import tkinter as tk
import tkinter.font as tkFont
from functools import partial
import threading
import queue
import logging
import sys
from pathlib import Path
import matplotlib as mpl
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from platformdirs import PlatformDirs

from .echogram_plotter import echogramPlotter
from .utils import setupLogging, app_name
from .file_ops import file_listen, file_replay

if sys.platform == "win32":
    import win32api

# Configure logging
dirs = PlatformDirs(appname=app_name, appauthor="Aqualyd")
log_dir = Path(dirs.user_log_dir)
log_dir.mkdir(parents=True, exist_ok=True)
setupLogging(log_dir, app_name)


def main():
    """Omnisonar calibration graphical user interface."""    
    ##########################################
    # Sort out the configuration file
    config_filename = Path(dirs.user_config_dir)/'config.ini'
    config_filename.parent.mkdir(parents=True, exist_ok=True)
    
    config = configparser.ConfigParser()
    c = config.read(config_filename, encoding='utf8')

    if not c:  # config file not found, so make one
        config['DEFAULT'] = {'numPingsToShow': 100,
                             'maxRange': 50,
                             'maxSv': -20,
                             'minSv': -60,
                             'replayRate': 'realtime',
                             'horizontalBeamGroupPath': 'Sonar/Beam_group1',
                             'watchDir': '.',
                             'liveData': 'yes'
                             }

        with open(config_filename, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        # TODO - open config dialog instead of exitting here
        print('No config file was found, so ' + str(config_filename) +
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

    ##########################################
    # Start things...

    mpl.use('TkAgg')


    # queue to communicate between two threads
    msg_queue = queue.Queue()
    root = tk.Tk()
    root.wm_title('Sonar calibrator')

    job = None  # handle to the function that does the echogram drawing

    # Does the message parsing and echogram display
    echogram = echogramPlotter(numPings, maxRange, maxSv, minSv, msg_queue, root, job)

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
        t = threading.Thread(target=file_listen, args=(watchDir, horizontalBeamGroup, msg_queue))
    else:
        t = threading.Thread(target=file_replay, args=(watchDir, horizontalBeamGroup, 
                                                       replayRate, msg_queue))

    t.daemon = True  # makes the thread close when main() ends
    t.start()

    # Check periodically for new echogram data
    job = root.after(echogram.checkQueueInterval, echogram.newPing, label)

    # For Windows, catch when the console is closed
    if sys.platform == "win32":
        win32api.SetConsoleCtrlHandler(partial(on_exit, root, job), True)

    # And start things...
    root.protocol("WM_DELETE_WINDOW", lambda: window_closed(root, job))
    root.mainloop()


def on_exit(root, job, sig):
    """Call when the Windows cmd console closes."""
    root.after_cancel(job)
    logging.info('Program ending...')
    root.quit()
    # not sure why this call is needed...
    window_closed(root, job)


def window_closed(root, job):
    """Call to nicely end the whole program."""
    root.after_cancel(job)
    logging.info('Program ending...')
    logging.shutdown()  # not working???
    root.quit()
