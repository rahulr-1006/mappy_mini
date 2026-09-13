# Meridian LEO Ground Segment — Concept of Operations

Document MER-CONOPS-002, Revision C. Fictional reference material for the
Mini-MAPPy demonstration.

## 1. Mission Overview

The Meridian ground segment supports a single low Earth orbit spacecraft in a
sun-synchronous orbit at 512 km mean altitude, inclination 97.5 degrees. The
spacecraft completes 15.2 orbits per day. Between four and six of those orbits
produce a usable contact with the primary ground station, depending on the
ascending node drift within the repeat cycle.

## 2. Contact Windows

A usable pass is defined as one where the spacecraft is above 10 degrees
elevation for a continuous period of at least 240 seconds. Typical usable
passes last between 5 and 11 minutes, with a mean of 7.4 minutes measured over
the first 90 days of operations. Passes below 10 degrees elevation are not
scheduled for payload downlink because the atmospheric path loss and multipath
from surrounding terrain degrade the link margin below the 3 dB threshold.

The station shall acquire the spacecraft signal within 30 seconds of the
predicted acquisition of signal time. Predicted AOS is computed from a two-line
element set no older than 18 hours. Operations has observed that TLE sets older
than 36 hours produce pointing errors exceeding the antenna half-power
beamwidth, causing acquisition failure.

## 3. Crew Operations

The station is staffed by a two-person crew on a rotating 12-hour shift
pattern, providing continuous coverage. One operator holds the console
position and is responsible for pass execution; the second holds the planning
position and is responsible for schedule generation, anomaly logging, and
handover documentation.

Crew handover occurs at 0600 and 1800 local time. No pass shall be scheduled to
begin within 10 minutes either side of a handover boundary. Where an orbit
geometry forces a conflict, the planning operator defers the pass to the
following orbit and records the deferral.

## 4. Availability

The ground segment availability requirement is 99.5 percent measured over a
rolling 12-month window, where availability is the ratio of successfully
executed scheduled passes to total scheduled passes. A pass counts as failed
when fewer than 90 percent of the planned payload bytes are recovered within
the contact window or within the following two contingency passes.

Planned maintenance outages are excluded from the availability calculation when
scheduled at least 14 days in advance and confined to periods with no
scheduled contact. Unplanned outages count against availability in full.

## 5. Data Handling

Recovered payload data is written to the local store and forwarded to the
mission data centre over a terrestrial link within 15 minutes of loss of
signal. The local store retains a complete copy for 30 days as protection
against a forwarding failure. Housekeeping telemetry is forwarded in near real
time during the pass and is not buffered beyond 60 seconds.
