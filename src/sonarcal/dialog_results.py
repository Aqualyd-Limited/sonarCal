import tkinter as tk
from tkinter import ttk
from tkinter import filedialog as fd
import natsort as nt
from datetime import datetime
from .configuration import config


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
        self.tree.tag_configure('active', background=config.calibrating_colour())
        
        for col in headings:
            self.tree.heading(col, text=col, anchor='e')
            self.tree.column(col, width=125, anchor='e')

        # Add rows (if any)
        self.update_with(data)            
                    
    def update_with(self, data, active_beam_label: str = ''):
        """Update dialog's display with given calibration data."""
        
        def format(value):
            """Format floats to 1 decimal place."""
            if isinstance(value, float):
                return f'{value:0.1f}'
            return f'{value}'

        for beam_label, row in data.df().iterrows():
            values = [beam_label] + [format(v) for v in row]

            if beam_label in self.item_ids:
                # row for this beam already exists, so update it
                self.tree.item(self.item_ids[beam_label], values=values)
            else:
                # new beam, so add a row
                item_id = self.tree.insert('', 'end', values=values)
                self.item_ids[beam_label] = item_id

        # sort rows by beam_label and highlight the active beam (if one is active)
        self.update_rows(active_beam_label)

        # keep this to use in the save and remove functionalities
        self.data = data

    def update_rows(self, active_beam_label: str):
        """Sorts calibration results rows by beam and sets background colours to look nice."""

        for beam_label, index in zip(nt.natsorted(self.item_ids.keys()), range(len(self.item_ids))):
            self.tree.move(self.item_ids[beam_label], '', index)

            # Decide on the row colour
            rowness = 'oddrow' if index % 2 == 0 else 'evenrow'
            if active_beam_label and beam_label == active_beam_label:
                rowness = 'active'  # gets highlighted

            # Set the row colour in the tree widget
            self.tree.item(self.item_ids[beam_label], tags=(rowness,))    

    def remove_rows(self):
        """Remove selected rows from the results table."""

        selected = self.tree.selection()  # returns a tuple of item_ids
        
        # Get the beam labels of the selected rows
        to_remove = []
        for iid in selected:
            item_data = self.tree.item(iid)
            values = item_data['values']
            # Convert to str because the self.items_id map has str has the key (this
            # comes from the DataFrame this class has been given).
            to_remove.append(str(values[0]))

        if to_remove:
            for beam_label in to_remove:
                # remove selected rows from treeview
                self.tree.delete(self.item_ids[beam_label])
                # remove beam imtem from the map between beam and item ids
                self.item_ids.pop(beam_label)
            # remove beams from the cal_data store
            self.data.remove(to_remove)
            self.update_rows(None)

    def save(self):
        """Save the results to a file."""
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        default_filename = 'sonar_calibration_' + timestamp + '.csv'
        save_filename = fd.asksaveasfilename(title='Save as CSV', defaultextension='.csv',
                                             initialdir=config.userDocumentsDir(),
                                             initialfile=default_filename,
                                             filetypes=[('CSV', '*.csv')])
        if save_filename:
            self.data.save(save_filename)

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
