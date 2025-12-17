"""Code to process Simrad raw sonar datagrams into Sv and TS."""
import logging
import numpy as np
from .utils import cartesian_to_spherical
from .configuration import config as config

logger = logging.getLogger(config.appName())


class rawDatagramProcessor():
    """Calculates Sv and TS from Simrad raw datagrams from sonars."""

    def __init__(self):
        self._raw_dgs = []
        self._power = []

        # There are multiple fans. 
        # In the example data:
        #
        # SN90 has 'Horizontal-H', 'Vertical-H', and 'InspectionC-H'
        # CS90 has 'Horizontal-H', and 'Vertical-H'
        #
        # This code currently only uses the horizontal fan
        self.selected_fan_name = 'Horizontal-H'
        self.selected_ping_name = 'Horizontal'

        self.product_name = ''
        self.sv = None  # [dB]
        self.ts = None  # [dB]
        self.sound_speed = None  # [m/s]
        self.ping_time = None  # [datetime]
        self.sample_interval = None  # [m]
        self.pulse_duration = None  # [s]
        self.frequency = None  # [Hz]
        self.transmit_power = None  # [W]
        self.equivalent_beam_angle = None  # [dB]
        self.labels = None
        self.theta = None  # [rad]
        self.tilts = None  # [rad]
        self.gain_rx = None  # [dB]
        self.gain_adjust = None  # [dB]
        self.sa_correction = None  # [dB]
        self.sa_correction_adjust = None  # [dB]
        self.absorption_coefficient = None  # [dB/m]
        
    def add_datagram(self, dg: dict) -> bool:
        """Accumulates datagrams for a ping.

        Parameters
        ----------
        dg :
            A Simrad sonar datagram
        
        Returns
        -------
        : True if all pings for a datagram have been received and processed ping data
            are available, otherwise False
        """
        
        if dg['type'] == 'EOP0':
            # have now received all data for a ping
            self._calculate_sv_ts()

            # in prep for new data
            self._power.clear()

            return True
        else:
            # Pick out data that doesn't need end of ping processing
            match dg['type']:
                case 'VER0':
                    self.product_name = dg['product_name']
                case 'PCO0' | 'PCO1':  # ping configuration, once per file
                    self._extract_ping_config(dg)
                case 'PIN0' | 'PIN1':  # ping information, once per ping
                    self.sound_speed = dg['sound_velocity']
                    self.ping_time = dg['ping_time'].datetime
                case 'RAW2':  # multiple per ping
                    self._accumulate_raw(dg)

            return False

    def _calculate_sv_ts(self) -> None:
        """Calculate Sv and TS for the just finished ping."""

        # reshape the power data to join together the separate blocks of power data
        power = np.concatenate(self._power, axis=1)
        num_samples = power.shape[1]

        gain_tx = 0  # unknown value so default to zero

        wavenumber = self.sound_speed / self.frequency
        tilt_corr = 40.0 * np.log10(np.cos(self.tilts))
        range_corr = 3.0  # [m] empirical range correction
        sample_range = self.sound_speed * self.sample_interval / 2.0
        r = np.arange(num_samples) * sample_range - range_corr
        # Ranges less than 0 get set to the smallest positive range
        r[r<sample_range] = sample_range

        tvg = 20*np.log10(r) + 2*r*self.absorption_coefficient
        sv_const = (10*np.log10(self.transmit_power * wavenumber**2 * self.sound_speed
                                * self.pulse_duration / (32.0 * np.pi**2)))\
                    + 2*gain_tx + 2*self.gain_rx + tilt_corr\
                    + 2*self.sa_correction\
                    + self.equivalent_beam_angle

        # make tvg and sv_const into 2D matrices to get broadcasting to work
        self.sv = power + tvg[np.newaxis, :] - sv_const[:, np.newaxis]

        tvg = 40*np.log10(r) + 2*r*self.absorption_coefficient
        ts_const = (10*np.log10(self.transmit_power * wavenumber**2 / (16.0 * np.pi**2)))\
                    + 2*gain_tx + 2*self.gain_rx + tilt_corr

        self.ts = power + tvg[np.newaxis, :] - ts_const[:, np.newaxis]

    def _accumulate_raw(self, raw: dict) -> None:
        
        # the raw datagrams can be from different beams and are also split into 
        # separate blocks (split by sample it seems). It also seems they they always
        # arrive with lowest samples first. Will need to change the code a bit if 
        # that isn't always the case.
        
        # beam id's can be:
        # SMSU - non-match-filtered samples intended for generating audio output
        # SMSM - main beam matched-filtered samples
        # SMSx - matched-filtered split beams, where x is:
        #   F - forward
        #   B - back
        #   S - starboard
        #   P - port
        
        # print(raw['datagram_number'], raw['sample_index'], raw['ping_number'],
        #       raw['beam_index_start'], num_samples)
        
        if raw['id'] == 'SMSM':
            # a SMSM message with no samples and the most significant bit of the
            # datagram_number field set marks the end of the current ping
            if (raw['datagram_number'] & (1 << 31)) != 0:
                # But we use the EOP datagram rather than this empty RAW2 datagram to 
                # know when to process the backscatter into Sv and TS
                return

            # It seems that:
            # - for the CS90 sonar, beam_index_start == 0 selects the horizontal fan
            #                       beam_index_start == 64 selects the vertical fan
            # - for the SN90 sonar, beam_index_start == 0 selects the vertical fan
            #                       beam_index_start == 32 selects the horizontal fan
            #                       beam_index_start == 64 selects the inspection beams
            # print(raw['beam_index_start'])
            beam_index_start = 32 if self.product_name == 'SN90' else 0
            
            if raw['beam_index_start'] == beam_index_start:
                # don't need the complex values so save some space...
                self._power.append(20.0*np.log10(np.abs(raw['data'])))


    def _extract_ping_config(self, pco: dict) -> None:
        """Extract various parameters that are needed to calculate Sv and TS."""
        
        # TODO assumes that there is only one transcevier config!!!
        cfg =  pco['ping_configuration']['transceiver_config'][0]

        # Find which fan dataset is self.selected_fan_name
        rx_fan = [fan for fan in cfg['rx_config']['fans']
                  if fan['fan_name'] == self.selected_fan_name]
        # and same for selected ping
        tx_config = [ping for ping in cfg['tx_config']['tx_ping_config']
                     if ping['ping_name'] == self.selected_ping_name]
        
        if not rx_fan:
            logger.error('No fan with name of %s found in the ping configuration datagram',
                         self.selected_fan_name)

        # for less typing below
        rx_fan = rx_fan[0]
        tx_config = tx_config[0]

        self.sample_interval = rx_fan['sample_interval']
        # there is an absorption value for each beam so use that instead of this one
        # self.absorption_coefficient = rx_fan['rx_beams'][0]['performance_info']['absorption_coefficient']
        self.transmit_power = tx_config['performance_info']['tx_power']
        self.frequency = tx_config['frequency']
        self.pulse_duration = tx_config['pulse_duration']
        
        g = []
        g_a = []
        sa = []
        sa_a = []
        eba = []
        alpha = []
        th = []
        tl = []
        lbls = []

        beams = rx_fan['rx_beams']

        for b in beams:
            lbls.append(b['beam_name'][-3:]) # pick out the number part of the beam name

            _, inc, azi = cartesian_to_spherical(b['steering_vector_hcs_x'],
                                                 b['steering_vector_hcs_y'],
                                                 b['steering_vector_hcs_z'])
            th.append(azi)
            tl.append(inc)

            g.append(b['performance_info']['gain'])
            g_a.append(b['performance_info']['gain_adjust'])
            sa.append(b['performance_info']['sa_correction'])
            sa_a.append(b['performance_info']['sa_correction_adjust'])
            alpha.append(b['performance_info']['absorption_coefficient'])

            EBA = b['performance_info']['equivalent_beam_angle']

            if EBA == 0.0:
                # Use the classic Simrad approximate formula
                EBA = 10*np.log10(b['beam_width_x'] * b['beam_width_y'] / 5800)
                logger.warning('No EBA for beam %s - using %.1f dB', b['beam_name'], EBA)
            eba.append(EBA)

        self.theta = -np.array(th)
        self.tilts = np.pi/2 - np.array(tl)
        self.labels = np.array(lbls)
        self.gain_rx = np.array(g)
        self.gain_adjust = np.array(g_a)
        self.sa_correction = np.array(sa)
        self.sa_correction_adjust = np.array(sa_a)
        self.absorption_coefficient = np.array(alpha).mean()  # same for all beams one expects!
        self.equivalent_beam_angle = np.array(eba)
