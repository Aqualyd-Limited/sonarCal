import sys
from time import sleep
# import h5py
import numpy as np
from datetime import datetime
from .utils import beamAnglesFromNetCDF4, SvTSFromSonarNetCDF4, nt_time_to_datetime
from .datagram_processor import rawDatagramProcessor
import logging
from pathlib import Path
from .configuration import config
from .raw_parser import simrad_raw_file as raw


logger = logging.getLogger(config.appName())

def most_recent_file(watch_dir: Path, wait_interval: float=1.0):
    """Get the most recent .nc or .raw file in the directory."""

    while True:
        files = sorted(list(watch_dir.glob('*.nc')) + list(watch_dir.glob('*.raw')))

        if files:
            return files[-1]

        logger.info("No .nc or .raw file found in '%s'", watch_dir)
        sleep(wait_interval)


def file_type(filename: Path):
    """Works out what sonar the data file is from and what format it is."""
    
    match filename.suffix:
        case '.nc':
            return 'sonar-netcdf4'
        case '.raw':
            return 'simrad-raw'
    return ''


def sonar_file_read(msg_queue):
    """Run code to listen to or read from the last file in the watched directory."""
    
    watch_dir = config.watchDir()
    beam_group = config.horizontalBeamGroup()
    live_data = config.liveData()

    last_file = most_recent_file(watch_dir)

    # beamGroup is currently only correct for netcdf files, not raw files.
    
    match file_type(last_file):
        case 'sonar-netcdf4':
            if live_data:
                file_listen_netcdf(watch_dir, beam_group, msg_queue)
            else:
                file_replay_netcdf(watch_dir, beam_group, msg_queue)
        case 'simrad-raw':
            if live_data:
                file_listen_raw(watch_dir, msg_queue)
            else:
                file_replay_raw(watch_dir, msg_queue)
        case _:
            logger.error('Unsupported sonar file type')


def file_listen_netcdf(watchDir, beamGroup, msg_queue):
    """Listen for new data in a file.

    Find new data in the most recent file (and keep checking for more new data).
    Used for live calibrations.
    """
    # A more elegant method for all of this can be found in the examples here:
    # https://docs.h5py.org/en/stable/swmr.html, which uses the watch facility
    # in the hdf5 library (but we're not sure if the omnisonars write data in
    # a manner that this will work with).

    # Config how and when to give up looking for new data in an existing file.
    maxNoNewDataCount = 20  # number of tries to find new pings in an existing file
    waitInterval = 0.5  # [s] time period between checking for new pings
    waitIntervalFile = 1.0  # [s] time period between checking for new files
    errorWaitInterval = 0.2  # [s] time period to wait if there is a file read error

    pingIndex = -1  # which ping to read. -1 means the last ping, -2 the second to last ping

    t_previous = datetime(1970, 1, 1)  # timestamp of previous ping
    f_previous = ''  # previously used file

    while True:  # could add a timeout on this loop...
        mostRecentFile = most_recent_file(watchDir, waitIntervalFile)

        if mostRecentFile == f_previous:  # no new file was found
            logger.info('No newer file found. Will try again in %s s.', str(waitIntervalFile))
            sleep(waitIntervalFile)  # wait and try again
        else:
            logger.info('Listening to file: %s.', mostRecentFile)
            noNewDataCount = 0

            while noNewDataCount <= maxNoNewDataCount:
                # open netcdf file
                try:
                    import h5py  # deferred to save startup time
                    f = h5py.File(mostRecentFile, 'r', libver='latest', swmr=True)
                    # f = h5py.File(mostRecentFile, 'r') # without HDF5 swmr option
                    f_previous = mostRecentFile

                    t = nt_time_to_datetime(f[beamGroup + '/ping_time'][pingIndex]/100)

                    if t > t_previous:  # there is a new ping in the file

                        theta, tilt = beamAnglesFromNetCDF4(f, beamGroup, pingIndex)
                        sv, ts, gains = SvTSFromSonarNetCDF4(f, beamGroup, pingIndex, tilt)

                        samInt = f[beamGroup + '/sample_interval'][pingIndex]
                        c = f['Environment/sound_speed_indicative'][()]
                        labels = f[beamGroup + '/beam']

                        # convert HDF5 text to list of str
                        labels = np.array([s.decode('utf-8') for s in labels])

                        t_previous = t
                        noNewDataCount = 0  # reset the count
                       
                        # send the data off to be plotted
                        msg_queue.put((t, samInt, c, sv, ts, theta, gains, labels))
                    else:
                        noNewDataCount += 1
                        if noNewDataCount > maxNoNewDataCount:
                            logger.info('No new data found in file %s after waiting %.1f s.',
                                         mostRecentFile.name, noNewDataCount * waitInterval)

                    f.close()
                    # try this instead of opening and closing the file
                    # t.id.refresh(), etc
                    sleep(waitInterval)
                except OSError:
                    f.close()  # just in case...
                    e = sys.exc_info()
                    logger.warning('OSError when reading netCDF4 file:')
                    logger.warning(e)
                    logger.warning('Ignoring the above and trying again.')
                    sleep(errorWaitInterval)


def file_replay_netcdf(watchDir, beamGroup, msg_queue):
    """Replay all data in the directory. Used for testing."""

    files = list(watchDir.glob('*.nc'))

    if not files:
        logger.info('No .nc files in %s', watchDir)

    for file in sorted(files, key=lambda p: p.stem):
        logger.info('Replaying file: %s', file)

        # open netcdf file
        import h5py  # deferred to save startup time
        f = h5py.File(file, 'r')

        t = f[beamGroup + '/ping_time']

        # Send off each ping at a sedate rate...
        for i in range(0, t.shape[0]):
            theta, tilt = beamAnglesFromNetCDF4(f, beamGroup, i)
            sv, ts, gains = SvTSFromSonarNetCDF4(f, beamGroup, i, tilt)

            samInt = f[beamGroup + '/sample_interval'][i]
            c = f['Environment/sound_speed_indicative'][()]
            labels = f[beamGroup + '/beam']

            # convert HDF5 text to list of str
            labels = np.array([s.decode('utf-8') for s in labels])

            # send the data off to be plotted
            ping_time = nt_time_to_datetime(t[i]/100)
            msg_queue.put((ping_time, samInt, c, sv, ts, theta, gains, labels))

            sleep(config.replayPingInterval())

        f.close()
    
    logger.info('Finished replaying files in %s', watchDir)


def file_listen_raw(watchDir: Path, msg_queue):
    """Replay live files."""

    previous_file = None

    # Check this often for files to appear in the directory if there are none
    file_wait = 2.0  # [s]
    
    # Check this often for new files to appear in the directory once we've finished
    # reading an existing file
    new_file_wait = 2.0  # [s]

    while True:
        files = list(watchDir.glob('*.raw'))

        if not files:
            logger.info('No .raw files in %s. Waiting...', watchDir)
            sleep(file_wait)
            continue

        sorted_files = sorted(files, key=lambda p: p.stem)
        last_file = sorted_files[-1]

        if last_file == previous_file:
            # there is no new file, we've already read through the
            # most recent file, so perhaps the sonar has finished
            # recording. We'll wait for more...
            logger.info('No new .raw files to read. Waiting for more...')
            sleep(new_file_wait)
            continue

        previous_file = last_file

        # there is a new raw file to read
        with raw.RawSimradFile(last_file) as fid:
            proc = rawDatagramProcessor()
            # read and process datagrams in last_file as they get written to the file
            logger.info('Reading datagrams from %s', last_file.name)

            while True:
                # live_read() will block waiting for a new datagram to be appended to the file.
                # If nothing gets appended after a few seconds it raises a
                # SimradFileFinished exception
                try:
                    dg = fid.live_read()
                    
                    if proc.add_datagram(dg):  # returns True when a processed ping is available
                        
                        msg_queue.put((proc.ping_time, proc.sample_interval, proc.sound_speed,
                                      proc.sv, proc.ts, proc.theta, proc.gain_rx, proc.labels))

                        sleep(config.replayPingInterval())
                except raw.SimradFileFinished:
                    break  # go back to the outer 'while True' loop to look for a new file.


def file_replay_raw(watchDir: Path, msg_queue):
    """Replays raw files."""

    files = list(watchDir.glob('*.raw'))

    if not files:
        logger.info('No .raw files in %s', watchDir)

    for file in sorted(files, key=lambda p: p.stem):
        with raw.RawSimradFile(file) as fid:
            proc = rawDatagramProcessor()
            logger.info('Reading datagrams from %s', file.name)

            while True:
                try:
                    dg = fid.read(1)

                    if proc.add_datagram(dg):  # returns True when a processed ping is available
                        msg_queue.put((proc.ping_time, proc.sample_interval, proc.sound_speed,
                                      proc.sv, proc.ts, proc.theta, proc.gain_rx, proc.labels))
                        sleep(config.replayPingInterval())
                except raw.SimradEOF:
                    break  # go back to the outer 'while True' loop for the next file
    
    logger.info('Finished replaying files in %s', watchDir)
