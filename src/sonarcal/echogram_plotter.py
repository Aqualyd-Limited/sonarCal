from queue import Empty
from datetime import datetime, timezone
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
# from scipy import signal
from matplotlib.widgets import RangeSlider
from .gui_utils import draggable_ring, draggable_radial
from .utils import get_adjacent_beams
import humanize
import logging
from .configuration import config

# Matplotlib for tkinter
mpl.use('TkAgg')

logger = logging.getLogger(config.appName())

class echogramPlotter:
    """Receive via a queue new ping data and use that to update the display."""

    def __init__(self, msg_queue, root):

        # This flag changes to True once self.createGUI() has run
        self.gui_created = False

        self.queue = msg_queue
        self.root = root
        self.job = None

        # All callback that is called whenever a new ping has finished drawing
        self.new_ping_cb = None

        # Various user-changable lines on the plots that could in the future
        # come from a config file.
        self.beamLine = None
        self.beamLineAngle = 0.0  # [deg]
        self.beamIdx = 0  # dummy value. Is updated once some data are received.
        self.beamLabel = ''

        self.sphere_stats_over = 5  # [pings]
        self.moving_average_pts = 10  # [pings]

        self.minTargetRange = 0.33*config.maxRange()
        self.maxTargetRange = 0.66*config.maxRange()

        self.diffPlotYlim = (config.diffPlotYMin(), 0)  # [dB]

        self.numPings = config.numPings()  # to show in the echograms
        self.maxRange = config.maxRange()  # [m] of the echograms
        self.maxSv = config.maxSv()  # [dB] max Sv to show in the echograms
        self.minSv = config.minSv()  # [dB] min Sv to show in the echograms

        self.checkQueueInterval = 200  # [ms] duration between checking the queue for new data

        self.emptySv = -999.0  # initialisation value of echogram data

        # Make the plots. It gets filled with pretty things once the first ping
        # of data is received.
        self.fig = plt.figure(figsize=(11.5, 5))
        plt.ion()


    def createGUI(self, samInt, c, sv, ts, theta, tilts, labels):
        """Create the GUI."""

        # createGUI() can be called to reinitialise the entire plotting display when
        # the data directory or live viewing setting is changed, so the old plots
        # need to be cleared.
        self.fig.clf()
        
        self.cmap = mpl.colormaps['jet']  # viridis looks nice too...
        self.cmap.set_under('w')  # and for values below self.minSv, if desired

        # number of samples to store per ping
        self.maxSamples = self.sample_from_range(self.maxRange)
        self.numBeams = sv.shape[0]

        # A copy of the beam gains from the file being read
        self.gains = None

        # Storage for the things we plot
        # Polar plot
        self.polar = np.full((self.maxSamples, self.numBeams), self.emptySv)
        # Echograms
        self.port = np.full((self.maxSamples, self.numPings), self.emptySv)
        self.main = np.full((self.maxSamples, self.numPings), self.emptySv)
        self.stbd = np.full((self.maxSamples, self.numPings), self.emptySv)
        # Amplitude of sphere
        self.amp = np.full((3, self.numPings), np.nan)
        # Range of the max amplitude within the range range on the selected beam
        self.rangeMax = None  # [m]

        # Make the plot axes and set up static things
        self.polarPlotAx = plt.subplot2grid((3, 3), (0, 0), rowspan=3, projection='polar')
        self.portEchogramAx = plt.subplot2grid((3, 3), (0, 1))
        self.mainEchogramAx = plt.subplot2grid((3, 3), (1, 1))
        self.stbdEchogramAx = plt.subplot2grid((3, 3), (2, 1))
        self.ampPlotAx = plt.subplot2grid((3, 3), (0, 2), rowspan=2)
        self.ampDiffPlotAx = plt.subplot2grid((3, 3), (2, 2))

        # plt.tight_layout(pad=1.5, w_pad=0.0, h_pad=0.0)

        # Configure the echogram axes
        self.portEchogramAx.invert_yaxis()
        self.mainEchogramAx.invert_yaxis()
        self.stbdEchogramAx.invert_yaxis()

        self.portEchogramAx.yaxis.tick_right()
        self.mainEchogramAx.yaxis.tick_right()
        self.stbdEchogramAx.yaxis.tick_right()

        self.portEchogramAx.xaxis.set_ticklabels([])
        self.mainEchogramAx.xaxis.set_ticklabels([])

        # Configure the sphere amplitude axes
        self.ampPlotAx.yaxis.tick_right()
        self.ampPlotAx.yaxis.set_label_position("right")
        self.ampPlotAx.xaxis.set_ticklabels([])
        self.ampPlotAx.grid(axis='y', linestyle=':')
        self.ampDiffPlotAx.yaxis.tick_right()
        self.ampDiffPlotAx.yaxis.set_label_position("right")
        self.ampDiffPlotAx.grid(axis='y', linestyle=':')

        self.portEchogramAx.set_title('', loc='left', color='red')
        self.mainEchogramAx.set_title(f' {self.beamLabel}', loc='left')
        self.stbdEchogramAx.set_title('', loc='left', color='green')

        # Create the lines in the plots
        # Sphere TS from 3 beams
        self.ampPlotLinePort, = self.ampPlotAx.plot(self.amp[0, :], 'r-', linewidth=1)
        self.ampPlotLineMain, = self.ampPlotAx.plot(self.amp[1, :], 'k-', linewidth=1)
        self.ampPlotLineStbd, = self.ampPlotAx.plot(self.amp[2, :], 'g-', linewidth=1)
     
        # Smoothed curves for the TS from 3 beams
        # Initialise these with a vector of nan as we calculate the actual values on
        # the fly each time a new ping is received, but we want the implicit x data
        # to be created for us.
        tmp = np.full((self.numPings), np.nan)
        self.ampPlotLinePortSmooth, = self.ampPlotAx.plot(tmp, 'r-', linewidth=2)
        self.ampPlotLineMainSmooth, = self.ampPlotAx.plot(tmp, 'k-', linewidth=2)
        self.ampPlotLineStbdSmooth, = self.ampPlotAx.plot(tmp, 'g-', linewidth=2)
        self.ampPlotAx.set_xlim(0, self.numPings)
     
        # a informative number on the TS plot
        self.diffVariability = self.ampPlotAx.text(0.05, 0.95, '', ha='left', va='top',
                                                   transform=self.ampPlotAx.transAxes)
        self.diffVariability.set_bbox({'color': 'w', 'alpha': 0.5})

        # Difference in sphere TS from the 3 beams
        self.ampDiffPortPlot, = self.ampDiffPlotAx.plot(tmp, 'r-', linewidth=1)
        self.ampDiffStbdPlot, = self.ampDiffPlotAx.plot(tmp, 'g-', linewidth=1)
        # Smoothed curves of the difference in TS
        self.ampDiffPortPlotSmooth, = self.ampDiffPlotAx.plot(tmp, 'r-', linewidth=2)
        self.ampDiffStbdPlotSmooth, = self.ampDiffPlotAx.plot(tmp, 'g-', linewidth=2)
        self.ampDiffPlotAx.set_xlim(0, self.numPings)
        self.ampDiffPlotAx.set_ylim(self.diffPlotYlim)

        # Echograms for the 3 selected beams
        ee = [0.0, self.numPings, self.maxRange, 0.0]
        self.portEchogram = self.portEchogramAx.imshow(self.port, interpolation='nearest',
                                                       aspect='auto', extent=ee, vmin=self.minSv,
                                                       vmax=self.maxSv)
        self.mainEchogram = self.mainEchogramAx.imshow(self.main, interpolation='nearest',
                                                       aspect='auto', extent=ee, vmin=self.minSv,
                                                       vmax=self.maxSv)
        self.stbdEchogram = self.stbdEchogramAx.imshow(self.stbd, interpolation='nearest',
                                                       aspect='auto', extent=ee, vmin=self.minSv,
                                                       vmax=self.maxSv)

        self.portEchogram.set_cmap(self.cmap)
        self.mainEchogram.set_cmap(self.cmap)
        self.stbdEchogram.set_cmap(self.cmap)

        # Omni echogram axes setup
        self.polarPlotAx.set_theta_offset(np.pi/2)  # to make bow direction plot upwards
        self.polarPlotAx.set_frame_on(False)
        self.polarPlotAx.xaxis.set_ticklabels([])
        self.polarPlotAx.set_rlabel_position(config.polarRangeLabelAngle())

        # Omni echogram image
        r = self.range_from_sample(np.arange(0, self.maxSamples))
        self.polarPlot = self.polarPlotAx.pcolormesh(theta, r, self.polar,
                                                     shading='auto', vmin=self.minSv,
                                                     vmax=self.maxSv)
        self.polarPlotAx.grid(axis='y', linestyle=':')

        self.polarPlot.set_cmap(self.cmap)
        self._create_polar_colourbar()

        # Range rings on the omni echogram
        self.rangeRing1 = draggable_ring(self.polarPlotAx, self.minTargetRange)
        self.rangeRing2 = draggable_ring(self.polarPlotAx, self.maxTargetRange)
        self.beamLine = draggable_radial(self.polarPlotAx, self.beamLineAngle,
                                         self.maxRange, theta, labels)

        # sets self.beamIdx and self.beamLabel from the positon of the radial line
        self.updateBeamNum(theta)  

        # Axes labels
        self.stbdEchogramAx.set_xlabel('Pings')

        self.portEchogramAx.yaxis.set_label_position('right')

        self.mainEchogramAx.yaxis.set_label_position('right')
        self.mainEchogramAx.set_ylabel('Range (m)')

        self.stbdEchogramAx.yaxis.set_label_position('right')

        self.ampDiffPlotAx.set_xlabel('Pings')
        self.ampPlotAx.set_ylabel('TS re 1 m$^{2}$ [dB]')
        self.ampDiffPlotAx.set_ylabel(r'$\Delta$ (dB)')
        self.ampPlotAx.set_title('Maximum amplitude at 0 m')

        plt.tight_layout(pad=1.5, w_pad=0.0, h_pad=0.0)
        
        # the tight_layout call causes a resize of the polar plot, so update the
        # inverse transform that beamline keeps
        self.beamLine.resized(None)
        
        # Text for the horizontal beam tilt
        self.beamTiltText = self.polarPlotAx.text(0.05, 1.0, s='',
                                                  transform=self.polarPlotAx.transAxes)

        # range slider to adjust the echogram thresholds. Do this after the tight_layout
        # call as it otherwise complains
        slider_ax = plt.axes([0.006, 0.2, 0.015, 0.6])
        lowestSv = config.sliderLowestSv()
        highestSv = config.sliderHighestSv()

        self.slider = RangeSlider(slider_ax, label="Thresholds", valmin=lowestSv, valmax=highestSv,
                                  valinit=((self.minSv, self.maxSv)),
                                  valstep=1.0,
                                  orientation='vertical', facecolor='blue')
        # self.slider.valtext.set_rotation(90)
        self.slider.valtext.set_visible(False)
        self.slider.label.set_rotation(90)
        self.slider.on_changed(self.updateEchogramThresholds)
        
        self.gui_created = True
        self.updateTiltValue(tilts.mean())

    def sample_from_range(self, r: float) -> int:
        """Calculate the sample number for a given range."""
        return int(np.ceil(2.0 * r / (self.sample_interval * self.sound_speed)))
    
    def range_from_sample(self, s: int) -> float:
        """Calculate the range for a given sample number."""
        return s * self.sample_interval * self.sound_speed/2.0

    def updateEchogramThresholds(self, val):
        """Update the image colormaps."""
        self.polarPlot.set_clim(val)
        self.portEchogram.set_clim(val)
        self.mainEchogram.set_clim(val)
        self.stbdEchogram.set_clim(val)
        
        # update the config with the new thresholds
        config.minSv(val[0])
        config.maxSv(val[1])

        # Redraw the figure to ensure it updates
        self.fig.canvas.draw_idle()

    def updateTiltValue(self, tilt: float):
        """Update the display of beam tilt on GUI.
        
        Units of tilt are radians
        """
        if self.gui_created:
            self.beamTiltText.set_text(f'Tilt: {tilt*180/np.pi:0.1f}°')

    def updatePolarAxisLabels(self):
        """Update the angle of the polar plot range axis labels."""
        if self.gui_created:
            self.polarPlotAx.set_rlabel_position(config.polarRangeLabelAngle())

    def updateDiffPlotYLim(self):
        """Update the lower limit of the difference plot y-axis."""
        if self.gui_created:
            self.ampDiffPlotAx.set_ylim((config.diffPlotYMin(), 0))

    def updateRangeSliderSettings(self):
        """Update the echogram range slider min and max values from the config."""
        if self.gui_created:
            vmin, vmax = self.slider.val
            if vmin < config.sliderLowestSv():
                self.slider.set_min(config.sliderLowestSv())
                config.minSv(config.sliderLowestSv())  # TODO - doesn't update the config dialog...
            if vmax > config.sliderHighestSv():
                self.slider.set_max(config.sliderHighestSv())
                config.maxSv(config.sliderHighestSv())  # TODO - doesn't update the config dialog...

            self.slider.valmin = config.sliderLowestSv()
            self.slider.valmax = config.sliderHighestSv()
            self.slider.ax.set_ylim(self.slider.valmin, self.slider.valmax)

        self.fig.canvas.draw_idle()

    def updateMaxRange(self):
        """Change the range of the echograms."""
        if self.maxRange == config.maxRange():
            return

        new_num_samples = self.sample_from_range(config.maxRange())

        if config.maxRange() < self.maxRange:
            # make the range shorter
            self.maxSamples = new_num_samples
            self.polar = self.polar[:self.maxSamples, :]
            self.port = self.port[:self.maxSamples, :]
            self.main = self.main[:self.maxSamples, :]
            self.stbd = self.stbd[:self.maxSamples, :]
        else:  # make the range larger
            extra_samples = new_num_samples - self.maxSamples
            self.maxSamples = new_num_samples

            self.polar = np.concatenate((self.polar,
                                np.full((extra_samples, self.numBeams), self.emptySv)), axis=0)

            extra = np.full((extra_samples, self.numPings), self.emptySv)
            self.port = np.concatenate((self.port, extra), axis=0)
            self.main = np.concatenate((self.main, extra), axis=0)
            self.stbd = np.concatenate((self.stbd, extra), axis=0)

        self.maxRange = config.maxRange()

        self.portEchogram.set_data(self.port)
        self.mainEchogram.set_data(self.main)
        self.stbdEchogram.set_data(self.stbd)

        extent = [0.0, self.numPings, self.maxRange, 0.0]
        self.portEchogram.set_extent(extent)
        self.mainEchogram.set_extent(extent)
        self.stbdEchogram.set_extent(extent)

        # The polar plot is more complicated. Matplotlib provides no way to
        # update the range and angle data for an existing pcolormesh so a new
        # pcolormesh needs to be created and setup on the polar axes. The old
        # pcolormesh also needs to be removed.
        self._new_polar_mesh()

    def _create_polar_colourbar(self):
        self.cb = plt.colorbar(self.polarPlot, ax=self.polarPlotAx, orientation='horizontal',
                          extend='both', fraction=0.05, location='bottom')
        self.cb.set_label('$S_v$ re 1 m$^{-1}$ [dB]')

    def _new_polar_mesh(self):
        """Remake the polar mesh.
        
        Matplotlib does not provide a way to update the ranges on a pcolormesh so
        we delete the old polar pcolormesh and make a new one.
        """
        self.cb.remove()  # do the colourbar too
        self.polarPlot.remove()

        # new pcolormesh
        r = self.range_from_sample(np.arange(0, self.maxSamples))
        self.polarPlot = self.polarPlotAx.pcolormesh(self.theta, r, self.polar,
                                                     shading='auto', vmin=self.minSv,
                                                     vmax=self.maxSv)
        self.polarPlotAx.set_rmax(self.maxRange)
        self.polarPlot.set_cmap(self.cmap)
        self._create_polar_colourbar()

        # update the range rings and radial line
        self.rangeRing1.new_max_range(self.maxRange)
        self.rangeRing2.new_max_range(self.maxRange)
        
        # take care that the range rings don't end up being the same
        if abs(self.rangeRing1.range - self.rangeRing2.range) < 0.5:
            r = self.rangeRing1.range
            self.rangeRing2.set_range(r-1.0)
        
        self.beamLine.new_max_range(self.maxRange)

    def updateNumPings(self):
        """Change the number of pings in the displays."""

        if self.numPings == config.numPings():
            return

        # All the lines on the plots that need adjusting
        lines = [self.ampPlotLinePort, self.ampPlotLineMain, self.ampPlotLineStbd,
                    self.ampPlotLinePortSmooth, self.ampPlotLineMainSmooth,
                    self.ampPlotLineStbdSmooth,
                    self.ampDiffPortPlot, self.ampDiffStbdPlot, 
                    self.ampDiffPortPlotSmooth, self.ampDiffStbdPlotSmooth]

        def update_plots():
            # Update echograms with new data and adjust axes limits
            extent = [0.0, self.numPings, self.maxRange, 0.0]
            for e, s in zip([self.portEchogram, self.mainEchogram, self.stbdEchogram],
                            [self.port, self.main, self.stbd]):
                e.set_data(s)
                e.set_extent(extent)

            self.ampPlotAx.set_xlim(0, self.numPings)
            self.ampDiffPlotAx.set_xlim((0, self.numPings))

        if config.numPings() < self.numPings:
            self.numPings = config.numPings()

            # Reduce storage variables
            self.port = self.port[:, -self.numPings:]
            self.main = self.main[:, -self.numPings:]
            self.stbd = self.stbd[:, -self.numPings:]
            self.amp = self.amp[:, -self.numPings:]

            # Shorten all the line plots
            for line in lines:
                y = line.get_ydata()
                line.set_data(np.arange(self.numPings), y[-self.numPings:])
        else:  # increase size
            extra_pings = config.numPings() - self.numPings
            self.numPings = config.numPings()

            # Increase storage variables
            extra = np.full((self.maxSamples, extra_pings), self.emptySv)
            self.port = np.concatenate((extra, self.port), axis=1)
            self.main = np.concatenate((extra, self.main), axis=1)
            self.stbd = np.concatenate((extra, self.stbd), axis=1)
            self.amp = np.concatenate((np.full((3, extra_pings), np.nan), self.amp), axis=1)
                       
            # Lengthen all the line plots
            for line in lines:
                y = np.concatenate((np.full(extra_pings, np.nan), line.get_ydata()))
                line.set_data(np.arange(self.numPings), y)

        update_plots()

    def set_ping_callback(self, cb):
        """Set the callback that is called after each new ping is displayed."""
        self.new_ping_cb = cb

    @staticmethod
    def sort_beams(sv, ts, theta, tilts, gains, labels):
        """Sorts everything by the values in theta."""

        sort_i = np.argsort(theta)

        return sv[sort_i], ts[sort_i], theta[sort_i], tilts[sort_i], gains[sort_i], labels[sort_i]

    def newPing(self, label):
        """Receive messages from the queue, decodes them and updates the echogram."""
        while not self.queue.empty():
            try:
                message = self.queue.get(block=False)
            except Empty:
                logger.info('No new data in received message.')
            else:
                try:
                    (first, pingTime, samInt, c, sv, ts, theta, tilts, gains, labels) = message
                    # first - bool - True when the first ping from a directory of files
                    # pingTime - datetime
                    # samInt - sample interval: float [m]
                    # c - sound speed: float [m/s]
                    # sv - Sv: 2D numpy float [dB]
                    # ts - TS: 2D numpy float [dB]
                    # the rest are all 1d numpy vectors
                    # theta - float [rad]
                    # tilts - float [rad]
                    # gains - float [dB]
                    # labels - str 

                    # sort on theta - needed to avoid a warning from the polar plot
                    (sv, ts, theta, tilts, gains, labels) =\
                        self.sort_beams(sv, ts, theta, tilts, gains, labels)

                    self.sound_speed = c
                    self.sample_interval = samInt
                    self.theta = theta

                    if first:
                        self.createGUI(samInt, c, sv, ts, theta, tilts, labels)

                    # Update our copy of the beam gains
                    self.gains = gains

                    # Update the plots with the data in the new ping
                    timeBehind = datetime.now(timezone.utc) - pingTime
                    milliseconds = pingTime.microsecond / 1000
                    label.config(text=f'Ping at {pingTime:%Y-%m-%d %H:%M:%S}.' +
                                 f'{milliseconds:03.0f} '
                                 f'({humanize.precisedelta(timeBehind)} ago)')
                    logger.debug('Displaying ping from %s.', pingTime)

                    self.minTargetRange = min(self.rangeRing1.range, self.rangeRing2.range)
                    self.maxTargetRange = max(self.rangeRing1.range, self.rangeRing2.range)

                    # print('Range rings: {}, {}'.format(self.minTargetRange, self.maxTargetRange))
                        
                    minSample = self.sample_from_range(self.minTargetRange)
                    maxSample = self.sample_from_range(self.maxTargetRange)

                    # Various things select a range of samples, so ensure that they
                    # always get something
                    if minSample == maxSample:
                        minSample -= 1

                    self.updateBeamNum(theta)  # sets self.beam from self.beamLineAngle

                    # work out the beam indices
                    # beamPort, beamStbd = get_adjacent_beamsV1(self.beamIdx, self.numBeams)
                    beamPort, beamStbd = get_adjacent_beams(self.beamIdx, self.numBeams)

                    # Find the max ts between the min and max ranges set by the UI
                    # and store for plotting
                    self.amp = np.roll(self.amp, -1, 1)
                    if minSample >= ts.shape[1]:
                        # we're beyond the range of the data so return such...
                        self.amp[0, -1] = np.nan
                        self.amp[1, -1] = np.nan
                        self.amp[2, -1] = np.nan
                        self.rangeMax = np.nan
                    else:
                        self.amp[0, -1] = np.max(ts[beamPort][minSample:maxSample])
                        max_i = np.argmax(ts[self.beamIdx][minSample:maxSample])
                        self.amp[1, -1] = ts[self.beamIdx][minSample+max_i]
                        self.rangeMax = self.range_from_sample(minSample+max_i)
                        self.amp[2, -1] = np.max(ts[beamStbd][minSample:maxSample])

                    # Store the amplitude for the 3 beams for the echograms
                    self.port = self.updateEchogramData(self.port, sv[beamPort])
                    self.main = self.updateEchogramData(self.main, sv[self.beamIdx])
                    self.stbd = self.updateEchogramData(self.stbd, sv[beamStbd])

                    # Update the plots
                    # Sphere TS from 3 beams
                    self.ampPlotLinePort.set_ydata(self.amp[0, :])
                    self.ampPlotLineMain.set_ydata(self.amp[1, :])
                    self.ampPlotLineStbd.set_ydata(self.amp[2, :])
                    # and smoothed plots
                    coeff = np.ones(self.moving_average_pts)/self.moving_average_pts
                    # and measure of ping-to-ping variability
                    variability = np.std(self.amp[1, -self.sphere_stats_over: -1])
                    if not np.isnan(variability):
                        self.diffVariability.set_text(rf'$\sigma$ = {variability:.1f} dB')

                    from scipy import signal  # deferred to save startup time
                    s0 = signal.filtfilt(coeff, 1, self.amp[0, :])
                    s1 = signal.filtfilt(coeff, 1, self.amp[1, :])
                    s2 = signal.filtfilt(coeff, 1, self.amp[2, :])
                    self.ampPlotLinePortSmooth.set_ydata(s0)
                    self.ampPlotLineMainSmooth.set_ydata(s1)
                    self.ampPlotLineStbdSmooth.set_ydata(s2)

                    self.ampPlotAx.set_title(f'Maximum amplitude at {self.rangeMax:.1f} m')
                    self.ampPlotAx.relim()
                    self.ampPlotAx.autoscale_view()

                    # Difference in sphere TS from 3 beams
                    diffPort = self.amp[0, :] - self.amp[1, :]
                    diffStbd = self.amp[2, :] - self.amp[1, :]
                    self.ampDiffPortPlot.set_ydata(diffPort)
                    self.ampDiffStbdPlot.set_ydata(diffStbd)
                    # and the smoothed
                    smPort = signal.filtfilt(coeff, 1, diffPort)
                    smStbd = signal.filtfilt(coeff, 1, diffStbd)
                    self.ampDiffPortPlotSmooth.set_ydata(smPort)
                    self.ampDiffStbdPlotSmooth.set_ydata(smStbd)

                    self.ampDiffPlotAx.relim()
                    self.ampDiffPlotAx.autoscale_view(scaley=False)

                    # Beam echograms
                    self.portEchogram.set_data(self.port)
                    self.mainEchogram.set_data(self.main)
                    self.stbdEchogram.set_data(self.stbd)

                    self.portEchogramAx.set_title(f'Beam {labels[beamPort]}', loc='left')
                    self.mainEchogramAx.set_title(f'Beam {labels[self.beamIdx]}', loc='left')
                    self.stbdEchogramAx.set_title(f'Beam {labels[beamStbd]}', loc='left')

                    # Polar plot
                    for i, b in enumerate(sv):
                        if b.shape[0] > self.maxSamples:
                            self.polar[:, i] = b[0: self.maxSamples]
                        else:
                            samples = b.shape[0]
                            self.polar[:, i] =\
                                np.concatenate((b, np.full(self.maxSamples-samples, self.emptySv)),
                                               axis=0)

                    self.polarPlot.set_array(self.polar.ravel())

                    self.updateTiltValue(tilts[self.beamIdx])

                    # If the range rings are too close together it becomes impossible to move 
                    # them separately, so check and move one if that happens
                    r1 = self.rangeRing1.range
                    r2 = self.rangeRing2.range
                    minimum_range_difference = 0.5  # [m]
                    range_shift = self.maxRange*0.1  # [m]

                    if abs(r1 - r2) <= minimum_range_difference:
                        # decrease the range of the inner one
                        if r1 <= r2:
                            self.rangeRing1.set_range(r1 - range_shift)
                        else:
                            self.rangeRing2.set_range(r2 - range_shift)

                    if self.new_ping_cb:
                        self.new_ping_cb()

                except Exception:  # if anything goes wrong, just ignore it...
                    logger.exception('Exception when processing and displaying echo data')
                    logger.info('Ignoring the exception and waiting for next ping.')

        self.job = self.root.after(self.checkQueueInterval, self.newPing, label)

    def updateEchogramData(self, data, pingData):
        """Shift the ping data to the left and add in the new ping data."""
        data = np.roll(data, -1, 1)
        if pingData.shape[0] > self.maxSamples:
            data[:, -1] = pingData[0:self.maxSamples]
        else:
            samples = pingData.shape[0]
            data[:, -1] = np.concatenate((pingData[:],
                                          np.full(self.maxSamples-samples, self.emptySv)), axis=0)
        return data

    def updateBeamNum(self, theta):
        """Get the beam number from the beam line angle and the latest theta."""
        self.beamIdx = self.beamLine.selected_beam_idx
        self.beamLabel = self.beamLine.selected_beam_label
