#
# CORE
# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
location.py: definition of CoreLocation class that is a member of the
Session object. Provides conversions between Cartesian and geographic coordinate
systems. Depends on utm contributed module, from
https://pypi.python.org/pypi/utm (version 0.3.0).
'''

from core.conf import ConfigurableManager
from core.api import coreapi
from core.misc import utm

class CoreLocation(ConfigurableManager):
    ''' Member of session class for handling global location data. This keeps
        track of a latitude/longitude/altitude reference point and scale in
        order to convert between X,Y and geo coordinates.
        
        TODO: this could be updated to use more generic 
              Configurable/ConfigurableManager code like other Session objects
    '''
    _name = "location"
    _type = coreapi.CORE_TLV_REG_UTILITY
    
    def __init__(self, session):
        ConfigurableManager.__init__(self, session)
        self.reset()
        self.zonemap = {}
        for n, l in utm.ZONE_LETTERS:
            self.zonemap[l] = n

    def reset(self):
        ''' Reset to initial state.
        '''
        # (x, y, z) coordinates of the point given by self.refgeo
        self.refxyz = (0.0, 0.0, 0.0)
        # decimal latitude, longitude, and altitude at the point (x, y, z)
        self.setrefgeo(0.0, 0.0, 0.0)
        # 100 pixels equals this many meters
        self.refscale = 1.0
        # cached distance to refpt in other zones
        self.zoneshifts = {}

    def configure_values(self, msg, values):
        ''' Receive configuration message for setting the reference point
            and scale.
        '''
        if values is None:
            self.session.info("location data missing")
            return None
        values = values.split('|')
        # Cartesian coordinate reference point
        refx,refy = map(lambda x: float(x), values[0:2])
        refz = 0.0
        self.refxyz = (refx, refy, refz)
        # Geographic reference point
        lat,long,alt = map(lambda x: float(x), values[2:5])
        self.setrefgeo(lat, long, alt)
        self.refscale = float(values[5])
        self.session.info("location configured: (%.2f,%.2f,%.2f) = "
            "(%.5f,%.5f,%.5f) scale=%.2f" %
            (self.refxyz[0], self.refxyz[1], self.refxyz[2], self.refgeo[0],
             self.refgeo[1], self.refgeo[2], self.refscale))
        self.session.info("location configured: UTM(%.5f,%.5f,%.5f)" %
                          (self.refutm[1], self.refutm[2], self.refutm[3]))

    def px2m(self, val):
        ''' Convert the specified value in pixels to meters using the
            configured scale. The scale is given as s, where
            100 pixels = s meters.
        '''
        return (val / 100.0) * self.refscale

    def m2px(self, val):
        ''' Convert the specified value in meters to pixels using the
            configured scale. The scale is given as s, where
            100 pixels = s meters.
        '''
        if self.refscale == 0.0:
            return 0.0
        return 100.0 * (val / self.refscale)

    def setrefgeo(self, lat, lon, alt):
        ''' Record the geographical reference point decimal (lat, lon, alt)
            and convert and store its UTM equivalent for later use.
        '''
        self.refgeo = (lat, lon, alt)
        # easting, northing, zone
        (e, n, zonen, zonel) = utm.from_latlon(lat, lon)
        self.refutm = ( (zonen, zonel), e, n, alt)

    def getgeo(self, x, y, z):
        ''' Given (x, y, z) Cartesian coordinates, convert them to latitude,
            longitude, and altitude based on the configured reference point
            and scale.
        '''
        # shift (x,y,z) over to reference point (x,y,z)
        x = x - self.refxyz[0]
        y = -(y - self.refxyz[1])
        if z is None:
            z = self.refxyz[2]
        else:
            z = z - self.refxyz[2]
        # use UTM coordinates since unit is meters
        zone = self.refutm[0]
        if zone == "":
            raise ValueError, "reference point not configured"
        e = self.refutm[1] + self.px2m(x)
        n = self.refutm[2] + self.px2m(y)
        alt = self.refutm[3] + self.px2m(z)
        (e, n, zone) = self.getutmzoneshift(e, n)
        try:
            lat, lon = utm.to_latlon(e, n, zone[0], zone[1])
        except utm.OutOfRangeError:
            self.info("UTM out of range error for e=%s n=%s zone=%s" \
                      "xyz=(%s,%s,%s)" % (e, n, zone, x, y, z))
            (lat, lon) = self.refgeo[:2]
        #self.info("getgeo(%s,%s,%s) e=%s n=%s zone=%s  lat,lon,alt=" \
        #          "%.3f,%.3f,%.3f" % (x, y, z, e, n, zone, lat, lon, alt))
        return (lat, lon, alt)

    def getxyz(self, lat, lon, alt):
        ''' Given latitude, longitude, and altitude location data, convert them
            to (x, y, z) Cartesian coordinates based on the configured
            reference point and scale. Lat/lon is converted to UTM meter
            coordinates, UTM zones are accounted for, and the scale turns
            meters to pixels.
        '''
        # convert lat/lon to UTM coordinates in meters
        (e, n, zonen, zonel) = utm.from_latlon(lat, lon)
        (rlat, rlon, ralt) = self.refgeo
        xshift = self.geteastingshift(zonen, zonel)
        if xshift is None:
            xm = e - self.refutm[1]
        else:
            xm = e + xshift
        yshift = self.getnorthingshift(zonen, zonel)
        if yshift is None:
            ym = n - self.refutm[2]
        else:
            ym = n + yshift
        zm = alt - ralt
        
        # shift (x,y,z) over to reference point (x,y,z)
        x = self.m2px(xm) + self.refxyz[0]
        y = -(self.m2px(ym) + self.refxyz[1])
        z = self.m2px(zm) + self.refxyz[2]
        return (x, y, z)

    def geteastingshift(self, zonen, zonel):
        ''' If the lat, lon coordinates being converted are located in a
        different UTM zone than the canvas reference point, the UTM meters
        may need to be shifted.
        This picks a reference point in the same longitudinal band 
        (UTM zone number) as the provided zone, to calculate the shift in
        meters for the x coordinate.
        '''
        rzonen = int(self.refutm[0][0])
        if zonen == rzonen:
            return None # same zone number, no x shift required
        z = (zonen, zonel)
        if z in self.zoneshifts and self.zoneshifts[z][0] is not None:
            return self.zoneshifts[z][0] # x shift already calculated, cached
            
        (rlat, rlon, ralt) = self.refgeo
        lon2 = rlon + 6*(zonen - rzonen) # ea. zone is 6deg band
        (e2, n2, zonen2, zonel2) = utm.from_latlon(rlat, lon2) # ignore northing
        # NOTE: great circle distance used here, not reference ellipsoid!
        xshift = utm.haversine(rlon, rlat, lon2, rlat) - e2
        # cache the return value
        yshift = None
        if z in self.zoneshifts:
            yshift = self.zoneshifts[z][1]
        self.zoneshifts[z] = (xshift, yshift)
        return xshift
    
    def getnorthingshift(self, zonen, zonel):
        ''' If the lat, lon coordinates being converted are located in a
        different UTM zone than the canvas reference point, the UTM meters
        may need to be shifted.
        This picks a reference point in the same latitude band (UTM zone letter)
        as the provided zone, to calculate the shift in meters for the
        y coordinate.
        '''
        rzonel = self.refutm[0][1]
        if zonel == rzonel:
            return None # same zone letter, no y shift required
        z = (zonen, zonel)
        if z in self.zoneshifts and self.zoneshifts[z][1] is not None:
            return self.zoneshifts[z][1] # y shift already calculated, cached
        
        (rlat, rlon, ralt) = self.refgeo
        # zonemap is used to calculate degrees difference between zone letters
        latshift = self.zonemap[zonel] - self.zonemap[rzonel]
        lat2 = rlat + latshift # ea. latitude band is 8deg high
        (e2, n2, zonen2, zonel2) = utm.from_latlon(lat2, rlon)
        # NOTE: great circle distance used here, not reference ellipsoid
        yshift = -(utm.haversine(rlon, rlat, rlon, lat2) + n2)
        # cache the return value
        xshift = None
        if z in self.zoneshifts:
            xshift = self.zoneshifts[z][0]
        self.zoneshifts[z] = (xshift, yshift)
        return yshift

    def getutmzoneshift(self, e, n):
        ''' Given UTM easting and northing values, check if they fall outside
        the reference point's zone boundary. Return the UTM coordinates in a
        different zone and the new zone if they do. Zone lettering is only
        changed when the reference point is in the opposite hemisphere.
        '''
        zone = self.refutm[0]
        (rlat, rlon, ralt) = self.refgeo
        if e > 834000 or e < 166000:
            num_zones = (int(e) - 166000) / (utm.R/10)
            # estimate number of zones to shift, E (positive) or W (negative)
            rlon2 = self.refgeo[1] + (num_zones * 6)
            (e2, n2, zonen2, zonel2) = utm.from_latlon(rlat, rlon2)
            xshift = utm.haversine(rlon, rlat, rlon2, rlat)
            # after >3 zones away from refpt, the above estimate won't work
            # (the above estimate could be improved)
            if not 100000 <= (e - xshift) < 1000000:
                # move one more zone away
                num_zones = (abs(num_zones)+1) * (abs(num_zones)/num_zones)
                rlon2 = self.refgeo[1] + (num_zones * 6)
                (e2, n2, zonen2, zonel2) = utm.from_latlon(rlat, rlon2)
                xshift = utm.haversine(rlon, rlat, rlon2, rlat)
            e = e - xshift
            zone = (zonen2, zonel2)
        if n < 0:
            # refpt in northern hemisphere and we crossed south of equator
            n += 10000000
            zone = (zone[0], 'M')
        elif n > 10000000:
            # refpt in southern hemisphere and we crossed north of equator
            n -= 10000000
            zone = (zone[0], 'N')
        return (e, n, zone)
       
    

