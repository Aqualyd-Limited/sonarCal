# import pandas as pd
import logging
from .utils import app_name

logger = logging.getLogger(app_name)

class calibrationData():
    """Storage for sonar caliration results."""

    def __init__(self):
        import pandas as pd  # deferred to save startup time
        self.data = pd.DataFrame(columns=['Time', 'Gain (dB)', 'RMS (dB)', 'Range (m)', 'Echoes'])
        self.data.index.name = 'Beam'
    
    def update(self, beam_label: str, timestamp: str, gain: float, rms: float, r: float, num: int):
        self.data.loc[beam_label] = (timestamp, gain, rms, r, num)
        
    def remove(self, beam_labels: list[str]):
        """Remove data for given beam."""
        self.data.drop(index=beam_labels, inplace=True)
        
    def df(self):
        return self.data  # eventually return a better form of the data?
    
    def save(self, filename:str):
        """Save the calibration data to a csv file."""

        if filename:
            logger.info('Saved results to %s', filename)
            self.data.sort_index().to_csv(filename)

    