# Meridian Spacecraft-to-Ground RF Interface Control Document

Document MER-ICD-014, Revision F. Fictional reference material for the
Mini-MAPPy demonstration.

## 1. Scope

Defines the radio frequency interface between the Meridian spacecraft and the
ground station antenna subsystem. Covers frequency allocation, modulation,
coding, and link budget allocations for both directions.

## 2. Frequency Allocation

Downlink occupies 2200 to 2290 MHz in the space research service allocation.
The assigned centre frequency is 2245.5 MHz with an occupied bandwidth of
4.2 MHz at the 99 percent power containment point.

Uplink occupies 2025 to 2110 MHz. The assigned centre frequency is
2067.5 MHz with an occupied bandwidth of 180 kHz.

## 3. Data Rates

Payload downlink operates at 2.0 Mbps using QPSK modulation with rate 1/2
convolutional coding and a concatenated Reed-Solomon (255,223) outer code.
Housekeeping telemetry is multiplexed into the same downlink at 32 kbps.

Command uplink operates at 64 kbps using BPSK modulation with rate 1/2
convolutional coding. Command frames conform to CCSDS 232.0-B telecommand
space data link protocol.

## 4. Link Budget

The downlink budget allocates 3.0 dB of margin at 10 degrees elevation under
clear-sky conditions at the reference site. The budget assumes a ground station
figure of merit of 18.5 dB/K and a spacecraft EIRP of 12 dBW.

Rain attenuation at S-band is modest but not negligible. The budget carries a
0.4 dB allocation for rain at the 99.9 percentile rate for the reference site
climate zone. Sites in higher rain zones require a revised budget.

## 5. Antenna Pointing

The ground antenna half-power beamwidth is 1.8 degrees at the downlink centre
frequency for the 4.5 metre reflector baseline. Pointing error shall remain
within 0.1 degrees root mean square during tracking to hold the pointing loss
allocation of 0.2 dB.

Pointing is computed from an orbit propagator and corrected by a monopulse
autotrack loop once the received signal exceeds the autotrack acquisition
threshold of minus 105 dBm. Programme track is used below that threshold and
during keyhole transits where the required azimuth rate exceeds the pedestal
slew capability.

## 6. Keyhole Constraint

An elevation-over-azimuth pedestal cannot track through zenith. For passes with
a maximum elevation above 84 degrees the azimuth rate demand exceeds the
pedestal limit of 12 degrees per second. Such passes are flagged in the
schedule and the operator accepts a brief tracking dropout near the maximum
elevation point, or the pass is planned with a deliberate pointing offset.
