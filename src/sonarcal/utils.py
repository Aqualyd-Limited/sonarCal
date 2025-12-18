import os
from datetime import datetime, timezone
import numpy as np
import logging
import logging.handlers
from .configuration import config

def setupLogging():
    """Set info, warning, and error message logger to a file and to the console."""
    now = datetime.now(timezone.utc)
    logger_filename = os.path.join(config.logDir(),
                                   now.strftime('log_' + config.appName() + '-%Y%m%d-T%H%M%S.log'))
    logger = logging.getLogger(config.appName())
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s')

    # A logger to a file that is changed periodically
    rotatingFile = logging.handlers.TimedRotatingFileHandler(logger_filename, when='H',
                                                             interval=12, utc=True)
    rotatingFile.setFormatter(formatter)
    logger.addHandler(rotatingFile)

    # add a second output to the logger to direct messages to the console
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    logger.info('Log file is %s.', logger_filename)
    
    return logger


def on_exit(root, job, sig):
    """Call when the Windows cmd console closes."""
    root.after_cancel(job)
    logging.info('Program ending...')
    root.quit()
    # not sure why this call is needed...
    window_closed(root, job)


def window_closed(root, job):
    """Call to nicely end the whole program."""
    config.save_config()
    root.after_cancel(job)
    logging.info('Program ending...')
    logging.shutdown()  # not working???
    root.quit()

def get_adjacent_beams(beam_idx: int, num_beams: int):
    """Work out the indices of the port and starboard beams."""
    # This assumes that a larger theta is to port and that
    # theta are sorted from lowest to highest.
    port = (beam_idx+1) % num_beams
    stbd = (beam_idx-1) % num_beams

    return port, stbd


def beamAnglesFromNetCDF4(f, beamGroup, i):
    """Calculate the beam angles as per the convention for the given beamGroup and ping index."""
    x = f[beamGroup + '/beam_direction_x'][i]
    y = f[beamGroup + '/beam_direction_y'][i]
    z = f[beamGroup + '/beam_direction_z'][i]
    tilt = np.arctan(z / np.sqrt(x**2 + y**2))  # [rad]

    # convert x,y,z direction into a horizontal angle for use elsewhere as per the 
    # coordinate system in the sonar-netcdf4 convention. This is the x-axis to forward
    # and the y-axis to starboard (and z-axis down).

    # Due to the -y below, the arctan2 angles are 0 to forward, decreasing to -pi to port and 
    # increasing to +pi to starboard
    theta = np.arctan2(-y, x)

    return theta, tilt


def SvTSFromSonarNetCDF4(f, beamGroup, i, tilt):
    """Calculate Sv and TS from the given beam group and ping."""
    eqn_type = f[beamGroup].attrs['conversion_equation_type']
    # work around the current Simrad files using integers instead of the
    # type defined in the convetion (which shows up here as a string)
    if isinstance(eqn_type, np.ndarray):
        eqn_type = f'type_{eqn_type[0]}'
    else:
        eqn_type = eqn_type.decode('utf-8')

    if eqn_type == 'type_2':

        # Pick out various variables for the given ping, i
        bs = f[beamGroup + '/backscatter_r'][i]  # an array for each beam
        tau_e = f[beamGroup + '/transmit_duration_equivalent'][i]  # a scaler for the current ping
        Psi = f[beamGroup + '/equivalent_beam_angle'][i]  # a scalar for each beam
        SL = f[beamGroup + '/transmit_source_level'][i]  # a scalar for the current ping
        K = f[beamGroup + '/receiver_sensitivity'][i]  # a scalar for each beam
        deltaG = f[beamGroup + '/gain_correction'][i]  # a scalar for each beam
        G_T = f[beamGroup + '/time_varied_gain'][i]  # a value for each sample in the current ping
        ping_freq_1 = f[beamGroup + '/transmit_frequency_start'][i]  # a scalar for each beam
        ping_freq_2 = f[beamGroup + '/transmit_frequency_stop'][i]  # a scalar for each beam

        # and some more constant things that could be moved out of this function...
        c = f['Environment/sound_speed_indicative'][()]  # a scalar
        alpha_vector = f['Environment/absorption_indicative'][()]  # a vector
        freq_vector = f['Environment/frequency'][()]  # a vector
        ping_freq = (ping_freq_1 + ping_freq_2)/2.0  # a scalar for each beam
        alpha = np.interp(ping_freq, freq_vector, alpha_vector)  # a scalar for each beam

        # some files have nan for some of the above variables, so fix that
        if np.any(np.isnan(deltaG)):
            deltaG = np.zeros(deltaG.shape)
        if np.any(np.isnan(alpha_vector)):
            # quick and dirty...
            alpha = acousticAbsorption(10.0, 35.0, 10.0, ping_freq)

        a_sv = 10.0 * np.log10(c * tau_e * Psi / 2.0) + SL + K + deltaG  # a scalar for each beam
        a_ts = SL + K + deltaG  # a scalar for each beam
        r_offset = 0.25 * c * tau_e

        samInt = f[beamGroup + '/sample_interval'][i]  # [s]

        gain = deltaG  # the beam gain from the file

        # usually some zeros in the data of no real consequence
        sv = []
        ts = []
        with np.errstate(divide='ignore', invalid='ignore'):
            for j in range(0, bs.shape[0]):  # loop over each beam
                # [m] range vector for the current beam
                r = samInt * c/2.0 * np.arange(0, bs[j].size) - r_offset
                sv.append(20.0*np.log10(bs[j]/np.sqrt(2.0)) + 20.0*np.log10(r)\
                          + 2*alpha[j]*r - a_sv[j] + G_T)
                ts.append(20.0*np.log10(bs[j]/np.sqrt(2.0)) + 40.0*np.log10(r)\
                          + 2*alpha[j]*r - a_ts[j] + G_T)
        sv = np.array(sv)
        ts = np.array(ts)

    elif eqn_type == 'type_1':
        # Pick out various variables for the given ping, i
        p_r = f[beamGroup + '/backscatter_r'][i]  # an array for each beam
        p_i = f[beamGroup + '/backscatter_i'][i]  # an array for each beam
        bs = np.absolute(p_r + 1j*p_i)
        tau_e = f[beamGroup + '/transmit_duration_equivalent'][i]  # a scaler for the current ping
        Psi = f[beamGroup + '/equivalent_beam_angle'][i]  # a scalar for each beam
        G = f[beamGroup + '/transducer_gain'][i]  # a scalar for each beam
        P = f[beamGroup + '/transmit_power'][i]  # a scalar
        ping_freq_1 = f[beamGroup + '/transmit_frequency_start'][i]  # a scalar for each beam
        ping_freq_2 = f[beamGroup + '/transmit_frequency_stop'][i]  # a scalar for each beam

        # and some more constant things that could be moved out of this function...
        c = f['Environment/sound_speed_indicative'][()]  # a scalar
        alpha_vector = f['Environment/absorption_indicative'][()]  # a vector
        freq_vector = f['Environment/frequency'][()]  # a vector
        ping_freq = (ping_freq_1 + ping_freq_2)/2.0  # a scalar for each beam
        alpha = np.interp(ping_freq, freq_vector, alpha_vector)  # a scalar
        wl = c / ping_freq  # wavelength [m]

        if np.any(np.isnan(alpha_vector)):
            # quick and dirty...
            alpha = acousticAbsorption(10.0, 35.0, 10.0, ping_freq)

        samInt = f[beamGroup + '/sample_interval'][i]  # [s]

        r_offset = 0.0  # incase we need this in the future

        gain = G  # the beam gain from the file

        # usually some zeros in the data of no real consequence
        sv = []
        ts = []
        with np.errstate(divide='ignore', invalid='ignore'):
            for k in range(0, bs.shape[0]):  # loop over each beam
                # [m] range vector for the current beam
                r = samInt * c/2.0 * np.arange(0, bs[k].size) - r_offset
                sv.append(20.0*np.log10(bs[k]) + 20.0*np.log10(r) + 2*alpha*r\
                    - 10.0*np.log10((P*wl*wl*c*Psi[k]*tau_e) / (32*np.pi*np.pi))\
                    - G[k] - 40.0*np.log10(np.cos(tilt[k])))
                ts.append(20.0*np.log10(bs[k]) + 40.0*np.log10(r) + 2*alpha*r\
                    - 10.0*np.log10((P*wl*wl) / (16*np.pi*np.pi))\
                    - G[k] - 40.0*np.log10(np.cos(tilt[k])))
        sv = np.array(sv)
        ts = np.array(ts)
    else:  # unsupported format - just take the log10 of the numbers. Usually usefull.
        sv = f[beamGroup + '/backscatter_r'][i]
        with np.errstate(divide='ignore'):
            for j in range(0, sv.shape[0]):
                sv[j] = np.log10(sv[j])
        ts = sv

    return sv, ts, gain


def acousticAbsorption(temperature, salinity, depth, frequency):
    """Calculate acoustic absorption.

    Uses Ainslie & McColm, 1998.
    Units are:
        temperature - degC
        salinity - PSU
        depth - m
        frequency - Hz
        alpha - dB/m
    """
    frequency = frequency / 1e3  # [kHz]
    pH = 8.0

    z = depth/1e3  # [km]
    f1 = 0.78 * np.sqrt(salinity/35.0) * np.exp(temperature/26.0)
    f2 = 42.0 * np.exp(temperature/17.0)
    alpha = 0.106 * (f1*frequency**2./(frequency**2+f1**2)) * np.exp((pH-8.0)/0.56) \
        + 0.52*(1+temperature/43.0) * (salinity/35.0) \
        * (f2*frequency**2)/(frequency**2+f2**2) * np.exp(z/6.0) \
        + 0.00049*frequency**2 * np.exp(-(temperature/27.0+z/17.0))
    alpha = alpha * 1e-3  # [dB/m]

    return alpha

def cartesian_to_spherical(x: float, y: float, z: float) -> tuple:
    """Convert Cartesian coordinates (x, y, z) to spherical coordinates (r, theta, phi).

    Parameters
    ----------
    x, y, z : float or array-like
        Cartesian coordinates.

    Returns
    -------
    r, theta, phi : float or array-like
        Spherical coordinates:
        r - radial distance
        theta - polar angle (inclination from positive z-axis) in radians
        phi - azimuthal angle (from positive x-axis in xy-plane) in radians
    """
    r = np.sqrt(x**2 + y**2 + z**2)

    # Handle the case where r is zero to avoid division by zero
    theta = np.arccos(z / r) if r != 0.0 else 0.0

    phi = np.arctan2(y, x)

    return r, theta, phi

def nt_time_to_datetime(nt_time: int):
    """Convert a Windows time number to a Python datetime object.

    Paramters
    --------
    nt_time :
        The Windows NT time value (number of 100-nanosecond
        intervals since January 1, 1601 UTC)
        
    Returns
    -------
        datetime.datetime: The corresponding datetime object in UTC.
    """
    # FILETIME epoch is January 1, 1601 UTC
    # Unix epoch is January 1, 1970 UTC
    # Calculate the difference in 100-nanosecond intervals
    # 100-nanoseconds per interval, 10,000,000 intervals per second
    # 11644473600 seconds between 1601-01-01 and 1970-01-01
    unix_epoch_diff = 116444736000000000  # in 100-nanosecond intervals

    # Convert NT time to Unix timestamp (seconds since 1970-01-01 UTC)
    # Subtract the difference to get intervals since Unix epoch
    # Divide by 10,000,000 to convert to seconds
    timestamp = (nt_time - unix_epoch_diff) / 10000000

    # Create a datetime object from the Unix timestamp
    return datetime.fromtimestamp(timestamp, timezone.utc)
