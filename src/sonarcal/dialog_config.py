from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from .configuration import config as cfg
import logging

logger = logging.getLogger(cfg.appName())

class configDialog:
    """A dialog box to set and change application parameters."""
    def __init__(self, parent, icon=None, updated_cb=None):
        self.top = tk.Toplevel(parent)
        self.top.title("Config")
        self.updated_cb = updated_cb

        if icon:
            self.top.iconphoto(False, icon)

        config_frame = ttk.Frame(self.top)
        
        @dataclass
        class Param:
            label: str
            name: str
            type: str
            unit: str = ''
            special: str = None

        self.params = [
            Param('Settings marked with * take effect with a program restart', '', 'label'),
            Param('', '', 'horizline'),
            Param('Calibration sphere TS', 'sphereTS', 'float', 'dB re 1 m²'),
            Param('* Sonar data directory', 'watchDir', 'str', '', 'filechooser'),
            Param('* Use live data (otherwise replay)', 'liveData', 'boolean'),
            Param('Replay ping interval', 'replayPingInterval', 'float', 's'),
            Param('', '', 'horizline'),
            Param('* Plot x-axis size', 'numPings', 'int', 'pings'),
            Param('* Echogram range', 'maxRange', 'float', 'm'),
            Param('', '', 'horizline'),
            Param('Difference plot y-axis minimum', 'diffPlotYMin', 'float', 'dB'),
            Param('* Default minimum echogram Sv', 'minSv', 'float', 'dB re 1 m⁻¹'),
            Param('* Default maximum echogram Sv', 'maxSv', 'float', 'dB re 1 m⁻¹'),
            Param('Minimum allowed Sv colour', 'sliderLowestSv', 'float', 'dB re 1 m⁻¹'),
            Param('Maximum allowed Sv colour', 'sliderHighestSv', 'float', 'dB re 1 m⁻¹'),
        ]

        self.vars = {}  # mapping for name to tkinter Var
        for p in self.params:
            if p.type == 'horizline':
                ttk.Separator(self.top, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)
                continue
            if p.type == 'label':
                ttk.Label(self.top, text=p.label).pack(side=tk.TOP,fill=tk.BOTH,
                                                       expand=tk.TRUE, pady=10)
                continue

            v = getattr(cfg, p.name)()  # get value of current config parameter
            match p.type:
                case 'int':
                    self.vars[p.name] = tk.IntVar(value=v)
                case 'float':
                    self.vars[p.name] = tk.DoubleVar(value=v)
                case 'boolean':
                    self.vars[p.name] = tk.BooleanVar(value=v)
                case 'str':
                    self.vars[p.name] = tk.StringVar(value=v)

            if p.special == 'filechooser':
                self.create_dir_chooser_row(p.label, self.vars[p.name])
            else:
                self.create_config_row(p.label, self.vars[p.name], p.unit)

        btn_frame = ttk.Frame(self.top)
        ttk.Button(btn_frame, text="Close", command=self.close_dialog).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Apply", command=self.apply).pack(side=tk.RIGHT)
        
        config_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.TRUE)
        btn_frame.pack(side=tk.TOP, fill=tk.BOTH)

    def create_dir_chooser_row(self, label, variable):
        """Create a directory chooser config row."""

        container = ttk.Frame(self.top)
        container.pack(fill=tk.X, expand=tk.YES, pady=5)

        lbl = ttk.Label(master=container, text=label, width=35)
        lbl.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=tk.NO)

        def _text_edit(event):
            """Keeps the config variable updated with text in the text widget."""
            event.widget.edit_modified(False)
            variable.set(event.widget.get('1.0', tk.END).rstrip())

        ent = tk.Text(container, wrap=tk.CHAR, width=35, height=4)
        ent.insert('1.0', variable.get())
        ent.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=tk.YES)
        ent.bind('<<Modified>>', _text_edit)

        def _dir_chooser(variable):
            """Uses a filedialog to get a directory."""
            d = filedialog.askdirectory(parent=container, title='Select data directory',
                                        initialdir=variable.get())
            if d:
                ent.delete('1.0', tk.END)
                ent.insert('1.0', d)
                variable.set(d)

        btn = ttk.Button(container, text='...', width=3,
                         command=lambda: _dir_chooser(variable))
        btn.pack(side=tk.LEFT)

    def create_config_row(self, label, variable, unit):
        """Create a single row in the config dialog"""
        container = ttk.Frame(self.top)
        container.pack(fill=tk.X, expand=tk.YES, pady=5)

        lbl = ttk.Label(master=container, text=label, width=35)
        lbl.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=tk.NO)

        if isinstance(variable.get(), bool):
            ent = ttk.Checkbutton(container, variable=variable)
        else:
            ent = ttk.Entry(master=container, textvariable=variable,
                            justify='right', width=15, font=('Arial 12'))
            unit = ttk.Label(master=container, text=unit, width=10)
            unit.pack(side=tk.RIGHT, padx=5)
        ent.pack(side=tk.RIGHT, padx=5, fill=tk.X, expand=tk.YES)

    def apply(self):
        for p in self.params:
            if p.name:
                getattr(cfg, p.name)(self.vars[p.name].get())

        if self.updated_cb:
            self.updated_cb()  # tell others that we've updated
        cfg.save_config()
        logger.info('Saved configuration')

    def close_dialog(self):
        self.top.destroy()