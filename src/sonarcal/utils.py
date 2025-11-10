import os
from datetime import datetime, timezone
import numpy as np
import logging
import logging.handlers

app_name = 'sonarcal'

def setupLogging(log_dir, label):
    """Set info, warning, and error message logger to a file and to the console."""
    now = datetime.now(timezone.utc)
    logger_filename = os.path.join(log_dir, now.strftime('log_' + label + '-%Y%m%d-T%H%M%S.log'))
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')

    # A logger to a file that is changed periodically
    rotatingFile = logging.handlers.TimedRotatingFileHandler(logger_filename, when='H',
                                                             interval=12, utc=True)
    rotatingFile.setFormatter(formatter)
    logger.addHandler(rotatingFile)

    # add a second output to the logger to direct messages to the console
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    logger.info('Log files are in %s.', log_dir.as_posix())


def on_exit(root, job, sig):
    """Call when the Windows cmd console closes."""
    root.after_cancel(job)
    logging.info('Program ending...')
    root.quit()
    # not sure why this call is needed...
    window_closed(root, job)


def window_closed(root, job):
    """Call to nicely end the whole program."""
    root.after_cancel(job)
    logging.info('Program ending...')
    logging.shutdown()  # not working???
    root.quit()


def beamAnglesFromNetCDF4(f, beamGroup, i):
    """Calculate the beam angles as per the convention for the given beamGroup and ping index."""
    x = f[beamGroup + '/beam_direction_x'][i]
    y = f[beamGroup + '/beam_direction_y'][i]
    z = f[beamGroup + '/beam_direction_z'][i]
    tilt = np.arctan(z / np.sqrt(x**2 + y**2))  # [rad]

    # convert x,y,z direction into a horizontal angle for use elsewhere
    theta = np.arctan2(-y, x)
    # Make angles go 0 to 2pi, not -pi to 0 to pi (all anti-clockwise)
    theta = np.mod(theta, 2*np.pi)

    return theta, tilt


def SvFromSonarNetCDF4(f, beamGroup, i, tilt):
    """Calculate Sv from the given beam group and ping."""
    eqn_type = f[beamGroup].attrs['conversion_equation_type']
    # work around the current Simrad files using integers instead of the
    # type defined in the convetion (which shows up here as a string)
    if isinstance(eqn_type, np.ndarray):
        eqn_type = f'type_{eqn_type[0]}'
    else:
        eqn_type = eqn_type.decode('utf-8')

    if eqn_type == 'type_2':

        # Pick out various variables for the given ping, i
        sv = f[beamGroup + '/backscatter_r'][i]  # an array for each beam
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

        a = 10.0 * np.log10(c * tau_e * Psi / 2.0) + SL + K + deltaG  # a scalar for each beam
        r_offset = 0.25 * c * tau_e

        samInt = f[beamGroup + '/sample_interval'][i]  # [s]

        # usually some zeros in the data of no real consequence
        with np.errstate(divide='ignore', invalid='ignore'):
            for j in range(0, sv.shape[0]):  # loop over each beam
                # [m] range vector for the current beam
                r = samInt * c/2.0 * np.arange(0, sv[j].size) - r_offset
                sv[j] = 20.0*np.log10(sv[j]/np.sqrt(2.0)) + 20.0*np.log10(r)\
                    + 2*alpha[j]*r - a[j] + G_T

    elif eqn_type == 'type_1':
        # Pick out various variables for the given ping, i
        p_r = f[beamGroup + '/backscatter_r'][i]  # an array for each beam
        p_i = f[beamGroup + '/backscatter_i'][i]  # an array for each beam
        sv = np.absolute(p_r + 1j*p_i)
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

        # usually some zeros in the data of no real consequence
        with np.errstate(divide='ignore', invalid='ignore'):
            for k in range(0, sv.shape[0]):  # loop over each beam
                # [m] range vector for the current beam
                r = samInt * c/2.0 * np.arange(0, sv[k].size) - r_offset
                sv[k] = 20.0*np.log10(sv[k]) + 20.0*np.log10(r) + 2*alpha*r\
                    - 10.0*np.log10((P*wl*wl*c*Psi[k]*tau_e) / (32*np.pi*np.pi))\
                    - G[k] - 40.0*np.log10(np.cos(tilt[k]))

    else:  # unsupported format - just take the log10 of the numbers. Usually usefull.
        sv = f[beamGroup + '/backscatter_r'][i]
        with np.errstate(divide='ignore'):
            for j in range(0, sv.shape[0]):
                sv[j] = np.log10(sv[j])

    return sv


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
