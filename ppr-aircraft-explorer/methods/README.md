# Additional aircraft activity checks

Contains information from ADSB.lol, made available under the Open Database License (ODbL) v1.0. Query service: ClickHouse / adsb.exposed. This independent activity transformation and its output are offered under ODbL v1.0. Original registry records remain separate; this method grants no rights in those records.

This directory offers the complete transformation method under ODbL section 4.6(b), rather than a bulk copy of the underlying trajectory database. It contains no registry downloads or raw tracks. The full selection query, grouping, sampling assumptions and filters are in [adsb_activity.py](adsb_activity.py).

## Source selection

The source table is `planes_mercator_sample100`, the materialized 1% point sample documented by ClickHouse. The exact query restricts `data_source = 'adsb.lol'` and UTC dates from 1 January through 30 September 2026. ADS-B Exchange evaluation data and airplanes.live data are excluded. Registration input is supplied for each lookup. Output is an independent summary keyed by ICAO24, source registration and type, without registry content.

## Complete transformation

The code rejects invalid hexadecimal identities, nonfinite coordinates, dates outside the window, duplicate points and stale positions (`flags & 1`). A qualifying fragment requires three distinct positions with the same nonempty callsign; altitude at least 1,000 feet; ground speed at least 80 knots; a span of at least five minutes; gaps no greater than 20 minutes; and at least 10 nautical miles of maximum displacement from its first point. Implied mean speed cannot exceed 750 knots. The code produces counts, dates and example endpoints.

A fragment supports airborne movement, not an independently verified completed flight. This sample cannot estimate total flights, utilization, absence of activity, an exact return-to-service date or lease availability. An aircraft can fly yet fail the conservative gates in a sparse sample.

## Separate identity review

The Explorer joins summaries with the registry for identity review while retaining the original 2025 cohort and dated outcomes. Additional activity has its own `airborne_observed` classification and is never added to the number of OPDI flight records. US links use FAA manufacturer/model, serial and Mode-S checks, with cancellation-date bounds for deregistered identities. China links remain provisional registration/type/ICAO24 matches; independently corroborated serial numbers are identified in individual records.

Run `python3 adsb_activity.py points.json > summary.json`. Input is a point list, a ClickHouse JSON response, or that response wrapped in a `response` key. `query(registrations)` constructs the exact source query. No undisclosed external contents are added by the ADS-B transformation.

Sources: [ADSB.lol historical archive](https://github.com/adsblol/globe_history_2026), [ODbL v1.0](https://opendatacommons.org/licenses/odbl/1.0/), [ClickHouse source and schema](https://github.com/ClickHouse/adsb.exposed).
