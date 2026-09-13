# Meridian Ground Station Site and Facility Specification

Document MER-SPEC-007, Revision B. Fictional reference material for the
Mini-MAPPy demonstration.

## 1. Site Environment

The reference site sits at 1,240 metres elevation. Design environmental
extremes are minus 25 to plus 45 degrees Celsius ambient, sustained wind of
35 metres per second, and gust of 52 metres per second. The antenna shall
survive the gust condition in the stow position and shall meet the pointing
specification in sustained wind up to 15 metres per second.

Ice accretion of up to 25 mm radial on the reflector surface is credible at
this site. The reflector carries a de-icing provision rated to clear that
accretion within 45 minutes at minus 10 degrees Celsius ambient.

## 2. Electrical Power

Prime power is a utility feed at 400 V three phase, 50 Hz. Measured supply
availability at the site is 99.2 percent, which alone is insufficient for the
99.5 percent ground segment availability requirement.

An uninterruptible power supply carries the full station load for 20 minutes.
A diesel generator starts automatically on loss of utility power and reaches
rated output within 45 seconds. Fuel storage supports 72 hours of continuous
operation at full station load. The 20 minute UPS holding time is sized to
cover generator start, a single restart attempt, and an orderly shutdown of the
data store if both attempts fail.

Station load is 42 kW nominal and 58 kW peak, where peak coincides with
transmit operation, de-icing, and full cooling demand.

## 3. Physical Security

The site perimeter is fenced with controlled vehicle access. Entry to the
equipment building requires badge authentication and is logged. The antenna
pedestal enclosure and the equipment room are separately controlled zones.

Access events are retained for 24 months. An access event comprises the
credential identifier, the zone, the timestamp to one second resolution, and
whether entry was granted or refused.

## 4. Audit Logging

The station logs command transmissions, configuration changes, schedule
modifications, and operator authentication events. Log records are written to
append-only storage and replicated off site within 5 minutes of creation.

Each command log record captures the command mnemonic, the originating
operator, the spacecraft time of execution if applicable, and the ground time
of transmission to one millisecond resolution. Retention is 7 years for
command records and 24 months for configuration and authentication records.

## 5. Cooling

The equipment room maintains 18 to 27 degrees Celsius and 20 to 60 percent
relative humidity non-condensing. Cooling capacity is sized for the 58 kW peak
load at the 45 degree Celsius ambient design extreme, with N+1 redundancy on
the chiller units.
