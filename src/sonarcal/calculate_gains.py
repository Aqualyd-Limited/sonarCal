# this file uses deferred imports

def calculate_calibration(sphere_echoes: list[tuple], sphere_ts: float)\
    -> tuple[float, float, float, float, int]:
    """Calculate the beam calibration gain and other stats."""

    # deferred imports to reduce program startup time
    import pandas as pd
    import scipy.stats.mstats as ms
    import numpy as np

    df = pd.DataFrame(sphere_echoes, columns=['timestamp', 'ts', 'range'])

    # find and ignore extreme sphere echoes
    trimmed = ms.trim(df['ts'], limits=(0.05, 0.05), relative=True)
    mask = np.logical_not(np.ma.getmaskarray(trimmed))
    dfm = df[mask]

    ts_mean = 10.0 * np.log10(np.mean(np.power(10, dfm['ts']/10.0)))
    ts_rms = np.sqrt(np.mean(np.square(dfm['ts']-ts_mean)))

    # This is quite specific to the actual sonar equations - is ok for Simrad and Furuno
    # omnisonars as of 2025...

    # and the new gain correction is....
    gain_adjust = ts_mean - sphere_ts

    return (gain_adjust, ts_mean, ts_rms, np.mean(dfm['range']), len(dfm))

