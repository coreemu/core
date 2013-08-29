"""
utm
===

.. image:: https://travis-ci.org/Turbo87/utm.png

Bidirectional UTM-WGS84 converter for python

Usage
-----

::

  import utm

Convert a (latitude, longitude) tuple into an UTM coordinate::

  utm.from_latlon(51.2, 7.5)
  >>> (395201.3103811303, 5673135.241182375, 32, 'U')

Convert an UTM coordinate into a (latitude, longitude) tuple::

  utm.to_latlon(340000, 5710000, 32, 'U')
  >>> (51.51852098408468, 6.693872395145327)

Speed
-----

The library has been compared to the more generic pyproj library by running the
unit test suite through pyproj instead of utm. These are the results:

* with pyproj (without projection cache): 4.0 - 4.5 sec
* with pyproj (with projection cache): 0.9 - 1.0 sec
* with utm: 0.4 - 0.5 sec

Authors
-------

* Tobias Bieniek <Tobias.Bieniek@gmx.de>

License
-------

Copyright (C) 2012 Tobias Bieniek <Tobias.Bieniek@gmx.de>

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import math

__all__ = ['to_latlon', 'from_latlon']

class OutOfRangeError(ValueError):
    pass


K0 = 0.9996

E = 0.00669438
E2 = E * E
E3 = E2 * E
E_P2 = E / (1.0 - E)

SQRT_E = math.sqrt(1 - E)
_E = (1 - SQRT_E) / (1 + SQRT_E)
_E3 = _E * _E * _E
_E4 = _E3 * _E

M1 = (1 - E / 4 - 3 * E2 / 64 - 5 * E3 / 256)
M2 = (3 * E / 8 + 3 * E2 / 32 + 45 * E3 / 1024)
M3 = (15 * E2 / 256 + 45 * E3 / 1024)
M4 = (35 * E3 / 3072)

P2 = (3 * _E / 2 - 27 * _E3 / 32)
P3 = (21 * _E3 / 16 - 55 * _E4 / 32)
P4 = (151 * _E3 / 96)

R = 6378137

ZONE_LETTERS = [
    (84, None), (72, 'X'), (64, 'W'), (56, 'V'), (48, 'U'), (40, 'T'),
    (32, 'S'), (24, 'R'), (16, 'Q'), (8, 'P'), (0, 'N'), (-8, 'M'), (-16, 'L'),
    (-24, 'K'), (-32, 'J'), (-40, 'H'), (-48, 'G'), (-56, 'F'), (-64, 'E'),
    (-72, 'D'), (-80, 'C')
]


def to_latlon(easting, northing, zone_number, zone_letter):
    zone_letter = zone_letter.upper()

    if not 100000 <= easting < 1000000:
        raise OutOfRangeError('easting out of range (must be between 100.000 m and 999.999 m)')
    if not 0 <= northing <= 10000000:
        raise OutOfRangeError('northing out of range (must be between 0 m and 10.000.000 m)')
    if not 1 <= zone_number <= 60:
        raise OutOfRangeError('zone number out of range (must be between 1 and 60)')
    if not 'C' <= zone_letter <= 'X' or zone_letter in ['I', 'O']:
        raise OutOfRangeError('zone letter out of range (must be between C and X)')

    x = easting - 500000
    y = northing

    if zone_letter < 'N':
        y -= 10000000

    m = y / K0
    mu = m / (R * M1)

    p_rad = (mu + P2 * math.sin(2 * mu) + P3 * math.sin(4 * mu) + P4 * math.sin(6 * mu))

    p_sin = math.sin(p_rad)
    p_sin2 = p_sin * p_sin

    p_cos = math.cos(p_rad)

    p_tan = p_sin / p_cos
    p_tan2 = p_tan * p_tan
    p_tan4 = p_tan2 * p_tan2

    ep_sin = 1 - E * p_sin2
    ep_sin_sqrt = math.sqrt(1 - E * p_sin2)

    n = R / ep_sin_sqrt
    r = (1 - E) / ep_sin

    c = _E * p_cos**2
    c2 = c * c

    d = x / (n * K0)
    d2 = d * d
    d3 = d2 * d
    d4 = d3 * d
    d5 = d4 * d
    d6 = d5 * d

    latitude = (p_rad - (p_tan / r) *
                (d2 / 2 -
                 d4 / 24 * (5 + 3 * p_tan2 + 10 * c - 4 * c2 - 9 * E_P2)) +
                 d6 / 720 * (61 + 90 * p_tan2 + 298 * c + 45 * p_tan4 - 252 * E_P2 - 3 * c2))

    longitude = (d -
                 d3 / 6 * (1 + 2 * p_tan2 + c) +
                 d5 / 120 * (5 - 2 * c + 28 * p_tan2 - 3 * c2 + 8 * E_P2 + 24 * p_tan4)) / p_cos

    return (math.degrees(latitude),
            math.degrees(longitude) + zone_number_to_central_longitude(zone_number))


def from_latlon(latitude, longitude):
    if not -80.0 <= latitude <= 84.0:
        raise OutOfRangeError('latitude out of range (must be between 80 deg S and 84 deg N)')
    if not -180.0 <= longitude <= 180.0:
        raise OutOfRangeError('northing out of range (must be between 180 deg W and 180 deg E)')

    lat_rad = math.radians(latitude)
    lat_sin = math.sin(lat_rad)
    lat_cos = math.cos(lat_rad)

    lat_tan = lat_sin / lat_cos
    lat_tan2 = lat_tan * lat_tan
    lat_tan4 = lat_tan2 * lat_tan2

    lon_rad = math.radians(longitude)

    zone_number = latlon_to_zone_number(latitude, longitude)
    central_lon = zone_number_to_central_longitude(zone_number)
    central_lon_rad = math.radians(central_lon)

    zone_letter = latitude_to_zone_letter(latitude)

    n = R / math.sqrt(1 - E * lat_sin**2)
    c = E_P2 * lat_cos**2

    a = lat_cos * (lon_rad - central_lon_rad)
    a2 = a * a
    a3 = a2 * a
    a4 = a3 * a
    a5 = a4 * a
    a6 = a5 * a

    m = R * (M1 * lat_rad -
             M2 * math.sin(2 * lat_rad) +
             M3 * math.sin(4 * lat_rad) -
             M4 * math.sin(6 * lat_rad))

    easting = K0 * n * (a +
                        a3 / 6 * (1 - lat_tan2 + c) +
                        a5 / 120 * (5 - 18 * lat_tan2 + lat_tan4 + 72 * c - 58 * E_P2)) + 500000

    northing = K0 * (m + n * lat_tan * (a2 / 2 +
                                        a4 / 24 * (5 - lat_tan2 + 9 * c + 4 * c**2) +
                                        a6 / 720 * (61 - 58 * lat_tan2 + lat_tan4 + 600 * c - 330 * E_P2)))

    if latitude < 0:
        northing += 10000000

    return easting, northing, zone_number, zone_letter


def latitude_to_zone_letter(latitude):
    for lat_min, zone_letter in ZONE_LETTERS:
        if latitude >= lat_min:
            return zone_letter

    return None


def latlon_to_zone_number(latitude, longitude):
    if 56 <= latitude <= 64 and 3 <= longitude <= 12:
        return 32

    if 72 <= latitude <= 84 and longitude >= 0:
        if longitude <= 9:
            return 31
        elif longitude <= 21:
            return 33
        elif longitude <= 33:
            return 35
        elif longitude <= 42:
            return 37

    return int((longitude + 180) / 6) + 1


def zone_number_to_central_longitude(zone_number):
    return (zone_number - 1) * 6 - 180 + 3


def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    m = 6367000 * c
    return m 
   
