
import webbrowser
import logging
from datetime import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox, filedialog
from importlib.metadata import version
from platform import python_version
from PIL import Image, ImageTk
from .utils import window_closed
from .calibration_data import calibrationData
from .calculate_gains import calculate_calibration
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from .configuration import config as cfg
import sv_ttk
logger = logging.getLogger(cfg.appName())

class calibrationGUI:
    """Provides the main GUI container and misc labels/buttons."""

    def __init__(self, echogram, reload_event):

        self.echogram = echogram
        self.reload_event = reload_event
        self.help_uri = str(cfg.helpURI())

        # Calibration gains are stored in here
        self.cal_data = calibrationData()
        # sphere echo data for the current beam calibration is stored in here
        self.sphere_echoes = []

        # The GUI window
        self.echogram.root.title(cfg.title())
        
        # Dialogs that we keep around
        self.results_dialog = None
        self.config_dialog = None
        
        # The toolbar and window icon/logo
        self.icon = ImageTk.PhotoImage(Image.open(cfg.iconFile()))
        self.echogram.root.iconphoto(False, self.icon)

        # Things to do with new pings 
        self.echogram.set_ping_callback(self.new_ping)

        # Put the matplotlib plots into the GUI window.
        canvas = FigureCanvasTkAgg(self.echogram.fig, master=self.echogram.root)
        canvas.get_tk_widget().pack(side='top', fill='both', expand=True, padx=5, pady=5)

        # Styles. These apply to all widgets, not just the ones created in this function
        s = ttk.Style()
        s.configure('TButton', font=('Arial', 16))
        s.configure('TLabel', font=('Arial', 12))
        s.configure('TCheckbutton', font=('Arial', 16))
        s.configure('Treeview.Heading', font=('Arial', 12, 'bold'))
        s.configure('Treeview', font=('Arial', 12))

        # A label to show the last received message time
        self.label = ttk.Label(self.echogram.root)
        self.label.pack(side=tk.TOP, fill=tk.BOTH)
        self.label.config(text='Waiting for data...', width=100, anchor=tk.W)

        ttk.Separator(self.echogram.root, orient='horizontal').pack(fill='x', padx=10, pady=5)

        # Buttons for help, on-axis toggle, config dialog, and close
        self.onaxis_value = tk.BooleanVar(value=False)

        frame = ttk.Frame(self.echogram.root)
        results = ttk.Button(frame, text='Results', command=self.results)
        config = ttk.Button(frame, text='Config', command=self.config)
        onaxis = ttk.Checkbutton(frame, text='On-axis', variable=self.onaxis_value,
                                 command=self.onaxis_changed)
        help = ttk.Button(frame, text='Help', command=self.help)
        about = ttk.Button(frame, text='About', command=self.about)
        close = ttk.Button(frame, text='Close', command=self.close)

        onaxis.pack(side=tk.LEFT)
        close.pack(side=tk.RIGHT)
        about.pack(side=tk.RIGHT)
        help.pack(side=tk.RIGHT)
        config.pack(side=tk.RIGHT)
        results.pack(side=tk.RIGHT)

        frame.pack(side=tk.TOP, fill=tk.BOTH)
        sv_ttk.set_theme('light')
        
        # At startup ask the user for the directory to watch for sonar files
        if cfg.askForWatchDir():
            d = filedialog.askdirectory(parent=self.echogram.root, title='Select sonar data directory',
                                            initialdir=cfg.watchDir())
            if d:
                cfg.watchDir(d)
        
        # Start listening for sonar data
        self.echogram.newPing(self.status_label())

    def job(self):
        return self.echogram.job

    def root(self):
        return self.echogram.root

    def onaxis_changed(self):
        """A beam calibration has either started or ended."""
        if not self.echogram.beamLine:
            return

        if self.onaxis_value.get():  # start calibrating a beam
            self.echogram.beamLine.freeze(True)
            logger.info('Beam %s calibration started', self.echogram.beamLabel)
        else:  # finished calibrating a beam
            logger.info('Beam %s calibration complete', self.echogram.beamLabel)
            self.auto_save()
            self.echogram.beamLine.freeze(False)
            self.sphere_echoes = []
            if self.results_dialog:
                self.results_dialog.update_rows(None)  # unhighlights the previously active row

    def auto_save(self):
        """Save cal results to an autosave location."""
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        filename = cfg.autoSaveDir()/('results_' + timestamp + '.csv')
        self.cal_data.save(filename)

    def new_ping(self):
        """Orchestrates things for each new ping."""
        e = self.echogram
        if e.beamLine.frozen():  # a beam is being calibrated
            # store the current ping's sphere echo info
            self.sphere_echoes.append((datetime.now().isoformat(), e.amp[1, -1], e.rangeMax))
            # calculate the beam gain and other stats
            (cal_offset, ts, rms, r, num) = calculate_calibration(self.sphere_echoes, cfg.sphereTS())
            # store the latest beam gain values
            self.cal_data.update(e.beamLabel, datetime.now().strftime('%H:%M:%S'),
                                 e.gains[e.beamIdx], cal_offset, ts, rms, r, num)
            # update the results dialog if present
            if self.results_dialog:
                self.results_dialog.update_with(self.cal_data, e.beamLabel)

    def about(self):
        message = (f'Sonarcal, version {version("sonarcal")}, running on Python {python_version()}\n\n'
                   'Sonarcal is a program to assist with calibrating omni-directional sonars.\n\n'
                   'Developed by Aqualyd Ltd, www.aqualyd.nz')

        messagebox.showinfo(title='About', message=message)

    def close(self):
        # Catch closing the program while still calibrating a beam
        if self.echogram.beamLine and self.echogram.beamLine.frozen():
            self.auto_save()
        window_closed(self.echogram.root, self.echogram.job)

    def results(self):
        """Open the Results dialog box."""
        # want one lasting instance of this dialog so manage that here
        if not self.results_dialog:
            # deferred to reduce startup time
            from .dialog_results import resultsDialog
            self.results_dialog = resultsDialog(self.echogram.root, self.cal_data, self.icon)
        else:
            self.results_dialog.reopen()

    def help(self):
        """Open the help documentation in a web browser."""
        if not webbrowser.open(self.help_uri, new=2):
            logging.warning('Failed to start a webbrowser to show the help documentation')
        
    def config(self):
        """Open the Config dialog box."""
        if not self.config_dialog:
            from .dialog_config import configDialog  # deferred importing
            self.config_dialog = configDialog(self.echogram.root, self.icon, self.config_updated)
        else:
            self.config_dialog.reopen()

    def config_updated(self, updated: list = None):
        """Things to do when the configuration is updated."""
        self.echogram.updateRangeSliderSettings()
        self.echogram.updateDiffPlotYLim()
        self.echogram.updateMaxRange()
        self.echogram.updateNumPings()
        self.echogram.updatePolarAxisLabels()
        
        # If data directory or live play config has changed, tell the file reader to reload.
        # The strings in the get call come from the setting name in the config file (also in the
        # SonarcalConfig() class).
        if updated and ('watchDir' in updated or 'liveData' in updated):
            logger.info('Resetting file reader - data directory or live viewing settings changed')
            self.reload_event.set()

    def status_label(self):
        return self.label
