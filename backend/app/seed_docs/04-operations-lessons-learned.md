# Meridian Ground Segment: Operations Lessons Learned, Year One

Document MER-OPS-031, Revision A. Fictional reference material for the
Mini-MAPPy demonstration.

## 1. Purpose

Captures findings from the first twelve months of Meridian ground segment
operations, for use in requirement updates and in the design of follow-on
stations.

## 2. Acquisition Failures

Thirty-one acquisition failures occurred in the reporting period against 2,180
scheduled passes, a rate of 1.4 percent. Root cause distribution:

- Stale orbit data, 19 events. In every case the two-line element set in use
  exceeded 24 hours of age. The 18 hour refresh requirement was in place but
  the scheduler did not enforce it, and the operator had no indication that the
  element set had aged out.
- Pedestal keyhole transits, 7 events. All seven passes had maximum elevation
  above 84 degrees and were not flagged in the schedule.
- Receiver configuration left from a prior pass, 4 events.
- Genuine equipment fault, 1 event.

The dominant finding is that the requirement existed and the tooling did not
enforce it. A requirement that depends on an operator remembering a threshold
is a requirement that will be violated at a rate proportional to workload.

## 3. Availability Performance

Measured availability for the reporting period was 99.34 percent against the
99.5 percent requirement. The shortfall is attributable to a single 14 hour
outage in month seven caused by a chiller failure that forced a thermal
shutdown of the transmit chain.

The chiller units were specified with N+1 redundancy. The failure took out the
shared coolant distribution manifold, which was single string and therefore
outside the redundancy the specification described. Redundancy specified at the
unit level does not deliver redundancy at the function level.

## 4. Data Recovery

Payload data recovery averaged 99.7 percent of planned bytes per successful
pass. Twelve passes recovered between 90 and 99 percent, and were counted as
successful under the 90 percent threshold. Four passes fell below 90 percent
and were recovered on a contingency pass within the same day.

The 30 day local retention proved its value twice, when a terrestrial
forwarding link outage lasting 40 hours would otherwise have lost two days of
payload data.

## 5. Crew Workload

The planning position averaged 4.2 hours of active work per 12 hour shift. The
console position averaged 2.8 hours, concentrated in the pass windows. Both
positions reported that the handover exclusion window of 10 minutes is too
narrow when a pass runs long, and recommend widening it to 15 minutes.

## 6. Recommendations

- Enforce the orbit data freshness threshold in the scheduling tool rather than
  in procedure.
- Flag keyhole passes automatically at schedule generation.
- Re-specify cooling redundancy at the function level, including distribution.
- Widen the handover exclusion window to 15 minutes.
