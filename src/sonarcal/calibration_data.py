# import pandas as pd
import logging
from .configuration import config

logger = logging.getLogger(config.appName())

class calibrationData():
    """Storage for sonar caliration results."""

    def __init__(self):
        import pandas as pd  # deferred to save startup time
        self.data = pd.DataFrame(columns=['Time (local)', 'Tx gain [dB]', 'Cal. offset [dB]',
                                          'Target TS [dB]', 
                                          'TS RMS [dB]', 'Range [m]', 'No. echoes'])
        self.data.index.name = 'Beam'
    
    def update(self, beam_label: str, timestamp: str, gain: float, cal_offset: float,
               ts: float, rms: float, r: float, num: int):
        self.data.loc[beam_label] = (timestamp, gain, cal_offset, ts, rms, r, num)
        
    def remove(self, beam_labels: list[str]):
        """Remove data for given beam."""
        self.data.drop(index=beam_labels, inplace=True)
        
    def df(self):
        return self.data  # eventually return a better form of the data?
    
    def save(self, filename:str):
        """Save the calibration data to a csv file."""

        if filename:
            logger.info('Saved results to %s', filename)

            # the dataframe index is str, but it will mostly be integer values, so make things
            # sort numerically if an int followed by non-ints.
            int_order = sorted((x for x in self.data.index if x.isdigit()), key=lambda i: int(i))
            str_order = sorted(x for x in self.data.index if not x.isdigit())
            self.data.loc[int_order+str_order].to_csv(filename)

    