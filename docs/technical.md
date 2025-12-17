# Technical Manual

This is the technical documentation for the Sonarcal program. It provides a brief overview of how the Sonarcal code is organised and some pointers for maintenance and further development.

The best reference for how Sonarcal works is the code and configuration in its' Github repository.

## Overview

Sonarcal is a Python program. It runs as two threads - one for the tkinter-based graphical user interface (GUI) and one that reads sonar data files. Data is passed between the threads using a queue.

The data reading thread reads the relevant sonar data files, calculates Sv and TS for all beams and sends that data to the GUI thread ping-by-ping. The main GUI display is an interative matplotlib figure in a tkinter canvas widget.

The main() function for Sonarcal is in the `controller.py` file. The `calibration_gui.py` file sets up the GUI and the `echogram_plotter.py` contains the code that generates and updates the matplotlib figure.

Sonarcal configurations are stored and saved by a class in the `configuration.py` file and the GUI for the configuration is managed by code in the `dialog_config.py` file. In a similar manner, calibration results are stored by a class in `calibration_data.py` and the GUI is in `calibration_gui.py`.

## Packaging

Generation of the Sonarcal Python package and uploading to the Python Package Index (PyPI) is done via a Github action that runs whenever a tagged commit is made to the Sonarcal repository.

Offline documentation is included in the Sonarcal package as internet access is not always available during calibrations. Online documentation is also provided and hosted on Github, being regenerated after each git push to Github. The offline documentation is only updated when a new version is uploaded to PyPI.

## Adding support for other sonars

Sonarcal supports Simrad raw data files from selected sonars and sonar-netCDF4 data files from any sonar that produces them. However, the sonar-netCDF4 format allows for different ways to convert from raw backscatter to Sv and TS and currently supports "type 1" and "type 2" equations. Support for other types will require modifications to the Sonarcal code, mainly the `SvTSFromSonarNetCDF4()` function in the `utils.py` file.

### Beam angles and coordinate systems

This can be tricky. The Sonarcal code requires that the beam angles go from -180 to 180 with 0 in the forward direction (drawn upwards on the omni echogram). Positive angles are to port, that is, the angles increase in the anticlockwise direction.

Sonar-netCDF4 files have their beam angles given as vectors in the sonar-netCDF4 coordinate system (x-axis is forward, y-axis to starboard, and z-axis down). The Sonarcal code transforms these to -180 to +180. The sonar-netCDF4 also contains beam labels that are separate from any other beam property.

The various raw files are not so consistent and sonar-specific conversions are included in the code that reads those files. Some raw files do not have explicit beam labels and instead the order (index) of the beams in the raw file is used as the beam name (so 0, 1, 2, etc).

When adding support for a new sonar it is very important to check that the beam angles and labels that Sonarcal uses do correspond to the beam labels that would be used when applying a beam calibration/gain.
