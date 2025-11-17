from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from .configuration import config as cfg
import logging

logger = logging.getLogger(cfg.appName())

class configDialog:
    """A dialog box to set and change application parameters."""
    def __init__(self, parent, icon=None):
        self.top = tk.Toplevel(parent)
        self.top.title("Config")
        if icon:
            self.top.iconphoto(False, icon)

        config_frame = ttk.Frame(self.top)
        
        @dataclass
        class Param:
            label: str
            name: str
            type: str
            special: str = None

        self.params = [
            Param('', '', 'horizline'),
            Param('Sonar data directory', 'watchDir', 'str', 'filechooser'),
            Param('Expect live data', 'liveData', 'boolean'),
            Param('', '', 'horizline'),
            Param('Number of pings in plots', 'numPings', 'int'),
            Param('Echogram range [m]', 'maxRange', 'float'),
            Param('', '', 'horizline'),
            Param('Default minimum echogram Sv (dB)', 'minSv', 'float'),
            Param('Default maximum echogram Sv (dB)', 'maxSv', 'float'),
            Param('Minimum allowed Sv colour (dB)', 'sliderLowestSv', 'float'),
            Param('Maximum allowed Sv colour (dB)', 'sliderHighestSv', 'float'),
            Param('', '', 'horizline'),
            Param('TS smoothing over (pings)', 'movingAveragePoints', 'int'),
            Param('Sphere stats over (pings)', 'sphereStatsOver', 'int'),
        ]

        ttk.Label(self.top, text='Changes to these settings requires restarting the program.')\
                  .pack(side=tk.TOP, fill=tk.BOTH, expand=tk.TRUE, pady=10)

        self.vars = {}  # mapping for name to tkinter Var
        for p in self.params:
            if p.type == 'horizline':
                ttk.Separator(self.top, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)
                continue

            v = getattr(cfg, p.name)()  # get value of current config parameter
            match p.type:
                case 'int':
                    self.vars[p.name] = tk.IntVar(value=v)
                case 'float':
                    self.vars[p.name] = tk.DoubleVar(value=v)
                case 'boolean':
                    self.vars[p.name] = tk.BooleanVar(value=v)  # needs to be a tick box
                case 'str':
                    self.vars[p.name] = tk.StringVar(value=v)  # needs a callback?

            self.create_form_entry(p.label, self.vars[p.name])

        btn_frame = ttk.Frame(self.top)
        ttk.Button(btn_frame, text="Close", command=self.close_dialog).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Apply", command=self.apply).pack(side=tk.RIGHT)
        
        config_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.TRUE)
        btn_frame.pack(side=tk.TOP, fill=tk.BOTH)

    def create_form_entry(self, label, variable):
        """Create a single form entry"""
        container = ttk.Frame(self.top)
        container.pack(fill=tk.X, expand=tk.YES, pady=5)

        lbl = ttk.Label(master=container, text=label, width=35)
        lbl.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=tk.YES)

        ent = ttk.Entry(master=container, textvariable=variable, justify='right', width=15)
        ent.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=tk.YES)

    def apply(self):
        for p in self.params:
            if p.name:
                getattr(cfg, p.name)(self.vars[p.name].get())
        cfg.save_config()
        logger.info('Saved configuration')

    def close_dialog(self):
        self.top.destroy()