from shapely.geometry import Polygon, MultiPolygon, LineString,Point
from bluesky import core, stack, traf, tools, settings
import plugins.geofence as geofence_TUD
from bluesky.tools.aero import ft

def checker(acid: 'acid', multiGeofence, multiGeofence_vert):
    # get the aircraft route to check against current geofence
    acroute = traf.ap.route[acid]
    iactwp = acroute.iactwp

    ac_lat = traf.lat[acid]
    ac_lon = traf.lon[acid]
    ac_route_alt = Point(0,max(traf.ap.route[acid].wpalt)/ft)
    ac_alt = Point(0,traf.alt[acid]/ft)
    ac_pos = Point(ac_lon, ac_lat)

    routecoords = [(ac_lon,ac_lat)]
    routecoords.extend(list(zip(acroute.wplon[iactwp:],acroute.wplat[iactwp:])))

    if len(routecoords) > 1:
        route = LineString(routecoords)
        for i,j in list(zip(multiGeofence, multiGeofence_vert)):
            # check for intersect between route and multipolygon
            routeval = route.intersects(i) and ac_route_alt.intersects(j)
            if routeval:
                break
    else:
        routeval = False

    for i,j in list(zip(multiGeofence, multiGeofence_vert)):
        acval = i.contains(ac_pos) and ac_alt.intersects(j)
        if acval: break
    for i in multiGeofence:
        destval = i.contains((Point(routecoords[-1])))
        if destval: break

    #if acval:
        #print(f'{acid} stuck in geofence')
    #if destval:
        #print(f'{acid} destination stuck in geofence')
    if routeval and not acval and not destval:
        stack.stack(f'REROUTEGEOFENCE {traf.id[acid]}')

    return routeval, acval

def create_multipoly(geofences):
    multiGeofence = []
    multiGeofence_vert = []
    geofence_names = [key for key, value in geofences.items() if type(key)==str]
    # check for each geofence if the aircrafts intent intersects with the geofence
    for j in geofence_names:

        # restructure the coordinates of the BS Poly shape to cast it into a shapely Polygon
        coord_list = list(zip(geofences[j]['coordinates'][1::2],geofences[j]['coordinates'][0::2]))

        #construct shapely Polygon object and add it to the multipolygon list
        shapely_geofence = Polygon(coord_list)
        multiGeofence.append(shapely_geofence)

        geoTop = geofence_TUD.Geofence.geo_save_dict[j]['top']
        geoBottom = geofence_TUD.Geofence.geo_save_dict[j]['bottom']

        shapely_line = LineString([(0,geoBottom),(0,geoTop)])
        multiGeofence_vert.append(shapely_line)

    return multiGeofence, multiGeofence_vert