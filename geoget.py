import math
import sys

import requests
import json
import time
import urllib3

URL = 'http://localhost:8093'
 
 
class GeoLocation:
    '''
    Class representing a coordinate on a sphere, most likely Earth.
    
    This class is based from the code smaple in this paper:
        http://janmatuschek.de/LatitudeLongitudeBoundingCoordinates
        
    The owner of that website, Jan Philip Matuschek, is the full owner of 
    his intellectual property. This class is simply a Python port of his very
    useful Java code. All code written by Jan Philip Matuschek and ported by me 
    (which is all of this class) is owned by Jan Philip Matuschek.
    '''
 
 
    MIN_LAT = math.radians(-90)
    MAX_LAT = math.radians(90)
    MIN_LON = math.radians(-180)
    MAX_LON = math.radians(180)
    
    EARTH_RADIUS = 6378.1  # kilometers
    
    
    @classmethod
    def from_degrees(cls, deg_lat, deg_lon):
        rad_lat = math.radians(deg_lat)
        rad_lon = math.radians(deg_lon)
        return GeoLocation(rad_lat, rad_lon, deg_lat, deg_lon)
        
    @classmethod
    def from_radians(cls, rad_lat, rad_lon):
        deg_lat = math.degrees(rad_lat)
        deg_lon = math.degrees(rad_lon)
        return GeoLocation(rad_lat, rad_lon, deg_lat, deg_lon)
    
    
    def __init__(
            self,
            rad_lat,
            rad_lon,
            deg_lat,
            deg_lon
    ):
        self.rad_lat = float(rad_lat)
        self.rad_lon = float(rad_lon)
        self.deg_lat = float(deg_lat)
        self.deg_lon = float(deg_lon)
        self._check_bounds()
        
    def __str__(self):
        degree_sign= u'\N{DEGREE SIGN}'
        return ("({0:.4f}deg, {1:.4f}deg) = ({2:.6f}rad, {3:.6f}rad)").format(
            self.deg_lat, self.deg_lon, self.rad_lat, self.rad_lon)
        
    def _check_bounds(self):
        if (self.rad_lat < GeoLocation.MIN_LAT 
                or self.rad_lat > GeoLocation.MAX_LAT 
                or self.rad_lon < GeoLocation.MIN_LON 
                or self.rad_lon > GeoLocation.MAX_LON):
            raise Exception("Illegal arguments")
            
    def distance_to(self, other, radius=EARTH_RADIUS):
        '''
        Computes the great circle distance between this GeoLocation instance
        and the other.
        '''
        return radius * math.acos(
                math.sin(self.rad_lat) * math.sin(other.rad_lat) +
                math.cos(self.rad_lat) * 
                math.cos(other.rad_lat) * 
                math.cos(self.rad_lon - other.rad_lon)
            )
            
    def bounding_locations(self, distance, radius=EARTH_RADIUS):
        '''
        Computes the bounding coordinates of all points on the surface
        of a sphere that has a great circle distance to the point represented
        by this GeoLocation instance that is less or equal to the distance argument.
        
        Param:
            distance - the distance from the point represented by this GeoLocation
                       instance. Must be measured in the same unit as the radius
                       argument (which is kilometers by default)
            
            radius   - the radius of the sphere. defaults to Earth's radius.
            
        Returns a list of two GeoLoations - the SW corner and the NE corner - that
        represents the bounding box.
        '''
        
        if radius < 0 or distance < 0:
            raise Exception("Illegal arguments")
            
        # angular distance in radians on a great circle
        rad_dist = distance / radius
        
        min_lat = self.rad_lat - rad_dist
        max_lat = self.rad_lat + rad_dist
        
        if min_lat > GeoLocation.MIN_LAT and max_lat < GeoLocation.MAX_LAT:
            delta_lon = math.asin(math.sin(rad_dist) / math.cos(self.rad_lat))
            
            min_lon = self.rad_lon - delta_lon
            if min_lon < GeoLocation.MIN_LON:
                min_lon += 2 * math.pi
                
            max_lon = self.rad_lon + delta_lon
            if max_lon > GeoLocation.MAX_LON:
                max_lon -= 2 * math.pi
        # a pole is within the distance
        else:
            min_lat = max(min_lat, GeoLocation.MIN_LAT)
            max_lat = min(max_lat, GeoLocation.MAX_LAT)
            min_lon = GeoLocation.MIN_LON
            max_lon = GeoLocation.MAX_LON
        
        return [ GeoLocation.from_radians(min_lat, min_lon) , 
            GeoLocation.from_radians(max_lat, max_lon) ]


            
if __name__ == '__main__':
    # Test bounding box
    # loc = GeoLocation.from_degrees(37.7749, -122.431279) # SFO
    # distance = 100  # 1 kilometer
    # SW_loc, NE_loc = loc.bounding_locations(distance)

    if len(sys.argv) <> 4:
        print "Usage: pgm lattitude longitude distance"
        sys.exit(0)

    lat =  float(sys.argv[1])
    lon =  float(sys.argv[2])
    distance =  float(sys.argv[3])
    print "lat: ", lat, "lon: ", lon, "distance: ", distance, "Kilometers"

    # Example
    # loc = GeoLocation.from_degrees(37.7749, -122.431279) # SFO
    # distance = 100  # kilometer

    loc = GeoLocation.from_degrees(lat, lon)
    distance = distance   #  kilometer

    SW_loc, NE_loc = loc.bounding_locations(distance)

    meridian180condition = (" OR " if (SW_loc.rad_lon > NE_loc.rad_lon) else " AND ")

    # To get the best performance, create the following index.
    # create index i1 on `beer-sample`(RADIANS(geo.lat), RADIANS(geo.lon))

    query = "SELECT country, state, city, name, geo FROM `beer-sample` WHERE " + \
    "(RADIANS(geo.lat) >= " + str(SW_loc.rad_lat) + " and RADIANS(geo.lat) <= " + str(NE_loc.rad_lat) + ") and " \
    "(RADIANS(geo.lon) >= " + str(SW_loc.rad_lon) +  meridian180condition + " RADIANS(geo.lon) <= " + str(NE_loc.rad_lon) + ")"  \
    + " AND " \
    " acos(sin( RADIANS(" + str(loc.deg_lat) + ")) * sin (RADIANS(geo.lat)) + cos( RADIANS(" + str(loc.deg_lat) +  " )) " \
    + " * cos(RADIANS(geo.lat)) * cos (RADIANS(geo.lon) - RADIANS( " + str(loc.deg_lon) + "))) <= " + str(distance/6371.0)

    stmt = {'statement':query}

    conn = urllib3.connection_from_url(URL)
    # print stmt
    response = conn.request('POST', '/query/service', fields=stmt, encode_multipart=False)
    body = json.loads(response.data.decode('utf8'))

    # print query
    print "Elapsed Time: ", body['metrics']['elapsedTime'], "Execution Time: ", body['metrics']['executionTime']
    # print body['results']

    print json.dumps(body['results'], separators=(',',':'),indent=4);
