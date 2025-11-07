import sys
import queue
from time import sleep
from datetime import datetime, timedelta
import h5py
from .utils import beamAnglesFromNetCDF4, SvFromSonarNetCDF4
import logging


logger = logging.getLogger("sonar_cal")

def file_listen(watchDir, beamGroup):
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
        # Find the most recent file in the directory
        while True:
            files = sorted(list(watchDir.glob('*.nc')))
            if files:
                mostRecentFile = files[-1]
                break
            logger.info('No .nc file found in %s.', watchDir)
            sleep(waitIntervalFile)

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
                        queue.put((t, samInt, c, sv, theta, labels))
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


def file_replay(watchDir, beamGroup, replayRate):
    """Replay all data in the newest file. Used for testing."""
    waitIntervalFile = 1.0  # [s] time period between checking for new files

    # Find the most recent file in the directory
    while True:
        files = sorted(list(watchDir.glob('*.nc')))
        if files:
            mostRecentFile = files[-1]
            break
        logger.info('No .nc file found in %s.', watchDir)
        sleep(waitIntervalFile)

    logger.info('Listening to file: %s.', mostRecentFile)

    # open netcdf file
    f = h5py.File(mostRecentFile, 'r')

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
        queue.put((t[i], samInt, c, sv, theta, labels))

        # Ping at recorded ping rate if asked
        if replayRate == 'realtime' and i > 0:
            # t has units of nanoseconds
            sleep((t[i] - t[i-1])/1e9)
        else:
            sleep(0.2)

    f.close()

    logger.info('Finished replaying file: %s', mostRecentFile)
