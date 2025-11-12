import sys
from time import sleep
from datetime import datetime, timedelta
import h5py
from .utils import beamAnglesFromNetCDF4, SvFromSonarNetCDF4, app_name
import logging
from pathlib import Path

logger = logging.getLogger(app_name)

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
    
    # Options will be 'sonar-netcdf4', 'CS90-raw', 'SN90-raw'

    match filename.suffix:
        case '.nc':
            return 'sonar-netcdf4'
        case '.raw':
            # could be several, so read some datagrams from the file...
            return ''

def file_listen(watchDir, beamGroup, msg_queue):
    """ """
    
    last_file = most_recent_file(watchDir)
    f_type = file_type(last_file)
    
    params = (watchDir, beamGroup, msg_queue)
    
    match f_type:
        case 'sonar-netcdf4':
            file_listen_netcdf(*params)
        case 'CS90-raw':
            file_listen_cs90_raw(*params)
        case 'SN90-raw':
            file_listen_sn90_raw(*params)
        case _:
            logger.error('Unsupported file type')


def file_replay(watchDir, beamGroup, msg_queue, replayRate):
    """Replay the most recent sonar file in the watched directory."""

    replay_file = most_recent_file(watchDir)
    f_type = file_type(replay_file)

    params = (replay_file, beamGroup, msg_queue, replayRate)
    
    match f_type:
        case 'sonar-netcdf4':
            file_replay_netcdf(*params)
        case 'CS90-raw':
            file_replay_cs90_raw(*params)
        case 'SN90-raw':
            file_replay_sn90_raw(*params)
        case _:
            logger.error('Unsupported file type')


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

    t_previous = 0  # timestamp of previous ping
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
                    f = h5py.File(mostRecentFile, 'r', libver='latest', swmr=True)
                    # f = h5py.File(mostRecentFile, 'r') # without HDF5 swmr option
                    f_previous = mostRecentFile

                    t = f[beamGroup + '/ping_time'][pingIndex]

                    if t > t_previous:  # there is a new ping in the file
                        pingTime = datetime(1601, 1, 1) + timedelta(microseconds=t/1000.0)
                        logger.info('Start reading ping from time %s', pingTime)

                        theta, tilt = beamAnglesFromNetCDF4(f, beamGroup, pingIndex)
                        sv = SvFromSonarNetCDF4(f, beamGroup, pingIndex, tilt)

                        samInt = f[beamGroup + '/sample_interval'][pingIndex]
                        c = f['Environment/sound_speed_indicative'][()]
                        labels = f[beamGroup + '/beam']

                        t_previous = t
                        noNewDataCount = 0  # reset the count

                        logger.info('Finished reading ping from time %s', pingTime)
                        # send the data off to be plotted
                        msg_queue.put((t, samInt, c, sv, theta, labels))
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


def file_replay_netcdf(replay_file, beamGroup, msg_queue, replayRate):
    """Replay all data in the newest file. Used for testing."""
    logger.info('Reading from file: %s.', replay_file)

    # open netcdf file
    f = h5py.File(replay_file, 'r')

    t = f[beamGroup + '/ping_time']

    # Send off each ping at a sedate rate...
    for i in range(0, t.shape[0]):
        # print('ping')
        theta, tilt = beamAnglesFromNetCDF4(f, beamGroup, i)
        sv = SvFromSonarNetCDF4(f, beamGroup, i, tilt)

        samInt = f[beamGroup + '/sample_interval'][i]
        c = f['Environment/sound_speed_indicative'][()]
        labels = f[beamGroup + '/beam']

        # send the data off to be plotted
        msg_queue.put((t[i], samInt, c, sv, theta, labels))

        # Ping at recorded ping rate if asked
        if replayRate == 'realtime' and i > 0:
            # t has units of nanoseconds
            sleep((t[i] - t[i-1])/1e9)
        else:
            sleep(0.2)

    f.close()

    logger.info('Finished replaying file: %s', replay_file)


def file_replay_cs90_raw(replay_file, beamGroup, msg_queue, replayRate):
    """Replay all data in the newest file. Used for testing."""

    logger.error('CS90 raw files are not yet supported')


def file_replay_sn90_raw(replay_file, beamGroup, msg_queue, replayRate):
    """Replay all data in the newest file. Used for testing."""

    logger.error('SN90 raw files are not yet supported')


def file_listen_cs90_raw(watchDir, beamGroup, msg_queue):
    """XXX"""
    logger.error('CS90 raw files are not yet supported')
    

def file_listen_sn90_raw(watchDir, beamGroup, msg_queue):
    """XXX"""
    logger.error('SN90 raw files are not yet supported')
