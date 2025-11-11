import traceback
from queue import Empty
from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
from scipy import signal
from matplotlib.widgets import RangeSlider
from .utils import app_name
from .gui_utils import draggable_ring, draggable_radial
import humanize
import logging

# Matplotlib for tkinter
mpl.use('TkAgg')

logger = logging.getLogger(app_name)

class echogramPlotter:
    """Receive via a queue new ping data and use that to update the display."""

    def __init__(self, numPings, maxRange, maxSv, minSv, msg_queue, root):
        self.queue = msg_queue
        self.root = root
        self.job = None

        # All callback that is called whenever a new ping has finished drawing
        self.new_ping_cb = None

        # Various user-changable lines on the plots that could in the future
        # come from a config file.
        self.beamLineAngle = 0.0  # [deg]
        self.beam = 0  # dummy value. Is updated once some data are received.

        self.minTargetRange = 0.33*maxRange
        self.maxTargetRange = 0.66*maxRange

        self.varNum = 5  # number of sphere values to use for the ping-to-ping variability

        self.diffPlotXlim = (-3, 0)  # [dB]

        self.numPings = numPings  # to show in the echograms
        self.maxRange = maxRange  # [m] of the echograms
        self.maxSv = maxSv  # [dB] max Sv to show in the echograms
        self.minSv = minSv  # [dB] min Sv to show in the echograms

        self.checkQueueInterval = 200  # [ms] duration between checking the queue for new data

        self.movingAveragePoints = 10  # number of points for moving average for smoothed plots

        self.emptySv = -999.0  # initialisation value of echogram data

        # Make the plots. It gets filled with pretty things once the first ping
        # of data is received.
        self.fig = plt.figure(figsize=(11.5, 5))
        plt.ion()

        self.firstPing = True

    def createGUI(self, samInt, c, backscatter, theta, labels):
        """Create the GUI."""
        cmap = mpl.colormaps['jet']  # viridis looks nice too...
        cmap.set_under('w')  # and for values below self.minSv, if desired

        # the max extend of the threshold range slider
        lowestSv = -100
        highestSv = 10

        # number of samples to store per ping
        self.maxSamples = int(np.ceil(self.maxRange / (samInt*c/2.0)))
        self.numBeams = backscatter.shape[0]

        # Storage for the things we plot
        # Polar plot
        self.polar = np.ones((self.maxSamples, self.numBeams), dtype=float) * self.emptySv
        # Echograms
        self.port = np.ones((self.maxSamples, self.numPings), dtype=float) * self.emptySv
        self.main = np.ones((self.maxSamples, self.numPings), dtype=float) * self.emptySv
        self.stbd = np.ones((self.maxSamples, self.numPings), dtype=float) * self.emptySv
        # Amplitude of sphere
        self.amp = np.ones((3, self.numPings), dtype=float) * np.nan
        self.ampSmooth = np.ones((3, self.numPings), dtype=float) * np.nan
        # Range of the max amplitude within the range range on the selected beam
        self.rangeMax = None  # [m]

        # Differences in sphere amplitudes, smoothed version
        self.ampDiffPort = np.ones((self.numPings), dtype=float) * np.nan
        self.ampDiffStbd = np.ones((self.numPings), dtype=float) * np.nan
        self.ampDiffPortSmooth = np.ones((self.numPings), dtype=float) * np.nan
        self.ampDiffStbdSmooth = np.ones((self.numPings), dtype=float) * np.nan

        # Make the plot axes and set up static things
        self.polarPlotAx = plt.subplot2grid((3, 3), (0, 0), rowspan=3, projection='polar')
        self.portEchogramAx = plt.subplot2grid((3, 3), (0, 1))
        self.mainEchogramAx = plt.subplot2grid((3, 3), (1, 1))
        self.stbdEchogramAx = plt.subplot2grid((3, 3), (2, 1))
        self.ampPlotAx = plt.subplot2grid((3, 3), (0, 2), rowspan=2)
        self.ampDiffPlotAx = plt.subplot2grid((3, 3), (2, 2))

        plt.tight_layout(pad=4, w_pad=0.05, h_pad=0.05)

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

        self.portEchogramAx.set_title('Port', loc='left')
        self.mainEchogramAx.set_title(f'Beam {self.beam}', loc='left')
        self.stbdEchogramAx.set_title('Starboard', loc='left')

        # Create the lines in the plots
        # Sphere TS from 3 beams
        self.ampPlotLinePort, = self.ampPlotAx.plot(self.amp[0, :], 'r-', linewidth=1)
        self.ampPlotLineMain, = self.ampPlotAx.plot(self.amp[1, :], 'k-', linewidth=1)
        self.ampPlotLineStbd, = self.ampPlotAx.plot(self.amp[2, :], 'g-', linewidth=1)
     
        # Smoothed curves for the TS from 3 beams
        self.ampPlotLinePortSmooth, = self.ampPlotAx.plot(self.ampSmooth[0, :], 'r-', linewidth=2)
        self.ampPlotLineMainSmooth, = self.ampPlotAx.plot(self.ampSmooth[1, :], 'k-', linewidth=2)
        self.ampPlotLineStbdSmooth, = self.ampPlotAx.plot(self.ampSmooth[2, :], 'g-', linewidth=2)
        self.ampPlotAx.set_xlim(0, self.numPings)
     
        # a informative number on the TS plot
        self.diffVariability = self.ampPlotAx.text(0.05, 0.95, '', ha='left', va='top',
                                                   transform=self.ampPlotAx.transAxes)
        self.diffVariability.set_bbox({'color': 'w', 'alpha': 0.5})

        # Difference in sphere TS from the 3 beams
        self.ampDiffPortPlot, = self.ampDiffPlotAx.plot(self.ampDiffPort, 'r-', linewidth=1)
        self.ampDiffStbdPlot, = self.ampDiffPlotAx.plot(self.ampDiffStbd, 'g-', linewidth=1)
        # Smoothed curves of the difference in TS
        self.ampDiffPortPlotSmooth, = self.ampDiffPlotAx.plot(self.ampDiffPortSmooth, 'r-',
                                                              linewidth=2)
        self.ampDiffStbdPlotSmooth, = self.ampDiffPlotAx.plot(self.ampDiffStbdSmooth, 'g-',
                                                              linewidth=2)
        self.ampDiffPlotAx.set_xlim(0, self.numPings)
        self.ampDiffPlotAx.set_ylim(self.diffPlotXlim)

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

        self.portEchogram.set_cmap(cmap)
        self.mainEchogram.set_cmap(cmap)
        self.stbdEchogram.set_cmap(cmap)

        # Omni echogram axes setup
        self.polarPlotAx.set_theta_offset(np.pi/2)  # to make bow direction plot upwards
        self.polarPlotAx.set_frame_on(False)
        self.polarPlotAx.xaxis.set_ticklabels([])

        # Omni echogram image
        r = np.arange(0, self.maxSamples)*samInt*c/2.0
        self.polarPlot = self.polarPlotAx.pcolormesh(theta, r, self.polar,
                                                     shading='auto', vmin=self.minSv,
                                                     vmax=self.maxSv)
        self.polarPlotAx.grid(axis='y', linestyle=':')

        self.polarPlot.set_cmap(cmap)

        # Colorbar for the omni echogram
        cb = plt.colorbar(self.polarPlot, ax=self.polarPlotAx, orientation='horizontal',
                          extend='both', fraction=0.05, location='bottom')
        cb.set_label('$S_v$ re 1 m$^{-1}$ [dB]')

        # range slider to adjust the echogram thresholds

        slider_ax = plt.axes([0.028, 0.20, 0.015, 0.65])
        self.slider = RangeSlider(slider_ax, "Thresholds", lowestSv, highestSv,
                                  valstep=np.arange(lowestSv, highestSv+1, 1),
                                  orientation='vertical', facecolor='blue')
        # using valinit in the constructor fails due to a bug, so use this workaround
        self.slider.set_val((self.minSv, self.maxSv))
        self.slider.on_changed(self.updateEchogramThresholds)

        # Range rings on the omni echogram
        self.rangeRing1 = draggable_ring(self.polarPlotAx, self.minTargetRange)
        self.rangeRing2 = draggable_ring(self.polarPlotAx, self.maxTargetRange)
        self.beamLine = draggable_radial(self.polarPlotAx, self.beamLineAngle,
                                         self.maxRange, theta, labels)

        self.updateBeamNum(theta)  # sets self.beam from the positon of the radial line

        # Axes labels
        self.stbdEchogramAx.set_xlabel('Pings')

        self.portEchogramAx.yaxis.set_label_position('right')

        self.mainEchogramAx.yaxis.set_label_position('right')
        self.mainEchogramAx.set_ylabel('Range (m)')

        self.stbdEchogramAx.yaxis.set_label_position('right')

        self.ampDiffPlotAx.set_xlabel('Pings')
        self.ampPlotAx.set_ylabel('$S_v$ re 1 m$^{-1}$ [dB]')
        self.ampDiffPlotAx.set_ylabel(r'$\Delta$ (dB)')
        self.ampPlotAx.set_title('Maximum amplitude at 0 m')

    def updateEchogramThresholds(self, val):
        """Update the image colormaps."""
        self.polarPlot.set_clim(val)
        self.portEchogram.set_clim(val)
        self.mainEchogram.set_clim(val)
        self.stbdEchogram.set_clim(val)

        # Redraw the figure to ensure it updates
        self.fig.canvas.draw_idle()

    def set_ping_callback(self, cb):
        """Set the callback that is called after each new ping is displayed."""
        self.new_ping_cb = cb

    def newPing(self, label):
        """Receive messages from the queue, decodes them and updates the echogram."""
        while not self.queue.empty():
            try:
                message = self.queue.get(block=False)
            except Empty:
                logger.info('No new data in received message.')
            else:
                try:
                    (t, samInt, c, backscatter, theta, labels) = message

                    if self.firstPing:
                        self.firstPing = False
                        self.createGUI(samInt, c, backscatter, theta, labels)

                    # Update the plots with the data in the new ping
                    pingTime = datetime(1601, 1, 1, tzinfo=timezone.utc)\
                        + timedelta(microseconds=t/1000.0)
                    timeBehind = datetime.now(timezone.utc) - pingTime
                    milliseconds = pingTime.microsecond / 1000
                    label.config(text=f'Ping at {pingTime:%Y-%m-%d %H:%M:%S}.' +
                                 f'{milliseconds:03.0f} '
                                 f'({humanize.precisedelta(timeBehind)} ago)')
                    logger.info('Displaying ping that occurred at %s.', pingTime)

                    self.minTargetRange = min(self.rangeRing1.range, self.rangeRing2.range)
                    self.maxTargetRange = max(self.rangeRing1.range, self.rangeRing2.range)

                    # print('Range rings: {}, {}'.format(self.minTargetRange, self.maxTargetRange))

                    minSample = int(np.floor(2*self.minTargetRange / (samInt * c)))
                    maxSample = int(np.floor(2*self.maxTargetRange / (samInt * c)))

                    self.updateBeamNum(theta)  # sets self.beam from self.beamLineAngle

                    # work out the beam indices
                    if self.beam == 0:
                        beamPort = self.numBeams-1
                    else:
                        beamPort = self.beam-1

                    if self.beam == self.numBeams-1:
                        beamStbd = 0
                    else:
                        beamStbd = self.beam+1

                    # print('{}, {}, {}'.format(beamPort, self.beam, beamStbd))
                    # Find the max amplitude between the min and max ranges set by the UI
                    # and store for plotting
                    self.amp = np.roll(self.amp, -1, 1)
                    self.amp[0, -1] = np.max(backscatter[beamPort][minSample:maxSample])
                    max_i = np.argmax(backscatter[self.beam][minSample:maxSample])
                    self.amp[1, -1] = backscatter[self.beam][minSample+max_i]
                    self.rangeMax = (minSample+max_i) * samInt * c / 2.0
                    self.amp[2, -1] = np.max(backscatter[beamStbd][minSample:maxSample])

                    # Store the amplitude for the 3 beams for the echograms
                    self.port = self.updateEchogramData(self.port, backscatter[beamPort])
                    self.main = self.updateEchogramData(self.main, backscatter[self.beam])
                    self.stbd = self.updateEchogramData(self.stbd, backscatter[beamStbd])

                    # Update the plots
                    # Sphere TS from 3 beams
                    self.ampPlotLinePort.set_ydata(self.amp[0, :])
                    self.ampPlotLineMain.set_ydata(self.amp[1, :])
                    self.ampPlotLineStbd.set_ydata(self.amp[2, :])
                    # and smoothed plots
                    coeff = np.ones(self.movingAveragePoints)/self.movingAveragePoints
                    # and measure of ping-to-ping variability
                    variability = np.std(self.amp[1, -self.varNum: -1])
                    if not np.isnan(variability):
                        self.diffVariability.set_text(rf'$\sigma$ = {variability:.1f} dB')

                    self.ampSmooth[0, :] = signal.filtfilt(coeff, 1, self.amp[0, :])
                    self.ampSmooth[1, :] = signal.filtfilt(coeff, 1, self.amp[1, :])
                    self.ampSmooth[2, :] = signal.filtfilt(coeff, 1, self.amp[2, :])
                    self.ampPlotLinePortSmooth.set_ydata(self.ampSmooth[0, :])
                    self.ampPlotLineMainSmooth.set_ydata(self.ampSmooth[1, :])
                    self.ampPlotLineStbdSmooth.set_ydata(self.ampSmooth[2, :])

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

                    self.portEchogramAx.set_title(f'Beam {labels[beamPort].decode()}', loc='left')
                    self.mainEchogramAx.set_title(f'Beam {labels[self.beam].decode()}', loc='left')
                    self.stbdEchogramAx.set_title(f'Beam {labels[beamStbd].decode()}', loc='left')

                    # Polar plot
                    for i, b in enumerate(backscatter):
                        if b.shape[0] > self.maxSamples:
                            self.polar[:, i] = b[0: self.maxSamples]
                        else:
                            samples = b.shape[0]
                            self.polar[:, i] =\
                                np.concatenate((b, self.emptySv*np.ones(self.maxSamples-samples)),
                                               axis=0)

                    self.polarPlot.set_array(self.polar.ravel())

                    if self.new_ping_cb:
                        self.new_ping_cb()

                except Exception:  # if anything goes wrong, just ignore it...
                    logger.warning('Error when processing and displaying echo data:')
                    logger.warning(traceback.print_exc())
                    logger.warning('Ignoring the above and waiting for next ping.')

        self.job = self.root.after(self.checkQueueInterval, self.newPing, label)

    def updateEchogramData(self, data, pingData):
        """Shift the ping data to the left and add in the new ping data."""
        data = np.roll(data, -1, 1)
        if pingData.shape[0] > self.maxSamples:
            data[:, -1] = pingData[0:self.maxSamples]
        else:
            samples = pingData.shape[0]
            data[:, -1] = np.concatenate((pingData[:],
                                          self.emptySv*np.ones(self.maxSamples-samples)), axis=0)
        return data

    def updateBeamNum(self, theta):
        """Get the beam number from the beam line angle and the latest theta."""
        self.beamLineAngle = self.beamLine.value

        idx = (np.abs(theta - self.beamLineAngle)).argmin()
        self.beam = idx
