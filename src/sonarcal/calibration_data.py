import pandas as pd

class calibrationData():
    """Storage for sonar caliration results."""

    def __init__(self):
        self.data = pd.DataFrame(columns=['Time', 'Gain (dB)', 'RMS (dB)', 'Range (m)', 'Echoes'])
        self.data.index.name = 'Beam'
    
    def add(self, beam: int, timestamp: str, gain: float, rms: float, r: float, num: int):
        self.data.loc[beam] = (timestamp, gain, rms, r, num)
        
    def df(self):
        return self.data  # eventually return a better form of the data?
    