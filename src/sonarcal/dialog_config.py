from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from .configuration import config as cfg
import logging
import re

logger = logging.getLogger(cfg.appName())


class configDialog:
    """A dialog box to set and change application parameters."""
    def __init__(self, parent, icon=None, updated_cb=None):
        self.top = tk.Toplevel(parent)
        self.top.title("Config")
        self.updated_cb = updated_cb
        self.label_width = 20  # [characters]

        ttk.Style().configure('select_dir.TButton', font=('Arial', 10))

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
            vmin:float = None
            vmax:float = None


        self.params = [
            Param('', '', 'horizline'),
            Param('Sonar data directory', 'watchDir', 'str', '', 'filechooser'),
            Param('Use live data', 'liveData', 'boolean'),
            Param('Replay ping interval', 'replayPingInterval', 'float', 's', '', 0.1),
            Param('', '', 'horizline'),
            Param('Calibration sphere TS', 'sphereTS', 'float', 'dB re 1 m²'),
            Param('', '', 'horizline'),
            Param('x-axis size', 'numPings', 'int', 'pings', '', 10, 500),
            Param('Echogram range', 'maxRange', 'float', 'm', '', 1.0, 300.0),
            Param('', '', 'horizline'),
            Param('y-axis minimum on Δ plot', 'diffPlotYMin', 'float', 'dB', '', None, -1.0),
            Param('Minimum Sv colour', 'sliderLowestSv', 'float', 'dB re 1 m⁻¹'),
            Param('Maximum Sv colour', 'sliderHighestSv', 'float', 'dB re 1 m⁻¹')
        ]

        self.vars = {}  # mapping for name to tkinter Var
        for p in self.params:
            if p.type == 'horizline':
                ttk.Separator(self.top, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)
                continue
            if p.type == 'label':
                ttk.Label(self.top, text=p.label).pack(side=tk.TOP, fill=tk.BOTH,
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
                self.create_config_row(p.label, self.vars[p.name], p.type,
                                       p.unit, p.vmin, p.vmax)

        btn_frame = ttk.Frame(self.top)
        ttk.Button(btn_frame, text="Close", command=self.close_dialog).pack(side=tk.RIGHT)

        self.apply_btn = ttk.Button(btn_frame, text="Apply", command=self.apply)
        self.apply_btn.pack(side=tk.RIGHT)
        self.apply_btn.state(['disabled'])
        
        config_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.TRUE)
        btn_frame.pack(side=tk.TOP, fill=tk.BOTH)

    def create_dir_chooser_row(self, label, variable):
        """Create a directory chooser config row."""

        container = ttk.Frame(self.top)
        container.pack(fill=tk.X, expand=tk.YES, pady=5)

        subcon = ttk.Frame(container)
        lbl = ttk.Label(master=subcon, text=label, width=self.label_width)
        lbl.pack(side=tk.TOP, padx=5, fill=tk.X, expand=tk.NO)

        btn = ttk.Button(subcon, text='Select directory', style='select_dir.TButton',
                         command=lambda: _dir_chooser(variable))
        btn.pack(side=tk.TOP, padx=5, expand=tk.NO, anchor=tk.W)

        variable.trace_add('write', callback=self.update_apply_state)

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


    def create_config_row(self, label, variable, var_type, unit, vmin, vmax):
        """Create a single row in the config dialog for a variable"""
        
        container = ttk.Frame(self.top)
        container.pack(fill=tk.X, expand=tk.YES, pady=5)

        lbl = ttk.Label(master=container, text=label, width=self.label_width)
        lbl.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=tk.NO)

        match var_type:
            case 'boolean':
                entry = ttk.Checkbutton(container, variable=variable)
            case 'float':
                entry = validated_entry(master=container, textvariable=variable,
                                        justify='right', width=10,
                                        min=vmin, max=vmax, vtype=var_type)
            case 'int':
                entry = validated_entry(master=container, textvariable=variable,
                                        justify='right', width=10,
                                        min=vmin, max=vmax, vtype=var_type)
            case _:
                entry = ttk.Entry(master=container, textvariable=variable,
                                  justify='right', width=10)

        unit = ttk.Label(master=container, text=unit, width=10)
        bounds = ttk.Label(master=container, text=self.bounds_to_str(vmin, vmax))

        variable.trace_add('write', callback=self.update_apply_state)

        entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=tk.NO)
        unit.pack(side=tk.LEFT, padx=5)
        bounds.pack(side=tk.RIGHT, padx=10)


    @staticmethod
    def bounds_to_str(vmin, vmax):
        """Convert the min/max limits into a text str for use display."""
        if vmin is None and vmax is None:
            return ''
        
        vmin_str = f'{vmin} ≤' if vmin else ''
        vmax_str = f'≤ {vmax}' if vmax else ''

        return vmin_str + ' x ' + vmax_str


    def changed_values(self) -> dict:
        """Which values have changed in the dialog compared to the config object."""
        changed = {}
        for p in self.params:
            if p.name:
                # Work out which settings have been changed
                dialog_value = self.vars[p.name].get()
                cfg_value = getattr(cfg, p.name)()
                if dialog_value != cfg_value:
                    changed[p.name] = True
        return changed


    def update_apply_state(self, var, index, mode):
        """Activate the Apply button if all config values are valid and at least one has changed."""
        if self.all_valid() and self.changed_values():
            self.apply_btn.state(['!disabled'])
        else:
            self.apply_btn.state(['disabled'])


    def all_valid(self):
        """Are values in the dialog valid (only for those with vmin or vmax set)"""
        all_valid = True
        for p in self.params:
            if p.name:
                try:
                    dialog_value = self.vars[p.name].get()
                except Exception:
                    all_valid = False
                if p.vmin:
                    all_valid = all_valid & (False if p.vmin > dialog_value else True)
                if p.vmax:
                    all_valid = all_valid & (False if p.vmax < dialog_value else True)
        return all_valid


    def apply(self):
        """Apply the dialog values to the config object."""
        changed = self.changed_values()

        for name in changed:
            dialog_value = self.vars[name].get()
            # update the settings in the cfg object
            getattr(cfg, name)(dialog_value)

        cfg.save_config() 
   
        if self.updated_cb:
            # tell others that we've updated
            self.updated_cb(changed)

        self.apply_btn.state(['disabled'])


    def reopen(self):
        self.top.deiconify()


    def close_dialog(self):
        self.top.withdraw()


class validated_entry(ttk.Entry):
    """Validated ttk Entry widget for ints and floats."""

    def __init__(self, master=None, vtype=None, min=None, max=None, **kwargs):
        super().__init__(master, **kwargs)
        
        if vtype == 'float':
            self.regex = r'^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d*)?$'
            self.convert = float
        elif vtype == 'int':
            self.regex = r'[-+]?\d+'
            self.convert = int
        else:
            self.regex = r'.*'
            self.convert = str
        
        self.invalid_colour = 'red'
        style = ttk.Style()
        self.foreground_color = style.lookup(self.winfo_class(), "foreground")
            
        self.min = min
        self.max = max
        vcmd = self.register(self._validate)
        self.configure(validate='all', validatecommand=(vcmd, '%P'))


    def _validate(self, proposed_value):
        """Validate the proposed new entry value."""

        if proposed_value == '':
            self.state(['invalid'])
            return True

        if re.fullmatch(self.regex, proposed_value):
            try:
                v = self.convert(proposed_value)
            except ValueError:
                self.state(['invalid'])
                return True

            if self.min and v < self.min:
                self.config(foreground=self.invalid_colour)
                self.state(['invalid'])
            elif self.max and v > self.max:
                self.config(foreground=self.invalid_colour)
                self.state(['invalid'])
            else:
                self.config(foreground=self.foreground_color)
                self.state(['!invalid'])
        else:
            self.config(foreground=self.invalid_colour)
            self.state(['invalid'])

        return True
