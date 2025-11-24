import sys
from time import sleep
from datetime import datetime, timedelta
# import h5py
import numpy as np
from .utils import beamAnglesFromNetCDF4, SvTSFromSonarNetCDF4, SvTSFromRawDatagrams
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
            return 'raw'
    return ''


def sonar_file_read(msg_queue):
    """Run code to listen to or read from the last file in the watched directory."""
    
    watch_dir = config.watchDir()
    beam_group = config.horizontalBeamGroup()
    live_data = config.liveData()

    last_file = most_recent_file(watch_dir)
    f_type = file_type(last_file)

    # TODO - fix this...
    # file_replay_*() currently uses the last file in the directory, while
    # file_listen_*() works out itself which file(s) to work on.
    #
    # beamGroup is currently only correct for netcdf files, not raw files.
    params_file = (last_file, beam_group, msg_queue)
    params_dir = (watch_dir, beam_group, msg_queue)
    
    match f_type:
        case 'sonar-netcdf4':
            if live_data:
                file_listen_netcdf(*params_dir)
            else:
                file_replay_netcdf(*params_file)
        case 'raw':
            if live_data:
                file_listen_raw(*params_dir)
            else:
                file_replay_raw(*params_file)
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
                    import h5py  # deferred to save startup time
                    f = h5py.File(mostRecentFile, 'r', libver='latest', swmr=True)
                    # f = h5py.File(mostRecentFile, 'r') # without HDF5 swmr option
                    f_previous = mostRecentFile

                    t = f[beamGroup + '/ping_time'][pingIndex]

                    if t > t_previous:  # there is a new ping in the file
                        pingTime = datetime(1601, 1, 1) + timedelta(microseconds=t/1000.0)
                        logger.info('Start reading ping from time %s', pingTime)

                        theta, tilt, sort_i = beamAnglesFromNetCDF4(f, beamGroup, pingIndex)
                        sv, ts, gains = SvTSFromSonarNetCDF4(f, beamGroup, pingIndex, tilt)

                        samInt = f[beamGroup + '/sample_interval'][pingIndex]
                        c = f['Environment/sound_speed_indicative'][()]
                        labels = f[beamGroup + '/beam']

                        t_previous = t
                        noNewDataCount = 0  # reset the count

                        logger.info('Finished reading ping from time %s', pingTime)
                        
                        # Sort everything so that the theta angles are monotonic
                        sv = sv[sort_i]
                        theta = theta[sort_i]
                        tilt = tilt[sort_i]
                        labels = labels[sort_i] 
                        
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


def file_replay_netcdf(replay_file, beamGroup, msg_queue):
    """Replay all data in the newest file. Used for testing."""
    logger.info('Reading from file: %s.', replay_file)

    # open netcdf file
    import h5py  # deferred to save startup time
    f = h5py.File(replay_file, 'r')

    t = f[beamGroup + '/ping_time']

    # Send off each ping at a sedate rate...
    for i in range(0, t.shape[0]):
        theta, tilt, sort_i = beamAnglesFromNetCDF4(f, beamGroup, i)
        sv, ts, gains = SvTSFromSonarNetCDF4(f, beamGroup, i, tilt)

        samInt = f[beamGroup + '/sample_interval'][i]
        c = f['Environment/sound_speed_indicative'][()]
        labels = f[beamGroup + '/beam']

        # convert HDF5 text to list of str
        labels = np.array([s.decode('utf-8') for s in labels])

        # Sort everything so that the theta angles are monotonic
        sv = sv[sort_i]
        theta = theta[sort_i]
        tilt = tilt[sort_i]
        labels = labels[sort_i] 

        # send the data off to be plotted
        msg_queue.put((t[i], samInt, c, sv, ts, theta, gains, labels))

        # Ping at recorded ping rate if asked
        if config.realtimeReplay() and i > 0:
            # t has units of nanoseconds
            sleep((t[i] - t[i-1])/1e9)
        else:
            sleep(config.replayPingInterval())

    f.close()

    logger.info('Finished replaying file: %s', replay_file)


def file_replay_raw(replay_file, beamGroup, msg_queue):
    pass


def file_listen_raw(watchDir: str|Path, beam_type: str, msg_queue):
    # Tested way to read from last file in a directory, keep reading as datagrams are 
    # added and then change to the next new file when no new datagrams are added

    previous_file = None

    # Check this often for files to appear in the directory if there are none
    file_wait = 2.0  # [s]
    
    # Check this often for new files to appear in the directory once we've finished
    # reading an existing file
    new_file_wait = 2.0  # [s]

    while True:
        # find the most recent file and open it.
        files = list(Path(watchDir).glob('*.raw'))

        if not files:
            print('No .raw files in the given directory. Waiting...')
            sleep(file_wait)
            continue

        sorted_files = sorted(files, key=lambda p: p.stem)
        last_file = sorted_files[-1]

        if last_file == previous_file:
            # there is no new file, we've already read through the
            # most recent file, so perhaps the sonar has finished
            # recording. We'll wait for more...
            print('No new .raw files to read. Waiting for more...')
            sleep(new_file_wait)
            continue

        previous_file = last_file

        # there is a new raw file to read
        with raw.RawSimradFile(last_file) as fid:
            # read and process datagrams in last_file as they get written to the file
            print(f'Reading datagrams from {last_file.name}')
            dg_count = 0
            while True:
                # live_read() will block waiting for a new datagram to be appended to the file.
                # If nothing gets appended after a few seconds it raises a
                # SimradFileFinished exception
                try:
                    dg = fid.live_read()
                    dg_count += 1
                    # convert ping data into Sv and TS then put into the queue
                    # to get displayed
                    sv, ts = SvTSFromRawDatagrams(dg)
                    if sv:
                        # t is ping time
                        # samInt is sample interval
                        # c is sound speed
                        # theta is beam horizontal angles
                        # gains is beam gains
                        # labels is beam labels
                        # beam values shouls be sorted so that theta is monotonic
                        t = samInt = c = theta = gains = labels = None
                        msg_queue.put(t, samInt, c, sv, ts, theta, gains, labels)
                except raw.SimradFileFinished:
                    print(f'Read {dg_count} datagrams from {last_file.name}')
                    break  # go back to the outer 'while True' loop to look for a new file.
