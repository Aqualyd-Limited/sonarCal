
import webbrowser
import logging
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog as fd
from tkinter import messagebox
from importlib.metadata import version
from PIL import Image, ImageTk
from .utils import window_closed, app_name
from .calibration_data import calibrationData
from .calculate_gains import calculate_gain
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from platformdirs import PlatformDirs

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
            logger.info('Beam %d calibration started', self.echogram.beam)
        else:  # finished calibrating a beam
            logger.info('Beam %d calibration complete', self.echogram.beam)
            self.echogram.beamLine.freeze(False)
            self.sphere_ts = []
            if self.results_dialog:
                self.results_dialog.update_rows(None)  # unhighlights the previously active row

    def new_ping(self):
        """Orchestrates things for each new ping."""
        e = self.echogram
        if e.beamLine.frozen():  # a beam is being calibrated
            # store the current ping's sphere echo info
            self.sphere_ts.append((datetime.now().isoformat(), e.amp[1, -1], e.rangeMax))
            # calculate the beam gain and other stats
            (gain, rms, r, num) = calculate_gain(self.sphere_ts)
            # store the latest beam gain values
            self.cal_data.update(e.beam, datetime.now().strftime('%H:%M:%S'), gain, rms, r, num)
            # update the results dialog if present
            if self.results_dialog:
                self.results_dialog.update_with(self.cal_data, e.beam)

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


class resultsDialog:
    """A dialog box to show completed calibration results per beam."""

    def __init__(self, parent, data: dict=None, icon=None):
        
        self.data = data
        
        self.top = tk.Toplevel(parent)
        self.top.title("Results")
        if icon:
            self.top.iconphoto(False, icon)

        tree_frame = ttk.Frame(self.top)

        # use a ttk.Treeview to show a table of the results
        self.item_ids = {}  # contains ids to rows that get added to the treeview
        self.setup_treeview(tree_frame, self.data)  # creates self.tree

        # Make scrollbars for the treeview widget
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        
        # pack the scrollbars and treeview
        vsb.pack(side="right", fill="y")
        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5)

        # create and pack the buttons
        btn_frame = ttk.Frame(self.top)
        remove = ttk.Button(btn_frame, text="Remove selected", command=self.remove_rows)
        save = ttk.Button(btn_frame, text="Save", command=self.save)
        close = ttk.Button(btn_frame, text="Close", command=self.close_dialog)
        
        close.pack(side=tk.RIGHT)
        save.pack(side=tk.RIGHT)
        remove.pack(side=tk.RIGHT)

        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_treeview(self, top, data):
        """Create the treeview columns, etc."""
        
        headings = [data.df().index.name] + list(data.df().columns)
        
        self.tree = ttk.Treeview(top, columns=headings, show='headings')
        self.tree.bind('<Button-1>', self.on_row_click)

        # colour odd and even rows
        self.tree.tag_configure('evenrow', background='white smoke')
        self.tree.tag_configure('oddrow', background='white')
        self.tree.tag_configure('active', background='orange2')
        
        for col in headings:
            self.tree.heading(col, text=col, anchor='e')
            self.tree.column(col, width=100, anchor='e')

        # Add rows (if any)
        self.update_with(data)            
                    
    def update_with(self, data, active_beam: int|None = None):
        """Update dialog's display with given calibration data."""

        for beam, row in data.df().iterrows():

            # TODO
            # This is hacky and fragile - find a better way that doesn't need to name the
            # columns
            values = [beam, 
                      row['Time'],
                      f"{row['Gain (dB)']:0.1f}",
                      f"{row['RMS (dB)']:0.1f}",
                      f"{row['Range (m)']:0.1f}",
                      row['Echoes']]
            # values = [beam] + list(row)

            if beam in self.item_ids:
                # row for this beam already exists, so update it
                self.tree.item(self.item_ids[beam], values=values)
            else:
                # new beam, so add a row
                item_id = self.tree.insert('', 'end', values=values)
                self.item_ids[beam] = item_id

        self.update_rows(active_beam)

        # keep this to use in the save and remove functionalities
        self.data = data

    def update_rows(self, active_beam: int|None):
        """Sorts calibration results rows by beam and sets background colours to look nice."""
        for beam, index in zip(sorted(self.item_ids.keys()), range(len(self.item_ids))):
            self.tree.move(self.item_ids[beam], '', index)

            rowness = 'oddrow' if index % 2 == 0 else 'evenrow'
            if active_beam and beam == active_beam:
                rowness = 'active'

            self.tree.item(self.item_ids[beam], tags=(rowness,))    

    def remove_rows(self):
        """Remove selected rows from the results table."""

        selected = self.tree.selection()  # returns a tuple of item_ids
        
        # Pick out the beam numbers of the selected rows
        to_remove = []
        for iid in selected:
            item_data = self.tree.item(iid)
            values = item_data['values']
            to_remove.append(values[0])

        if to_remove:
            for beam in to_remove:
                # remove selected rows from treeview
                self.tree.delete(self.item_ids[beam])
                # remove beam imtem from the map between beam and item ids
                self.item_ids.pop(beam)
            # remove beams from the cal_data store
            self.data.remove(to_remove)
            self.update_rows(None)

    def save(self):
        """Save the results to a file."""
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        default_filename = 'sonar_calibration_' + timestamp + '.csv'
        save_filename = fd.asksaveasfilename(title='Save as CSV', defaultextension='.csv',
                                             initialdir=PlatformDirs.user_documents_dir,
                                             initialfile=default_filename,
                                             filetypes=[('CSV', '*.csv')])
        if save_filename:
            logger.info('Saved results to %s', save_filename)
            self.data.df().sort_index().to_csv(save_filename)

    def on_row_click(self, event):
        """Implement selection and deselection."""
        # TODO - work out why it can take multiple clicks on a row to get it unselected
        item_id = self.tree.identify_row(event.y)
        if item_id and item_id in self.tree.selection():
            self.tree.selection_remove(item_id)


    def reopen(self):
        self.top.deiconify()

    def close_dialog(self):
        self.top.withdraw()
