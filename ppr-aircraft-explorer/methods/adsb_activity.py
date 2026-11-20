"""Complete ADSB.lol activity transformation for the Explorer, ODbL-1.0.

Source contents: ADSB.lol, ODbL-1.0, via ClickHouse's adsb.exposed.
This module processes an independent ADS-B sidecar. Registry identity checks
and any commercial-availability decision are separate. It does not count flights.
Run: python3 adsb_activity.py points.json > activity-summary.json
Input: JSON list of points, or ClickHouse JSON response with a `data` list.
"""
import collections
from datetime import datetime, timezone
import json
import math
import re
import sys

RULES = dict(minPoints=3, minSpanSeconds=300, maxInterpointGapSeconds=1200,
             minDisplacementNm=10, minAltitudeFt=1000, minGroundSpeedKnots=80,
             maxImpliedSpeedKnots=750, sameNonemptyCallsign=True,
             rejectStalePositionFlag=True, minDistinctPositions=3)
SOURCE = 'adsb.lol'
START, END = '2026-01-01', '2026-10-01'


def query(registrations):
    """Exact source selection; 1% is the materialized source table's sampling."""
    tails = sorted(set(registrations))
    if any(not re.fullmatch(r'[A-Za-z0-9-]{1,16}', r) for r in tails):
        raise ValueError('Invalid registration input')
    quoted = ','.join("'" + r + "'" for r in tails)
    return ("SELECT icao,r,t,time,lat,lon,altitude,ground_speed,aircraft_flight,flags,data_source "
            "FROM planes_mercator_sample100 WHERE data_source='adsb.lol' "
            "AND date>='2026-01-01' AND date<'2026-10-01' AND bitAnd(flags,1)=0 "
            "AND r IN (" + quoted + ") ORDER BY icao,time")


def distance(a, b):
    p1, p2 = math.radians(a['lat']), math.radians(b['lat'])
    dp, dl = p2-p1, math.radians(b['lon']-a['lon'])
    z = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 3440.065*2*math.asin(min(1, math.sqrt(z)))


def summarize(points):
    groups = collections.defaultdict(list)
    seen = set()
    for original in points:
        p = dict(original)
        if p.get('data_source') != SOURCE or not START <= p.get('time', '')[:10] < END:
            continue
        h = str(p.get('icao', '')).lower()
        if not re.fullmatch(r'[0-9a-f]{6}', h) or int(p.get('flags', 0)) & 1:
            continue
        if not all(isinstance(p.get(k), (int, float)) and math.isfinite(p[k])
                   for k in ('lat', 'lon', 'altitude', 'ground_speed')):
            continue
        if not -90 <= p['lat'] <= 90 or not -180 <= p['lon'] <= 180:
            continue
        key = (h, p.get('r', ''), p.get('t', ''))
        duplicate = key + (p['time'], p['lat'], p['lon'], p.get('aircraft_flight', ''))
        if duplicate in seen:
            continue
        seen.add(duplicate)
        p['_stamp'] = datetime.fromisoformat(p['time']).replace(tzinfo=timezone.utc).timestamp()
        groups[key].append(p)
    results = []
    for (h, reg, typ), values in sorted(groups.items()):
        values.sort(key=lambda p: p['_stamp'])
        airborne = [p for p in values if p['altitude'] >= 1000 and p['ground_speed'] >= 80]
        calls = collections.defaultdict(list)
        for p in airborne:
            call = (p.get('aircraft_flight') or '').strip()
            if call:
                calls[call].append(p)
        accepted = []

        def segment(seq, call):
            if len(seq) < 3 or len({(p['lat'], p['lon']) for p in seq}) < 3:
                return
            span = seq[-1]['_stamp'] - seq[0]['_stamp']
            if span < 300:
                return
            moved = max(distance(seq[0], p) for p in seq[1:])
            if moved < 10 or moved/span*3600 > 750:
                return
            first, last = seq[0], seq[-1]
            accepted.append(dict(callsign=call, first=first['time'], last=last['time'],
                points=len(seq), pointCount=len(seq), durationMinutes=round(span/60, 2),
                displacementNm=round(moved, 2),
                firstPosition={k:first[k] for k in ('lat','lon','altitude','ground_speed')},
                lastPosition={k:last[k] for k in ('lat','lon','altitude','ground_speed')}))
        for call, seq in sorted(calls.items()):
            current = []
            for p in seq:
                if current and not 0 < p['_stamp']-current[-1]['_stamp'] <= 1200:
                    segment(current, call)
                    current = []
                current.append(p)
            segment(current, call)
        results.append(dict(icao24=h, registration=reg, typecode=typ,
            sourcePoints=len(values), airbornePoints=len(airborne),
            sourceFirst=values[0]['time'], sourceLast=values[-1]['time'],
            qualifiedSegmentCount=len(accepted), qualifiedSegments=accepted))
    return dict(metadata=dict(source='ADSB.lol via ClickHouse adsb.exposed',
        sourceUrl='https://github.com/ClickHouse/adsb.exposed', license='ODbL-1.0',
        windowStart=START, windowEnd='2026-09-30', sampleFraction=.01, rules=RULES), records=results)


if __name__ == '__main__':
    with open(sys.argv[1], encoding='utf-8') as stream:
        payload = json.load(stream)
    if isinstance(payload, dict):
        payload = payload.get('response', payload).get('data', [])
    json.dump(summarize(payload), sys.stdout, separators=(',', ':'))
