"""Manage and provide access to the sonarcal config file."""

from pathlib import Path
import configparser
from .utils import dirs


class sonarcalConfig():

    def __init__(self):
        config_filename = Path(dirs.user_config_dir)/'config.ini'
        config_filename.parent.mkdir(parents=True, exist_ok=True)

        self.config = configparser.ConfigParser()
        c = self.config.read(config_filename, encoding='utf8')

        if not c:  # config file not found, so make one
            self.config['sonarcal'] = {'numPingsToShow': 100,
                                'maxRange': 50,
                                'maxSv': -20,
                                'minSv': -60,
                                'replayRate': 'realtime',
                                'horizontalBeamGroupPath': 'Sonar/Beam_group1',
                                'watchDir': '.',
                                'liveData': 'no'
                                }

            with open(config_filename, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)

            self.config.read(config_filename, encoding='utf8')
            
            # what to do if new config variables have been added since the .ini file 
            # was created???
    
    @staticmethod
    def title():
        # Used for the main window title bar text
        return 'Sonar calibration'

    def numPings(self):
        return self.config['sonarcal'].getint('numPingsToShow', 100)
    
    def maxRange(self):
        return self.config['sonarcal'].getfloat('maxRange', 50)
    
    def maxSv(self):
        return self.config['sonarcal'].getfloat('maxSv', -20)
    
    def minSv(self):
        return self.config['sonarcal'].getfloat('minSv', -60)

    def replayRate(self):
        return self.config['sonarcal'].get('replayRate', 'realtime')

    def horizontalBeamGroup(self):
        return self.config['sonarcal'].get('horizontalBeamGroupPath', 'Sonar/Beam_group1')

    def watchDir(self):
        return Path(self.config['sonarcal'].get('watchDir', '.'))

    def liveData(self):
        return self.config['sonarcal'].getboolean('liveData', 'no')

    @staticmethod
    def calibrating_colour():
        # Colour used for highlighting things when calibrating a beam
        return '#EE9A00'  # an orange

    @staticmethod
    def helpURI():
        return str(Path(__file__).parent/'offline-docs'/'index.html')
    
    @staticmethod
    def iconFile():
        return Path(__file__).parent/'assets'/'logo.png'