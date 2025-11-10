
import webbrowser
import logging
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import ttk
from .utils import window_closed, app_name
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

logger = logging.getLogger(app_name)

class calibrationGUI:
    """Provides the main GUI container and misc labels/buttons."""

    def __init__(self, echogram, title='TITLE', help_uri=None):
        self.echogram = echogram
        self.help_uri = help_uri

        # The GUI window
        self.echogram.root.title(title)
        
        # The toolbar and window icon/logo
        self.tk_icon = ImageTk.PhotoImage(Image.open(r'.\assets\logo.png'))  # TODO
        self.echogram.root.iconphoto(True, self.tk_icon)

        # Put the matplotlib plots into the GUI window.
        canvas = FigureCanvasTkAgg(self.echogram.fig, master=self.echogram.root)
        canvas.get_tk_widget().pack(side='top', fill='both', expand=True)

        # Styles
        s = ttk.Style()
        s.configure('TButton', font=('Arial', 16))
        s.configure('TLabel', font=('Arial', 12))
        s.configure('TCheckbutton', font=('Arial', 16))

        # A label to show the last received message time
        self.label = ttk.Label(self.echogram.root)
        self.label.pack(side=tk.TOP, fill=tk.BOTH)
        self.label.config(text='Waiting for data...', width=100, anchor=tk.W)

        ttk.Separator(self.echogram.root, orient='horizontal').pack(fill='x', padx=10, pady=5)

        # Buttons for help, on-axis toggle, config dialog, and close
        self.onaxis_value = tk.BooleanVar(value=False)

        frame = ttk.Frame(self.echogram.root)
        gains = ttk.Button(frame, text='Gains', command=self.gains)
        config = ttk.Button(frame, text='Config', command=self.config)
        onaxis = ttk.Checkbutton(frame, text='on-axis', variable=self.onaxis_value)
        help = ttk.Button(frame, text='Help', command=self.help)
        close = ttk.Button(frame, text='Close', command=self.close)

        onaxis.pack(side=tk.LEFT)
        close.pack(side=tk.RIGHT)
        help.pack(side=tk.RIGHT)
        config.pack(side=tk.RIGHT)
        gains.pack(side=tk.RIGHT)

        frame.pack(side=tk.TOP, fill=tk.BOTH)

        # Start listening for sonar data
        self.echogram.newPing(self.status_label())

    def job(self):
        return self.echogram.job

    def root(self):
        return self.echogram.root

    def close(self):
        window_closed(self.echogram.root, self.echogram.job)

    def gains(self):
        gainDialog(self.echogram.root)

    def help(self):
        if not webbrowser.open(self.help_uri, new=2):
            logging.warning('Failed to start a webbrowser to show the help documentation')
        
    def config(self):
        configDialog(self.echogram.root)

    def status_label(self):
        return self.label


class configDialog:
    def __init__(self, parent):
        self.top = tk.Toplevel(parent)
        self.top.title("Config")

        ttk.Label(self.top, text="Configs").pack(padx=20, pady=10)
        ttk.Button(self.top, text="Close", command=self.close_dialog).pack(pady=5)
        ttk.Button(self.top, text="Apply", command=self.apply).pack(pady=5)

    def apply(self):
        pass

    def close_dialog(self):
        self.top.destroy()


class gainDialog:
    def __init__(self, parent):
        self.top = tk.Toplevel(parent)
        self.top.title("Gains")

        ttk.Label(self.top, text="Table of gain value done so far").pack(padx=20, pady=10)
        ttk.Button(self.top, text="Close", command=self.close_dialog).pack(pady=5)

    def close_dialog(self):
        self.top.destroy()
