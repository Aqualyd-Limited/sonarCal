import tkinter as tk
from tkinter import ttk


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

