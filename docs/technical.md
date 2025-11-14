# Technical Manual

???+ note

    This manual is under development.

This is the technical documentation for the sonarcal program.

## Adding support for other sonars

### Beam angles and coordinate systems

This can be tricky. The sonarcal code requires that the beam angles go from -180 to 180 with 0 in the forward direction (drawn upwards on the omni echogram). Negative angles to port and positive angles to starboard.

Sonar-netCDF4 files have their beam angles given as vectors in the sonar-netCDF4 coordinate system (x-axis is forward, y-axis to starboard, and z-axis down). The sonarcal code transforms these to -180 to +180. The sonar-netCDF4 also contains beam labels that are separate from any other beam property.

The various raw files have their beam angles in degrees, not necessarily the same as sonarcal requires, so sonar-specific conversions are included in the code that reads the raw files. Raw files tend not to have explicit beam labels and instead the order (index) of the beams in the raw file is used as the beam name (so 0, 1, 2, etc).

When adding support for a new sonar it is very important to check that the beam angles and labels that sonarcal uses do correspond to the beam labels that would be used when applying a beam calibration/gain.

Sonarcal also assumes that for a given beam index, the beam to port has an index of one less and the beam to starboard has an index of one more. This assumption may be problematic if a sonar has an angle convention the opposite of this.
