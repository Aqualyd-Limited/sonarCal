"""Manage and provide access to the sonarcal config file."""

from pathlib import Path
import configparser
import logging
from platformdirs import PlatformDirs

app_name = 'sonarcal'
logger = logging.getLogger(app_name)

def int_config(func):
    """A decorator to set and return an int from the configuration."""
    def wrapper(self, value=None):
        n = func(self, value)
        if value:
            self.sc[n] = str(value)
        return self.sc.getint(n)
    return wrapper

def float_config(func):
    """A decorator to set and return a float from the configuration."""
    def wrapper(self, value=None):
        n = func(self, value)
        if value:
            self.sc[n] = str(value)
        return self.sc.getfloat(n)
    return wrapper

def bool_config(func):
    """A decorator to set and return a boolean from the configuration."""
    def wrapper(self, value=None):
        n = func(self, value)
        if value is not None:
            self.sc[n] = str(value)
        return self.sc.getboolean(n)
    return wrapper

def str_config(func):
    """A decorator to set and return a str from the configuration."""
    def wrapper(self, value=None):
        n = func(self, value)
        if value:
            self.sc[n] = value
        return self.sc[n]
    return wrapper


class sonarcalConfig():

    def __init__(self):
        self.app_name = app_name
        self.app_author = 'Aqualyd'
        self.ini_section_name = 'sonarcal'
        
        self.dirs = PlatformDirs(appname=self.app_name, appauthor=self.app_author)

        self.config_filename = Path(self.dirs.user_config_dir)/'config.ini'
        self.config_filename.parent.mkdir(parents=True, exist_ok=True)

        self.config = configparser.ConfigParser()
        c = self.config.read(self.config_filename, encoding='utf8')

        # default values, used if an entry is not present in the config file or 
        # the config file doesn't exist.
        defaults = {'title': 'Sonar calibration',
                    'spherets': '-35.0',
                    'numPingsToShow': '100',
                    'maxRange': '50',
                    'maxSv': '-20',
                    'minSv': '-60',
                    'realtimeReplay': 'yes',
                    'replayPingInterval': '0.2',
                    'watchDir': '.',
                    'liveData': 'no',
                    'calibrating_colour': '#EE9A00',  # an orange
                    'sliderLowestSv': '-100',
                    'sliderHighestSv': '10',
                    'diffPlotYMin': '-3.0',
                    'askForWatchDir': 'yes',
                    'polarPlotRangeLabelAngle': '-22.5'
                    }

        if not c:  # config file not found, so make one
            self.config[self.ini_section_name] = defaults
            self.save_config()
        else:
            # if the config file doesn't have all of the entries in the defaults, add 
            # the missing ones in.
            if not self.config.has_section(self.ini_section_name):
                self.config.add_section(self.ini_section_name)
            added = False
            for k, v in defaults.items():
                if k not in self.config[self.ini_section_name]:
                    added = True
                    self.config[self.ini_section_name][k] = v
            if added:
                self.save_config()

        self.sc = self.config[self.ini_section_name]

    # Note: decorated functions below can get and set config values.
    # Non-decorated functions only get config values.
    def save_config(self):
        with open(self.config_filename, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)
        logger.info('Saved configuration to %s', str(self.config_filename))
    
    def appName(self) -> str:
        return self.app_name

    def appAuthor(self) -> str:
        return self.app_author

    @float_config
    def sphereTS(self, value=None):
        return 'sphereTS'

    @staticmethod
    def title() -> str:
        # Used for the main window title bar text
        return 'Sonar calibration'

    @staticmethod
    def helpURI() -> Path:
        return Path(__file__).parent/'offline-docs'/'index.html'
    
    @staticmethod
    def iconFile() -> Path:
        return Path(__file__).parent/'assets'/'logo.png'
    
    def autoSaveDir(self) -> Path:
        d = Path(self.dirs.user_data_dir)/'autosave'
        d.mkdir(parents=True, exist_ok=True)
        return d

    def logDir(self) -> Path:
        d = Path(self.dirs.user_log_dir)
        d.mkdir(parents=True, exist_ok=True)
        return d
    
    def userDocumentsDir(self) -> str:
        return self.dirs.user_documents_dir
    
    @int_config
    def numPings(self, value=None):
        return 'numPingsToShow'
    
    @float_config
    def maxRange(self, value=None):
        return 'maxRange'

    @float_config  
    def maxSv(self, value=None):
        return 'maxSv'
    
    @float_config
    def minSv(self, value=None):
        return 'minSv'

    @float_config
    def diffPlotYMin(self, value=None):
        return 'diffPlotYMin'

    @float_config
    def replayPingInterval(self, value=None):
        return 'replayPingInterval'

    @str_config
    def watchDir(self, value=None) -> str:
        return 'watchDir'

    @bool_config
    def liveData(self, value=None):
        return 'liveData'
    
    @bool_config
    def askForWatchDir(self, value=None):
        return 'askForWatchDir'

    @str_config
    def calibrating_colour(self, value=None):
        # Colour used for highlighting things when calibrating a beam
        return 'calibrating_colour'

    @int_config
    def sphereStatsOver(self, value=None):
        """Number of sphere values to use for the ping-to-ping variability."""
        return 'sphereStatsOver'

    @int_config
    def movingAveragePoints(self, value=None):
        """Number of points for moving average for smoothed plots."""
        return 'movingAveragePoints'

    @float_config
    def sliderLowestSv(self, value=None):
        "Echogram colour scheme lower threshold."
        return 'sliderLowestSv'
        
    @float_config
    def sliderHighestSv(self, value=None):
        "Echogram colour scheme upper threshold."
        return 'sliderHighestSv'

    @float_config
    def polarRangeLabelAngle(self, value=None):
        "Angle of polar echogram range labels."
        return 'polarPlotRangeLabelAngle'

# Simple way to get a singleton...
config = sonarcalConfig()
