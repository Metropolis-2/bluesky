""" BlueSky plugin template. The text you put here will be visible
    in BlueSky as the description of your plugin. """
from random import randint
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, LineString
from bluesky import core, stack, traf, tools, settings

geofences = tools.areafilter.basic_shapes
geofence_names = geofences.keys()
#TODO ignore if current location or last waypoint is in a geofence.

def init_plugin():
    ingeofence = ingeoFence()
    config = {
        # The name of your plugin
        'plugin_name':     'ingeofence',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }

    # init_plugin() should always return a configuration dict.
    return config

class ingeoFence(core.Entity):
    ''' Example new entity object for BlueSky. '''
    def __init__(self):
        super().__init__()
        with self.settrafarrays():
            self.ingeofence = np.array([],dtype=bool)

        traf.ingeofence = self.ingeofence

    @core.timed_function(name='ingeofence', dt=settings.asas_dt)
    def update(self):
        #check for each aircraft if it interferes with one of the geofences
        for i in traf.id:
            idx=traf.id2idx(i)
            val = self.checker(acid=idx)
            self.ingeofence[idx] = val

        # set the self to the traf so it can be used by other plugins
        traf.ingeofence = self.ingeofence

    def checker(self, acid: 'acid'):
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
        if len(routecoords) > 1:

            route = LineString(routecoords)

            #construct the multipolygon object from all the polygons
            #this way you only have to check each aircraft against one shapely object instead of when each geofence in its own.
            #Buffer is used here to account for errors when having overlapping polygons, why does this work?
            #source https://stackoverflow.com/questions/63955752/topologicalerror-the-operation-geosintersection-r-could-not-be-performed
            multiGeofence = MultiPolygon(multiGeofence).buffer(0)

            #check for intersect between route and multipolygon

            val = route.intersects(multiGeofence)

            if val:
                stack.stack(f'REROUTEGEOFENCE {traf.id[acid]}')
        else:
            val = False
        return val

    @stack.command
    def echoacgeofence(self, acid: 'acid'):
        ''' Print the if an acid is in conflict with a geofence '''
        geofence = self.getacgeofence(acid)
        return True, f'{traf.id[acid]} geofence conflict {geofence}.'

    def getacgeofence(self, acid: 'acid'):
        ''' return the bool value in ingeofence of a specific acid '''
        val = self.ingeofence[acid]
        return val