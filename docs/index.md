# User Manual

!!! info

    If you opened this documentation from the Sonarcal program you will be reading the offline version. The online version is available [here](https://aqualyd-limited.github.io/sonarCal/).

## Introduction

This is the user documentation for Sonarcal, a program to assist with calibrating fisheries sonars using the target sphere method. Sonarcal currently supports these sonars and file formats:

|Brand|Model|Supported file format|
|---|---|---|
|Furuno|FSV25|sonar-netCDF4|
|Simrad|SU90|sonar-netCDF4|
|Simrad|SX90|sonar-netCDF4|
|Simrad|CS90|raw & sonar-netCDF4**|
|Simrad|SN90|raw & sonar-netCDF4**|

(** = requires testing)

Other sonars that output sonar-netCDF4 files may also work, but there can often be small adjustments needed for full support. Contact the developer via Sonarcal's [GitHub](https://github.com/Aqualyd-Limited/sonarCal) page for further information.

The current form of this program was funded by [AZTI](https://www.azti.es/en/). Earlier versions were developed while the author was employed at the Norwegian [Institute of Marine Research](https://www.hi.no).

## Installation

Sonarcal requires Python version 3.11 or higher. If you are unfamiliar with installing and running Python programs we recommend using `uv` (see [below](#using-uv)).

Sonarcal is installed from the command line via:

    pip install sonarcal

and upgraded via:

    pip install sonarcal --upgrade

The latest version of Sonarcal will always be listed [github](https://github.com/Aqualyd-Limited/sonarCal/releases). Sonarcal has been developed on Windows and is tested on Linux and MacOS. It may work on other operating systems.

### Using `uv`

[uv](https://docs.astral.sh/uv/) can be used to install Python and Sonarcal and then to run Sonarcal. uv creates a Python installation just for Sonarcal (it is independent of all other Python installations on your computer).

Install uv using these [instructions](https://github.com/astral-sh/uv?tab=readme-ov-file#installation), then install Sonarcal with this command:

    uv tool install sonarcal

and run Sonarcal with this command:

    uv tool run sonarcal

uv's installation of Sonarcal can be upgraded with this command:

    uv tool upgrade sonarcal

## How to use

Sonarcal is started from a command line with:

    sonarcal

(or if using uv, the command is `uv tool run sonarcal`). It make take a few seconds to start, after which the Sonarcal window will appear.

If there are suitable sonar files in the configured data directory[^1], the program will start to replay them. Replay happens in two ways:

Live data enabled

:    The last file in the directory will be replayed[^2] and then any new data added to that file will also be replayed. If a newer file appears, that will be replayed too.

[^1]: Sonarcal can be configured (via the Config dialog) to always ask for the data directory when starting.
[^2]: Just the last ping is replayed for sonar-netCDF4 files.

Live data disabled

:    All files in the directory will be replayed in chronological order.

![Main screen](assets/screenshot.png){ align=right }
/// caption
The main operation screen.
///

Each new ping is displayed in the polar plot to the left. The three centre plots show an echogram of the data from the three sonar beams at and adjacent to the beam line (the black radial line in the polar plot).

The target strength of the maximum amplitude echo on the three beams between the range rings is shown in the plots to the right. The upper plot uses **black** lines for the selected beam, <span style="color:red">**red**</span> for the beam to port, and <span style="color:green">**green**</span> for starboard. The lower plot shows the difference in amplitude between the echo in the centre beam and the two adjacent beams.

The plots also include smoothed lines to aid in seeing trends in the sphere amplitude - these use a thicker line style than the raw echo amplitudes.

The beam being calibrated is selected by using the mouse to click on and drag the black radial line on the polar plot. The range over which the sphere is detected can be changed by clicking on and dragging the two range rings in the polar plot.

The echogram colour thresholds can be adjusted by clicking and dragging on the slider to the left of the polar plot.

## Calibrating

When using Sonarcal to calibrate, follow these steps:

- Start Sonarcal
- In the Config dialog:
  - Set the calibration [sphere TS](#sphere-target-strength)
  - Set the sonar data directory to where the sonar will be recording data files
  - Turn on the use of live data
  - Close and restart Sonarcal for these changes to take effect
- Repeat for multiple beams:
  - Move the beam line and range rings to select the beam and ranges
  - Locate the sphere on-axis of a beam using the sphere amplitude plots to assist
  - Tick the `on-axis` box when the sphere is on-axis
  - Monitor the results in the Results dialog box
  - Untick the `on-axis` box when sufficient data have been collected for the beam

Every time that the `on-axis` box is unticked all calibration results are saved to a backup file. The results can also be exported at any time using the `Save` button on the results dialog box - you will be prompted for a directory and filename for saving.

The beam being calibrated is highlighted in orange in the results dialog box and the beam line on the polar plot can not be moved while calibrating.

## Using the calibration results

Sonarcal calculates a `calibration offset` for each calibrated beam. This is the value in dB that should be added to the TS or S~v~ output from the sonar to get a calibrated result.

Both Simrad raw files and sonar-netCDF4 files contain a transducer gain value that is used to convert raw data into TS and S~v~. It is not always correct to just add the calibration offset to this gain value - it depends on how the relevant raw to TS and S~v~ equations use the gain. For example, raw files use double the gain value, while the process for sonar-netCDF4 files depends on the type of conversion equation used (see Chapter 4 in the sonar-netCDF4 document for details).

## Sphere target strength

Sonarcal requires you to enter calibration sphere target strength (TS) into the Configuration dialog box. Make sure to do this before you start using Sonarcal to collect data.

The TS is derived from the sphere size and material and the temperature and salinity of the water surrounding the sphere. There are a few options to calculate TS from these:

- [NOAA sphere calculator](https://www.fisheries.noaa.gov/data-tools/standard-sphere-target-strength-calculator) - an online app
- [SphereTS](https://github.com/gavinmacaulay/SphereTS) - a Python app that runs locally
- [TS_package](https://github.com/gavinmacaulay/calibration-code/tree/master/matlab/TS_Package) - Matlab code
- [echoSMs](https://ices-tools-dev.github.io/echoSMs/) - contains an elastic sphere scattering model applicable to calibration spheres
