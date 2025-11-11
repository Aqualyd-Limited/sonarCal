import pandas as pd

def calculate_gain(sphere_ts):
    """Calculate the beam calibration gain and other stats."""
    df = pd.DataFrame(sphere_ts, columns=['timestamp', 'ts', 'range'])
    return (df['ts'].mean(), df['ts'].std(), df['range'].mean(), len(df))

