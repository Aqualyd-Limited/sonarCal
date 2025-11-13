
import webbrowser
import logging
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from importlib.metadata import version
from PIL import Image, ImageTk
from .utils import window_closed, app_name, autosave_dir
from .calibration_data import calibrationData
from .calculate_gains import calculate_gain
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

logger = logging.getLogger(app_name)
icon_file = Path(__file__).parent/'assets'/'logo.png'  # TODO get via a config file

class calibrationGUI:
    """Provides the main GUI container and misc labels/buttons."""

    def __init__(self, echogram, title='TITLE', help_uri=None):
        self.echogram = echogram
        self.help_uri = help_uri

        # Calibration gains are stored in here
        self.cal_data = calibrationData()
        # sphere ts for the current beam calibration is stored in here
        self.sphere_ts = []

        # The GUI window
        self.echogram.root.title(title)
        
        # Dialogs that we keep around
        self.results_dialog = None
        
        # The toolbar and window icon/logo
        self.icon = ImageTk.PhotoImage(Image.open(icon_file))
        self.echogram.root.iconphoto(False, self.icon)

        # Things to do with new pings 
        self.echogram.set_ping_callback(self.new_ping)

        # Put the matplotlib plots into the GUI window.
        canvas = FigureCanvasTkAgg(self.echogram.fig, master=self.echogram.root)
        canvas.get_tk_widget().pack(side='top', fill='both', expand=True, padx=5, pady=5)

        # Styles. These apply to all widgets, not just the ones create in this function
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

        # Start listening for sonar data
        self.echogram.newPing(self.status_label())

    def job(self):
        return self.echogram.job

    def root(self):
        return self.echogram.root

    def onaxis_changed(self):
        """A beam calibration has either started or ended."""
        if self.onaxis_value.get():  # start calibrating a beam
            self.echogram.beamLine.freeze(True)
            logger.info('Beam %s calibration started', self.echogram.beamLabel)
        else:  # finished calibrating a beam
            self.auto_save()
            logger.info('Beam %s calibration complete', self.echogram.beamLabel)
            self.echogram.beamLine.freeze(False)
            self.sphere_ts = []
            if self.results_dialog:
                self.results_dialog.update_rows(None)  # unhighlights the previously active row

    def auto_save(self):
        """Save cal results to an autosave location."""
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        filename = autosave_dir/('results_' + timestamp + '.csv')
        self.cal_data.save(filename)

    def new_ping(self):
        """Orchestrates things for each new ping."""
        e = self.echogram
        if e.beamLine.frozen():  # a beam is being calibrated
            # store the current ping's sphere echo info
            self.sphere_ts.append((datetime.now().isoformat(), e.amp[1, -1], e.rangeMax))
            # calculate the beam gain and other stats
            (gain, rms, r, num) = calculate_gain(self.sphere_ts)
            # store the latest beam gain values
            self.cal_data.update(e.beamLabel, datetime.now().strftime('%H:%M:%S'), gain, rms, r, num)
            # update the results dialog if present
            if self.results_dialog:
                self.results_dialog.update_with(self.cal_data, e.beamLabel)

    def about(self):
        message = (f'Sonarcal, version {version("sonarcal")}\n\n'
                   'A program to assist with calibrating omni-directional sonars.\n\n'
                   'Developed by Aqualyd Ltd\n\n'
                   'www.aqualyd.nz')

        messagebox.showinfo(title='About', message=message)

    def close(self):
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
        configDialog(self.echogram.root, self.icon)

    def status_label(self):
        return self.label


class configDialog:
    """A dialog box to set and change application parameters."""
    def __init__(self, parent, icon=None):
        self.top = tk.Toplevel(parent)
        self.top.title("Config")
        if icon:
            self.top.iconphoto(False, icon)

        ttk.Label(self.top, text="Configs").pack(padx=20, pady=10)
        ttk.Button(self.top, text="Close", command=self.close_dialog).pack(pady=5)
        ttk.Button(self.top, text="Apply", command=self.apply).pack(pady=5)

    def apply(self):
        pass

    def close_dialog(self):
        self.top.destroy()


