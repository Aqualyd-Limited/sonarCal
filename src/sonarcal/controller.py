"""Omnisonar calibration program

Provides omni and echogram displays and sphere amplitude plots for use when
calibrating omni-directional sonars.
"""
# TODO:
# Choose beam_group based on beam type rather than requiring it in the config file

import configparser
import tkinter as tk
from functools import partial
import threading
import queue
import sys
from pathlib import Path

from platformdirs import PlatformDirs

from .echogram_plotter import echogramPlotter
from .utils import setupLogging, app_name, on_exit, window_closed
from .file_ops import file_listen, file_replay
from .calibration_gui import calibrationGUI

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
                             'liveData': 'no',
                             'helpURI': 'https://aqualyd-limited.github.io/sonarCal/'
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
    helpURI = config.get('DEFAULT', 'helpURI')

    ##########################################
    # Start things...

    # queue to communicate between two threads
    msg_queue = queue.Queue()
    
    # Tk GUI
    root = tk.Tk()

    # handle to the function that does the echogram drawing
    # job = None  

    echogram = echogramPlotter(numPings, maxRange, maxSv, minSv, msg_queue, root)
    gui = calibrationGUI(echogram, title='Sonar calibration', help_uri=helpURI)
    # Check periodically for new echogram data
    # job = root.after(echogram.checkQueueInterval, echogram.newPing, gui.status_label())

    # Start receive in a separate thread
    if liveData:
        t = threading.Thread(target=file_listen, args=(watchDir, horizontalBeamGroup, msg_queue))
    else:
        t = threading.Thread(target=file_replay, args=(watchDir, horizontalBeamGroup, msg_queue,
                                                       replayRate))
    t.daemon = True  # makes the thread close when main() ends
    t.start()

    # For Windows, catch when the console is closed
    if sys.platform == "win32":
        win32api.SetConsoleCtrlHandler(partial(on_exit, gui.root(), gui.job()), True)

    # And start things...
    root.protocol("WM_DELETE_WINDOW", lambda: window_closed(gui.root(), gui.job()))
    root.mainloop()


