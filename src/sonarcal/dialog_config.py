import tkinter as tk
from tkinter import ttk
from .configuration import config as cfg

class configDialog:
    """A dialog box to set and change application parameters."""
    def __init__(self, parent, icon=None):
        self.top = tk.Toplevel(parent)
        self.top.title("Config")
        if icon:
            self.top.iconphoto(False, icon)

        config_frame = ttk.Frame(self.top)
        
        ttk.Label(config_frame, text='Number of pings to show').grid(row=0, column=0)
        self.numPingsEntry = ttk.Entry(config_frame)
        self.numPingsEntry.grid(row=0, column=1)
        self.numPings = tk.IntVar()
        self.numPings.set(cfg.numPings())
        self.numPingsEntry['textvariable'] = self.numPings

        btn_frame = ttk.Frame(self.top)
        ttk.Button(btn_frame, text="Close", command=self.close_dialog).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Apply", command=self.apply).pack(side=tk.RIGHT)
        
        config_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.TRUE)
        btn_frame.pack(side=tk.TOP, fill=tk.BOTH)

    def apply(self):
        cfg.numPings(int(self.numPings.get()))
        
        # need a way to update the GUI for realtime apply of config instead
        # of having to restart the program
        
        cfg.save_config()

    def close_dialog(self):
        self.top.destroy()

