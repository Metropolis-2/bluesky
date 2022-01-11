
from random import randint
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, LineString,Point
from bluesky import core, stack, traf, tools, settings



geofences = tools.areafilter.basic_shapes
#geo_save_dict =
geofence_names = geofences.keys()
#TODO ignore if current location or last waypoint is in a geofence.

def checker(acid: 'acid'):
    multiGeofence = []
    # check for each geofence if the aircrafts intent intersects with the geofence
    # TODO Check if we can only run below function if a new geofence gets created... sort of like the super.create
    for j in geofence_names:

        # restructure the coordinates of the BS Poly shape to cast it into a shapely Polygon
        coord_list = list(zip(geofences[j].coordinates[1::2],geofences[j].coordinates[0::2]))

        #construct shapely Polygon object and add it to the multipolygon list
        shapely_geofence = Polygon(coord_list)
        multiGeofence.append(shapely_geofence)

    # get the aircraft route to check against current geofence
    # TODO trim the route to only the active waypoint and forwards and current position
    acroute = traf.ap.route[acid]
    iactwp = acroute.iactwp

    ac_lat = traf.lat[acid]
    ac_lon = traf.lon[acid]

    routecoords = [(ac_lon,ac_lat)]
    routecoords.extend(list(zip(acroute.wplon[iactwp:],acroute.wplat[iactwp:])))

    # construct the multipolygon object from all the polygons
    # this way you only have to check each aircraft against one shapely object instead of when each geofence in its own.
    # Buffer is used here to account for errors when having overlapping polygons, why does this work?
    # source https://stackoverflow.com/questions/63955752/topologicalerror-the-operation-geosintersection-r-could-not-be-performed
    multiGeofence = MultiPolygon(multiGeofence).buffer(0)

    if len(routecoords) > 1:
        route = LineString(routecoords)
        #check for intersect between route and multipolygon
        routeval = route.intersects(multiGeofence)
    else:
        routeval = False

    acval = multiGeofence.contains((Point(ac_lon, ac_lat)))
    destval = multiGeofence.contains((Point(routecoords[-1])))

    if acval:
        print(f'{acid} stuck in geofence')
    if destval:
        print(f'{acid} destination stuck in geofence')
    if routeval and not acval and not destval:
        stack.stack(f'REROUTEGEOFENCE {traf.id[acid]}')

    return routeval, acval