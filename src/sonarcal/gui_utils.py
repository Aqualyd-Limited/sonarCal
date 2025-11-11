import numpy as np
from matplotlib import lines

class draggable_ring:
    """Provides a range ring on a polar plot that the user can move with the mouse."""

    def __init__(self, ax, r):
        self.ax = ax
        self.c = ax.get_figure().canvas
        self.range = r
        self.numPoints = 50  # used to draw the range circle

        self.line = lines.Line2D(np.linspace(-np.pi, np.pi, num=self.numPoints),
                                 np.ones(self.numPoints)*self.range,
                                 linewidth=2, color='k', picker=True)
        self.line.set_pickradius(5)
        self.ax.add_line(self.line)
        self.c.draw_idle()
        self.sid = self.c.mpl_connect('pick_event', self.clickonline)

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
        
        self.line_color_unfrozen = 'black'
        self.line_color_frozen = 'orange'
        
        self.ax = ax
        self.c = ax.get_figure().canvas
        self.angle = angle
        self.maxRange = maxRange
        self.labels = labels
        self.theta = theta  # the sonar-provided beam pointing angles.

        self.value = 0.0  # is updated to a true value once data is received

        self.line = lines.Line2D([self.angle, self.angle], [0, self.maxRange],
                                 linewidth=2, marker='o', markevery=[-1],
                                 color=self.line_color_unfrozen, picker=True)
        self.text = self.ax.text(self.angle, 1.2*self.maxRange, '',
                                 color=self.line_color_unfrozen,
                                 horizontalalignment='center', verticalalignment='center')
        # self.text.set_bbox({'color': 'w', 'alpha': 0.5, 'boxstyle': 'round,rounding_size=0.6'})
        self.snapAngle(self.angle)

        self.line.set_pickradius(5)
        self.ax.add_line(self.line)
        self.c.draw_idle()
        self.sid = self.c.mpl_connect('pick_event', self.clickonline)
        
        self.radial_frozen = False

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

        Snap the beam line to beam centres (make it easier to get the beam
        line on a specific beam in the sonar display)
        """
        if event.xdata is not None:
            x = float(event.xdata)
            # When the polar plot has an offset (applied setting up the plot),
            # the angles in one quadrant become negative (which we don't want).
            # This fixes that.
            if x < 0:
                x += 2*np.pi
            self.snapAngle(x)

    def snapAngle(self, x):
        """Snap the mouse position to the cente of a beam.

        Updates the beam line and beam number text.
        """
        idx = (np.abs(self.theta - x)).argmin()
        snappedAngle = self.theta[idx]
        self.line.set_data([snappedAngle, snappedAngle], [0, self.maxRange])

        # update beam number display at the end of the radial line
        self.text.set_position((snappedAngle, 1.12*self.maxRange))
        self.text.set_text(f'{self.labels[idx].decode()}')

        self.c.draw_idle()

    def releaseonclick(self, _event):
        """Stop following events once mouse button is released."""
        if not self.radial_frozen:
            self.value = self.line.get_xdata()[0]

            self.c.mpl_disconnect(self.releaser)
            self.c.mpl_disconnect(self.follower)
