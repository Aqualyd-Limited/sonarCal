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
        self.label_width = 20  # [characters]
        # for config values that need a program restart to take effect
        self.label_colour_restart = 'orange red'

        # Widget styles
        ttk.Style().configure('needs_restart.TLabel', foreground=self.label_colour_restart)
        ttk.Style().configure('select_dir.TButton', font=('Arial', 10))

        if icon:
            self.top.iconphoto(False, icon)

        config_frame = ttk.Frame(self.top)
        
        @dataclass
        class Param:
            needs_restart: bool
            label: str
            name: str
            type: str
            unit: str = ''
            special: str = None

        self.params = [
            Param(True, 'Coloured settings apply when the program restarts', '', 'label'),
            Param(False, '', '', 'horizline'),
            Param(True, 'Sonar data directory', 'watchDir', 'str', '', 'filechooser'),
            Param(True, 'Use live data', 'liveData', 'boolean'),
            Param(False, 'Replay ping interval', 'replayPingInterval', 'float', 's'),
            Param(False, '', '', 'horizline'),
            Param(False, 'Calibration sphere TS', 'sphereTS', 'float', 'dB re 1 m²'),
            Param(False, '', '', 'horizline'),
            Param(False, 'X-axis size', 'numPings', 'int', 'pings'),
            Param(False, 'Echogram range', 'maxRange', 'float', 'm'),
            Param(False, '', '', 'horizline'),
            Param(False, 'Y-axis minimum on Δ plot', 'diffPlotYMin', 'float', 'dB'),
            Param(False, 'Minimum Sv colour', 'sliderLowestSv', 'float', 'dB re 1 m⁻¹'),
            Param(False, 'Maximum Sv colour', 'sliderHighestSv', 'float', 'dB re 1 m⁻¹'),
        ]

        self.vars = {}  # mapping for name to tkinter Var
        for p in self.params:
            if p.type == 'horizline':
                ttk.Separator(self.top, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)
                continue
            if p.type == 'label':
                s = 'needs_restart.TLabel' if p.needs_restart else  ''
                ttk.Label(self.top, text=p.label, style=s).\
                    pack(side=tk.TOP,fill=tk.BOTH, expand=tk.TRUE, pady=10)
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
                self.create_dir_chooser_row(p.needs_restart, p.label, self.vars[p.name])
            else:
                self.create_config_row(p.needs_restart, p.label, self.vars[p.name], p.unit)

        btn_frame = ttk.Frame(self.top)
        ttk.Button(btn_frame, text="Close", command=self.close_dialog).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Apply", command=self.apply).pack(side=tk.RIGHT)
        
        config_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.TRUE)
        btn_frame.pack(side=tk.TOP, fill=tk.BOTH)

    def create_dir_chooser_row(self, needs_restart, label, variable):
        """Create a directory chooser config row."""

        container = ttk.Frame(self.top)
        container.pack(fill=tk.X, expand=tk.YES, pady=5)

        subcon = ttk.Frame(container)
        lbl = ttk.Label(master=subcon, text=label, width=self.label_width,
                        style='needs_restart.TLabel' if needs_restart else  '')
        lbl.pack(side=tk.TOP, padx=5, fill=tk.X, expand=tk.NO)

        btn = ttk.Button(subcon, text='Select directory', style='select_dir.TButton',
                         command=lambda: _dir_chooser(variable))
        btn.pack(side=tk.TOP, padx=5, expand=tk.NO, anchor=tk.W)

        subcon.pack(side=tk.LEFT)
        
        def _text_edit(event):
            """Keeps the config variable updated with text in the text widget."""
            event.widget.edit_modified(False)
            variable.set(event.widget.get('1.0', tk.END).rstrip())

        ent = tk.Text(container, wrap=tk.CHAR, width=35, height=4)
        ent.insert('1.0', variable.get())
        ent.pack(side=tk.TOP, padx=5, fill=tk.X, expand=tk.NO)
        ent.bind('<<Modified>>', _text_edit)
        ent.config(state=tk.DISABLED)



        def _dir_chooser(variable):
            """Uses a filedialog to get a directory."""
            d = filedialog.askdirectory(parent=container, title='Select data directory',
                                        initialdir=variable.get())
            if d:
                ent.config(state=tk.NORMAL)  # allows us to change the contents
                ent.delete('1.0', tk.END)
                ent.insert('1.0', d)
                variable.set(d)
                ent.config(state=tk.DISABLED)


    def create_config_row(self, needs_restart, label, variable, unit):
        """Create a single row in the config dialog"""
        
        container = ttk.Frame(self.top)
        container.pack(fill=tk.X, expand=tk.YES, pady=5)

        lbl = ttk.Label(master=container, text=label, width=self.label_width,
                        style='needs_restart.TLabel' if needs_restart else  '')
        lbl.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=tk.NO)

        if isinstance(variable.get(), bool):
            ent = ttk.Checkbutton(container, variable=variable)
            ent.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=tk.NO)
        else:
            ent = ttk.Entry(master=container, textvariable=variable,
                            justify='right', width=10)
            unit = ttk.Label(master=container, text=unit, width=10)

            ent.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=tk.NO)
            unit.pack(side=tk.LEFT, padx=5)


    def apply(self):
        for p in self.params:
            if p.name:
                getattr(cfg, p.name)(self.vars[p.name].get())

        if self.updated_cb:
            self.updated_cb()  # tell others that we've updated
        cfg.save_config()

    def close_dialog(self):
        self.top.destroy()