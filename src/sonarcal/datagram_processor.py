"""Code to process raw datagrams into Sv and TS."""

class rawDatagramProcessor():
    """XXX."""

    def __init__(self):
        self._dgs = []
        self._prev_ping_time = None


        self.product_name = ''
        self.sv = None
        self.ts = None
        self.sound_speed = None
        self.ping_time = None
        self.sample_interval = None
        self.labels = None
        self.theta = None
        self.gains = None
        self.ping_interval = 1.0  # [s] until we get two pings of data
        
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
            # have now received all data for a ping, so process and set the various
            # processed variables

            # steps:
            # 1. pull out beam amplitude for the horizontal beams
            # 2. get ancillary beam info - pointing angles, labels, gains
            # 3. get ancillary info - sample interval, ping_time
            # 4. calculate sv and ts
            # 5. work out other stuff

            # much of the setup info is in PCO0

            # need to calculate the tvg
            
            # and calculate ts and sv from the beam amplitudes
            
            # may need sa correction, gain adjust and sa correction adjust?

            # clear current ping datagrams in prep for receiving datagrams from a new ping
            self._dgs = []

            return True
        else:
            self._dgs.append(dg)       

            # Pick out data that doesn't need end of ping processing
            match dg['type']:
                case 'VER0':
                    self.product_name = dg['product_name']
                case 'PIN0' | 'PIN1':
                    self.sound_speed = dg['sound_velocity']

            return False

