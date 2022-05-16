""" Plugin to translate and scale aircraft between two different areas. """
import numpy as np
from os import path
import geopandas as gpd
from shapely.affinity import rotate, scale, translate
from pyproj import Transformer
import warnings
from shapely.errors import ShapelyDeprecationWarning
warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)

from bluesky import settings, stack
from bluesky.ui.qtgl.gltraffic import Traffic

# Register settings defaults
settings.set_variable_defaults(
    text_size=13, ac_size=16,
    asas_vmin=200.0, asas_vmax=500.0)

### Initialization function of plugin.
def init_plugin():
    config = {
        'plugin_name':     'GLPROJECTTRAFFIC',
        'plugin_type':     'gui',
        }

    return config

# Projected Traffic class
class ProjTraffic(Traffic):

    def __init__(self):
        super().__init__()

        # center of airspace in vienna (epsg:3857)
        self.xy_center_vienna = (1821437, 6141036)

        # reference length of vienna (km)
        self.ref_length_vienna = 8

        # center of airspace in Valkenburg (epsg:3857) (491733, 6830838)
        self.xy_valkenburg = (491733, 6830838)

        # reference length of valkenburg (km)
        self.ref_length_valkenburg = 8

        # initialize the offset and scale factor
        self.xy_offset = (0, 0)
        self.scale_factor = 1

        # create a transformer for the projection
        self.transformer_m = Transformer.from_crs(4326, 3857, always_xy=True)
        self.transformer_deg = Transformer.from_crs(3857, 4326)

    def actdata_changed(self, nodeid, nodedata, changed_elems):
        ''' Process incoming traffic data. '''
        if 'ACDATA' in changed_elems:
            data = self.project_aircraft_data(nodedata.acdata)
            self.update_aircraft_data(data)

        if 'ROUTEDATA' in changed_elems:
            self.update_route_data(nodedata.routedata)
        if 'TRAILS' in changed_elems:
            self.update_trails_data(nodedata.traillat0,
                                    nodedata.traillon0,
                                    nodedata.traillat1,
                                    nodedata.traillon1)

    def project_aircraft_data(self, data):
        ''' Project aircraft data to a new area. '''
        if not self.initialized:
            return
        naircraft = len(data.lat)
        
        if naircraft == 0:
            self.cpalines.set_vertex_count(0)
        else:
            # Move drone to Vienna

            # step 1: create vectors from self.xy_valkenburg to current aircraft positions
            # step 2: scale the vectors by the self.scale_factor
            # step 3: translate the vectors by self.xy_offset

            # Step 1
            # transform to UTM
            x, y = self.transformer_m.transform(data.lon, data.lat)

            # subtract from valkenburg reference point
            x_pos = x - self.xy_valkenburg[0]
            y_pos = y - self.xy_valkenburg[1]

            # Step 2: scale x_pos and y_pos by self.scale_factor
            x_pos *= self.scale_factor
            y_pos *= self.scale_factor

            # step 3: translate x_pos and y_pos from self.xy_vienna
            x_pos += self.xy_center_vienna[0]
            y_pos += self.xy_center_vienna[1]

            data.lat, data.lon = self.transformer_deg.transform(x_pos, y_pos)
            
        return data
    
    @stack.command
    def setrefpoint(self, *coords):
        ''' Set reference point for scenario in valkenburg. 
        This value should be where the center of the airspace in Vallenkenburg should be.
        EPSG:3857 coordinates. '''

        # get xy coordinates of reference point
        self.xy_valkenburg  = (float(coords[0]), float(coords[1]))

        # Calculate offset between reference point and center of airspace
        self.xy_offset = (self.xy_center_vienna[0] - self.xy_valkenburg[0], 
                          self.xy_center_vienna[1] - self.xy_valkenburg[1])
    
    @stack.command
    def setreflength(self, reflen: float):
        ''' Set the reference length for scaling. In kilometers. '''

        # set scale factor
        self.scale_factor = self.ref_length_vienna / reflen
