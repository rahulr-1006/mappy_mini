# Meridian Site B: Candidate Site Survey

Document MER-SURVEY-042, Revision A. Fictional reference material for the
Mini-MAPPy demonstration. Upload this during the demo to show a new document
changing what the assistant retrieves.

## 1. Purpose

Records the survey of the Kestrel Ridge candidate location for the Meridian
follow-on ground station, and the ways it differs from the reference site
described in MER-SPEC-007.

## 2. Location and Terrain

Kestrel Ridge sits at 2,310 metres elevation, roughly 1,070 metres higher than
the reference site. The horizon profile is obstructed to the north east by a
ridge line rising to 7 degrees elevation across a 40 degree azimuth sector.

Passes whose acquisition point falls inside the obstructed sector cannot use
the 10 degree elevation mask defined in MER-CONOPS-002. For those passes the
usable mask is 9 degrees above the ridge line, an effective 16 degrees, which
shortens the contact by between 60 and 140 seconds.

## 3. Radio Frequency Environment

A civil air surveillance radar operates 18 kilometres south west of the ridge,
transmitting in the 2700 to 2900 MHz band. Measured spurious emission in the
2200 to 2290 MHz downlink band reaches minus 138 dBm per hertz at the survey
point, which erodes 0.7 dB from the downlink margin defined in MER-ICD-014.

The 3.0 dB margin allocation therefore falls to 2.3 dB at Kestrel Ridge unless
a filter is fitted ahead of the low noise amplifier. A cavity filter with 40 dB
rejection at 2700 MHz recovers 0.6 dB of the loss at a cost of 0.1 dB insertion
loss in band.

## 4. Environment

Design environmental extremes at Kestrel Ridge are minus 34 to plus 38 degrees
Celsius, a sustained wind of 41 metres per second, and a gust of 67 metres per
second. Both wind figures exceed the reference site design case.

Ice accretion of up to 40 mm radial is credible, against 25 mm at the reference
site. The existing de-icing provision, rated to clear 25 mm within 45 minutes,
does not meet the Kestrel Ridge case and requires re-rating.

## 5. Utilities

No utility power feed reaches the ridge. The nearest three phase connection
terminates 6.2 kilometres away at the valley substation. Options are a
dedicated spur at an estimated 14 week lead time, or full time generator
operation with a fuel resupply interval of 9 days at the 42 kW nominal station
load.

Terrestrial data connectivity is a single microwave hop to the valley, with no
diverse path available. The 15 minute payload forwarding requirement in
MER-CONOPS-002 cannot be met during a hop outage, and the 30 day local
retention becomes the only protection.

## 6. Survey Findings

- The elevation mask assumption does not hold in the obstructed sector.
- Downlink margin is eroded by an off site radar and needs filtering.
- Wind and ice design cases both exceed the reference site.
- There is no diverse terrestrial path and no utility power.
