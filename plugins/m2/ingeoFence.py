from shapely.geometry import Polygon, MultiPolygon, LineString,Point
from bluesky import core, stack, traf, tools, settings


def checker(acid: 'acid', multiGeofence):
    # get the aircraft route to check against current geofence
    acroute = traf.ap.route[acid]
    iactwp = acroute.iactwp

    ac_lat = traf.lat[acid]
    ac_lon = traf.lon[acid]

    routecoords = [(ac_lon,ac_lat)]
    routecoords.extend(list(zip(acroute.wplon[iactwp:],acroute.wplat[iactwp:])))

    if len(routecoords) > 1:
        route = LineString(routecoords)
        for i in multiGeofence:
            #check for intersect between route and multipolygon
            routeval = route.intersects(i)
            if routeval: break
    else:
        routeval = False

    for i in multiGeofence:
        acval = i.contains((Point(ac_lon, ac_lat)))
        if acval: break
    for i in multiGeofence:
        destval = i.contains((Point(routecoords[-1])))
        if destval: break

    if acval:
        print(f'{acid} stuck in geofence')
    if destval:
        print(f'{acid} destination stuck in geofence')
    if routeval and not acval and not destval:
        stack.stack(f'REROUTEGEOFENCE {traf.id[acid]}')

    return routeval, acval

def create_multipoly(geofences):
    multiGeofence = []

    geofence_names = geofences.keys()
    # check for each geofence if the aircrafts intent intersects with the geofence
    for j in geofence_names:

        # restructure the coordinates of the BS Poly shape to cast it into a shapely Polygon
        coord_list = list(zip(geofences[j]['coordinates'][1::2],geofences[j]['coordinates'][0::2]))

        #construct shapely Polygon object and add it to the multipolygon list
        shapely_geofence = Polygon(coord_list)
        multiGeofence.append(shapely_geofence)

    return multiGeofence