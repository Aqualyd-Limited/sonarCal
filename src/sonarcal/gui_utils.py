import numpy as np
from math import pi
# from matplotlib import lines
from .configuration import config


class draggable_ring:
    """Provides a range ring on a polar plot that the user can move with the mouse."""

    def __init__(self, ax, r):
        # deferred imports
        from matplotlib import lines

        self.ax = ax
        self.c = ax.get_figure().canvas
        self.range = r
        self.numPoints = 50  # used to draw the range circle

        self.line = lines.Line2D(np.linspace(-pi, pi, num=self.numPoints),
                                 np.ones(self.numPoints)*self.range,
                                 linewidth=2, color='k', picker=True)
        self.line.set_pickradius(5)
        self.ax.add_line(self.line)
        self.c.draw_idle()
        self.c.mpl_connect('pick_event', self.clickonline)

    def set_range(self, r):
        """Set the range ring radius."""
        self.range = r
        self.line.set_ydata(np.full(self.numPoints, self.range))

    def new_max_range(self, r):
        """Change the range of the ring."""
        if r < self.range:
            self.range = r
            self.line.set_ydata(np.full(self.numPoints, self.range))

    def clickonline(self, event):
        """Capture clicks on lines."""
        if event.artist == self.line:
            self.follower = self.c.mpl_connect("motion_notify_event", self.followmouse)
            self.releaser = self.c.mpl_connect("button_release_event", self.releaseonclick)

    def followmouse(self, event):
        """Act on mouse movement."""
        if event.ydata is not None:
            self.line.set_ydata(np.ones(self.numPoints)*float(event.ydata))
            self.c.draw_idle()

    def releaseonclick(self, _event):
        """Stop following events once mouse button is released."""
        self.range = self.line.get_ydata()[0]

        self.c.mpl_disconnect(self.releaser)
        self.c.mpl_disconnect(self.follower)


class draggable_radial:
    """Provide a radial line on a polar plot that the user can move with the mouse."""

    def __init__(self, ax, angle: float, maxRange: float, theta: float, labels):
        from matplotlib import lines  # deferred to save import time

        # Text range is this factor times the plot max range
        self.text_range_factor = 1.2

        self.line_color_unfrozen = 'black'
        self.line_color_frozen = config.calibrating_colour()
        
        self.ax = ax
        self.inv = self.ax.transData.inverted()  # used in followmouse()
        self.ax.set_zorder(2) # so that it is on top of the rangeslider

        self.c = ax.get_figure().canvas
        # self.angle = angle
        self.maxRange = maxRange
        self.labels = labels
        self.theta = theta  # the sonar-provided beam pointing angles.

        #self.value = 0.0  # is updated to a true value once data is received
        self.selected_beam_idx = 0

        self.line = lines.Line2D([angle, angle], [0, self.maxRange],
                                 linewidth=2, marker='o', markevery=[-1],
                                 color=self.line_color_unfrozen, picker=True,
                                 clip_on=False)
        self.text = self.ax.text(angle, self.text_range_factor*self.maxRange, '',
                                 color=self.line_color_unfrozen,
                                 bbox={'boxstyle':'square,pad=0.0', 'fc': 'white', 'ec': 'none'},
                                 horizontalalignment='center', verticalalignment='center')
        # self.text.set_bbox({'color': 'w', 'alpha': 0.5, 'boxstyle': 'round,rounding_size=0.6'})
        self.snapAngle(angle)

        self.line.set_pickradius(5)
        self.ax.add_line(self.line)
        self.c.draw_idle()
        self.c.mpl_connect('pick_event', self.clickonline)
        self.c.mpl_connect('resize_event', self.resized)
        
        self.radial_frozen = False

    def resized(self, event):
        """Update the inverse polar plot transform when the plot is resized."""
        self.inv = self.ax.transData.inverted()

    def new_max_range(self, r):
        """Adjust the line and text to the given max range."""
        self.maxRange = r
        self.line.set_ydata([0, self.maxRange])
        # and move the text to match
        angle, _ = self.text.get_position()
        self.text.set_position((angle, self.text_range_factor*self.maxRange))

    def frozen(self):
        return self.radial_frozen

    def freeze(self, state: bool):
        self.radial_frozen = state

        if self.radial_frozen:
            self.line.set_color(self.line_color_frozen)
            self.text.set_color(self.line_color_frozen)
        else:
            self.line.set_color(self.line_color_unfrozen)
            self.text.set_color(self.line_color_unfrozen)

    def clickonline(self, event):
        """Capture clicks on lines."""
        if not self.radial_frozen and event.artist == self.line:
            self.follower = self.c.mpl_connect("motion_notify_event", self.followmouse)
            self.releaser = self.c.mpl_connect("button_release_event", self.releaseonclick)

    def followmouse(self, event):
        """Beam line follower.

        Snap the beam line to beam centres (makes it easier to get the beam
        line on a specific beam in the sonar display)
        """

        # Could just use event.xdata here, but that doesn't return values when the motion notify
        # event is outside of the axes that the radial line is in. So we do the conversion
        # between mouse coordinates and axes coordinates ourselves, which works over the 
        # entire computer screen.

        if event.x and event.y:  # avoid None's
            x, _ = self.inv.transform((event.x, event.y))
            # The matplotlib inverse transform gives angles from -90 to 270 (but in radians) 
            # with increasing values in an anticlockwise direction.
            # Convert the 180 to 270 to be -90 to -180 (in radians).
            if x > np.pi:
                x -= 2*np.pi

            self.snapAngle(x)

    def snapAngle(self, x: float):
        """Snap the mouse position to the cente of a beam.

        Updates the beam line and beam number text.
        """
        idx = (np.abs(self.theta - x)).argmin()

        self.selected_beam_idx = idx
        self.selected_beam_label = self.labels[idx]

        snappedAngle = self.theta[idx]
        self.line.set_data([snappedAngle, snappedAngle], [0, self.maxRange])

        # update beam number display at the end of the radial line
        self.text.set_position((snappedAngle, 1.15*self.maxRange))
        self.text.set_text(f'{self.labels[idx]}')

        self.c.draw_idle()

    def releaseonclick(self, _event):
        """Stop following events once mouse button is released."""
        if not self.radial_frozen:
            self.value = self.line.get_xdata()[0]

            self.c.mpl_disconnect(self.releaser)
            self.c.mpl_disconnect(self.follower)
