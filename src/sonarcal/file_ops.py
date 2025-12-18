from time import sleep
# import h5py
import numpy as np
from datetime import datetime, timezone
from .utils import beamAnglesFromNetCDF4, SvTSFromSonarNetCDF4, nt_time_to_datetime
from .datagram_processor import rawDatagramProcessor
import logging
from pathlib import Path
from .configuration import config
from .raw_parser import simrad_raw_file as raw


logger = logging.getLogger(config.appName())

def most_recent_file(watch_dir: Path, wait_interval: float=5.0):
    """Get the most recent .nc or .raw file in the directory."""

    while True:
        files = sorted(list(watch_dir.glob('*.nc')) + list(watch_dir.glob('*.raw')))

        if files:
            return files[-1]

        logger.info("No .nc or .raw files found in '%s'", watch_dir)
        sleep(wait_interval)


def file_type(filename: Path):
    """Works out what sonar the data file is from and what format it is."""
    
    match filename.suffix:
        case '.nc':
            return 'sonar-netcdf4'
        case '.raw':
            return 'simrad-raw'
    return ''


def sonar_file_read(msg_queue, reload_event):
    """Run code to listen to or read from the last file in the watched directory."""
    
    # The reload_event is used to restart listening to or reading from
    # files and is set when the data directory and/or live data switch is changed.
    
    while True:
        reload_event.clear()  # because we've noticed it was set (or it's the first time through)
        watch_dir = Path(config.watchDir())
        live_data = config.liveData()

        if live_data:
            logger.info('Listening for pings in %s', watch_dir)
        else:                    
            logger.info('Replaying files in %s', watch_dir)

        last_file = most_recent_file(watch_dir)

        # The listen functions only return if reload_event is set - they wait for 
        # new data indefinitely otherwise.
        # The replay functions replay all the files in the directory and don't return,
        # but will abandon this and return if reload_event is set.

        match file_type(last_file):
            case 'sonar-netcdf4':
                logger.info('File type is sonar-netCDF4')
                if live_data:
                    file_listen_netcdf(watch_dir, msg_queue, reload_event)
                else:
                    file_replay_netcdf(watch_dir, msg_queue, reload_event)
            case 'simrad-raw':
                logger.info('File type is Simrad raw')
                if live_data:
                    file_listen_raw(watch_dir, msg_queue, reload_event)
                else:
                    file_replay_raw(watch_dir, msg_queue, reload_event)
            case _:
                logger.error('Unsupported sonar file type')

        logger.info('File listening and replaying ended - restarting')


def get_sonar_model(hdf_attrs: dict) -> str:
    """Get the sonar model name - some older Simrad files have it in a different place."""
    product_name = hdf_attrs['sonar_model'].decode('utf-8')

    if 'TBD:sonar_model' in product_name:
        product_name = hdf_attrs['sonar_software_name'].decode('utf-8')

    return product_name

def shorten_beam_label(label: str) -> str:
    """Shorten the beam label and remove unnecessary text."""
    
    # Simrad sonars have beam labels of the form 'Horizontal-H01', 
    # 'Vertical-H01', etc. 
    return label.replace('Horizontal-', '').replace('Vertical-', '')

def get_horiz_beam_group(hdf, log=True) -> str:
    """Work out which beam group has the horizontal beam data."""

    # List of all Beam_group paths in the Sonar group file
    groups = ['Sonar/' + k for k in (hdf['Sonar'].keys()) if 'Beam_group' in k]
    modes = [hdf[g].attrs['beam_mode'].decode('utf-8') for g in groups]

    # Some info that may be useful in the log when things don't work out as expected
    if log:
        for g, m in zip(groups, modes):
            logger.info('%s contains %s beams', g, m)

    # Use the first horizontal beam group
    for g, m in zip(groups, modes):
        if m == 'horizontal':
            return g

    logger.error('No horizontal beam group found in current .nc file')
    return ''

def file_listen_netcdf(watchDir, msg_queue, reload_event):
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
    waitInterval = 0.25  # [s] time period between checking for new pings
    waitIntervalFile = 1.0  # [s] time period between checking for new files
    errorWaitInterval = 0.2  # [s] time period to wait if there is a file read error

    pingIndex = -1  # which ping to read. -1 means the last ping, -2 the second to last ping

    t_previous = datetime(1970, 1, 1, tzinfo=timezone.utc)  # timestamp of previous ping
    f_previous = ''  # previously used file

    while True:  # could add a timeout on this loop...
        mostRecentFile = most_recent_file(watchDir, waitIntervalFile)
        
        if reload_event.is_set():
            return

        if mostRecentFile == f_previous:  # no new file was found
            logger.debug('No newer file found. Will try again in %s s.', str(waitIntervalFile))
            sleep(waitIntervalFile)  # wait and try again
        else:
            logger.info('Listening to %s', mostRecentFile.name)
            first_ping = True
            noNewDataCount = 0

            while noNewDataCount <= maxNoNewDataCount:
                # open netcdf file
                try:
                    import h5py  # deferred to save startup time
                    f = h5py.File(mostRecentFile, 'r', libver='latest', swmr=True)
                    # f = h5py.File(mostRecentFile, 'r') # without HDF5 swmr option

                    if first_ping:
                        product_name = get_sonar_model(f['Sonar'].attrs)
                        logger.info('File contains data from a %s sonar', product_name)
                        beam_group = get_horiz_beam_group(f)

                    f_previous = mostRecentFile

                    t = nt_time_to_datetime(f[beam_group + '/ping_time'][pingIndex]/100)

                    if t > t_previous:  # there is a new ping in the file

                        theta, tilts = beamAnglesFromNetCDF4(f, beam_group, pingIndex)
                        sv, ts, gains = SvTSFromSonarNetCDF4(f, beam_group, pingIndex, tilts)

                        samInt = f[beam_group + '/sample_interval'][pingIndex]
                        c = f['Environment/sound_speed_indicative'][()]
                        labels = f[beam_group + '/beam']

                        # convert HDF5 text to list of str and shorten if needed
                        labels = np.array([shorten_beam_label(s.decode('utf-8')) for s in labels])

                        t_previous = t
                        noNewDataCount = 0  # reset the count
                       
                        # send the data off to be plotted
                        msg_queue.put((first_ping, t, samInt, c, sv, ts, theta, tilts, gains, labels))
                    else:
                        noNewDataCount += 1
                        if noNewDataCount > maxNoNewDataCount:
                            logger.info('Finished listening to %s', mostRecentFile.name)
                            logger.info('Waiting for a new file to listen to')
                    first_ping = False
                    f.close()

                    if reload_event.is_set():
                        return

                    # try this instead of opening and closing the file
                    # t.id.refresh(), etc

                    sleep(waitInterval)
                except OSError:
                    f.close()  # just in case...
                    logger.exception('OSError when reading netCDF4 file')
                    logger.info('Ignoring the OSError exception and trying again.')
                    sleep(errorWaitInterval)


def file_replay_netcdf(watchDir, msg_queue, reload_event):
    """Replay all data in the directory. Used for testing."""

    files = list(watchDir.glob('*.nc'))
    logger.info('Number of files to replay: %d', len(files))

    if not files:
        logger.info('No .nc files in %s', watchDir)

    first_ping = True

    for file in sorted(files, key=lambda p: p.stem):
        logger.info('Replaying %s', file.name)

        # open netcdf file
        import h5py  # deferred to save startup time
        f = h5py.File(file, 'r')

        product_name = get_sonar_model(f['Sonar'].attrs)
        logger.info('File contains data from a %s sonar', product_name)
        beam_group = get_horiz_beam_group(f)

        t = f[beam_group + '/ping_time']

        # Send off each ping at a sedate rate...
        for i in range(0, t.shape[0]):
            theta, tilts = beamAnglesFromNetCDF4(f, beam_group, i)
            sv, ts, gains = SvTSFromSonarNetCDF4(f, beam_group, i, tilts)

            samInt = f[beam_group + '/sample_interval'][i]
            c = f['Environment/sound_speed_indicative'][()]
            labels = f[beam_group + '/beam']

            # convert HDF5 text to list of str and shorten if needed
            labels = np.array([shorten_beam_label(s.decode('utf-8')) for s in labels])

            # send the data off to be plotted
            ping_time = nt_time_to_datetime(t[i]/100)
            msg_queue.put((first_ping, ping_time, samInt, c, sv, ts, theta, tilts, gains, labels))
            first_ping = False

            if reload_event.is_set():
                f.close()
                return

            sleep(config.replayPingInterval())

        f.close()
    
    logger.info('Finished replaying files in %s', watchDir)
    
    # if we return we'll immediately get run again, so wait for a reload event, otherwise
    # just do nothing.
    while True:
        if reload_event.is_set():
            return
        sleep(1.0)


def file_listen_raw(watchDir: Path, msg_queue, reload_event):
    """Replay live files."""

    previous_file = None

    # Check this often for files to appear in the directory if there are none
    file_wait = 2.0  # [s]
    
    # Check this often for new files to appear in the directory once we've finished
    # reading an existing file
    new_file_wait = 2.0  # [s]

    while True:
        files = list(watchDir.glob('*.raw'))

        if reload_event.is_set():
            return

        if not files:
            logger.debug('No .raw files in %s. Waiting...', watchDir)
            sleep(file_wait)
            continue

        sorted_files = sorted(files, key=lambda p: p.stem)
        last_file = sorted_files[-1]

        if last_file == previous_file:
            # there is no new file, we've already read through the
            # most recent file, so perhaps the sonar has finished
            # recording. We'll wait for more...
            logger.debug('No new .raw files to read. Waiting for more...')
            sleep(new_file_wait)
            continue

        previous_file = last_file
        first_ping = True

        logger.info('Listening to %s', last_file.name)

        # there is a new raw file to read
        with raw.RawSimradFile(last_file) as fid:
            proc = rawDatagramProcessor()
            # read and process datagrams in last_file as they get written to the file

            while True:
                # live_read() will block waiting for a new datagram to be appended to the file.
                # If nothing gets appended after a few seconds it raises a
                # SimradFileFinished exception
                try:
                    dg = fid.live_read(eof_retries=7)
                    
                    if proc.add_datagram(dg):  # returns True when a processed ping is available
                        if first_ping:
                            logger.info('File contains data from a %s sonar', proc.product_name)

                        msg_queue.put((first_ping,
                                      proc.ping_time, proc.sample_interval, proc.sound_speed,
                                      proc.sv, proc.ts, proc.theta, proc.tilts,
                                      proc.gain_rx, proc.labels))

                        first_ping = False

                        if reload_event.is_set():
                            return

                        # we want to read the file as quick as possible, but no too fast
                        # that the GUI becomes unresponsive.
                        sleep(0.25)
                except raw.SimradFileFinished:
                    break  # go back to the outer 'while True' loop to look for a new file.
                
        logger.info('Finished listening to %s', last_file.name)
        logger.info('Waiting for a new file to listen to')


def file_replay_raw(watchDir: Path, msg_queue, reload_event):
    """Replays raw files."""

    files = list(watchDir.glob('*.raw'))
    logger.info('Number of files to replay: %d', len(files))

    if not files:
        logger.info('No .raw files in %s', watchDir)

    first_play_ping = True

    for file in sorted(files, key=lambda p: p.stem):
        first_ping_from_file = True
        logger.info('Replaying %s', file.name)

        with raw.RawSimradFile(file) as fid:
            proc = rawDatagramProcessor()

            while True:
                try:
                    dg = fid.read(1)

                    if proc.add_datagram(dg):  # returns True when a processed ping is available
                        if first_ping_from_file:
                            logger.info('File contains data from a %s sonar', proc.product_name)
                        first_ping_from_file = False
                        msg_queue.put((first_play_ping,
                                      proc.ping_time, proc.sample_interval, proc.sound_speed,
                                      proc.sv, proc.ts, proc.theta, proc.tilts, proc.gain_rx,
                                      proc.labels))
                        first_play_ping = False
                        if reload_event.is_set():
                            return
                        sleep(config.replayPingInterval())
                except raw.SimradEOF:
                    break  # go back to the outer 'while True' loop for the next file
    
    logger.info('Finished replaying files in %s', watchDir)

    # if we return we'll immediately get run again, so wait for a reload event, otherwise
    # just do nothing.
    while True:
        if reload_event.is_set():
            return
        sleep(1.0)
