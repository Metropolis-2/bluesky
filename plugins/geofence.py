from bluesky import settings, stack
from bluesky.tools import aero, areafilter, geo
from rtree import index
from matplotlib.path import Path

settings.set_variable_defaults(geofence_dtlookahead=30)

def init_plugin():
    # Configuration parameters
    config = {
        'plugin_name': 'GEOFENCE',
        'plugin_type': 'sim',
        'reset': Geofence.reset
    }
    return config

@stack.command()
def geofence(name: 'txt', top: float, bottom: float, *coordinates: float):
    ''' Create a new geofence from the stack. 
        
        Arguments:
        - name: The name of the new geofence
        - top: The top of the geofence in feet.
        - bottom: The bottom of the geofence in feet.
        - coordinates: three or more lat/lon coordinates in degrees.
    '''
    Geofence.geofences[name] = Geofence(name, top, bottom, coordinates)
    return True, f'Created geofence {name}'

class Geofence(areafilter.Poly):
    ''' BlueSky Geofence class.
    
        This class subclasses Shape, and adds Geofence-specific data and methods.
    '''
    # Keep dicts of geofences by either name or rtree ID
    geo_by_name = dict()
    geo_by_id = dict()
    
    # Also have a dictionary used for saving and loading geofences
    geo_save_dict = dict()
    
    # Keep an Rtree of geofences
    geo_tree = index.Index()
    
    # Keep track of the geofences themselves that aircraft are hitting or intruding in
    # "intrusions" contains aircraft that are currently intruding inside a geofence, and a list
    # of the geofences they are intruding in
    # "hits" contains the geofences that aircraft are about to hit (or are intruding)
    intrusions = dict()
    hits = dict()

    def __init__(self, name, coordinates, top=999999, bottom=-999999):
        super().__init__(name, coordinates, top=top, bottom=bottom)
        self.active = True
        #Add info to geofence save dictionary
        geo_dict = dict()
        geo_dict['name'] = name
        geo_dict['coordinates'] = coordinates
        geo_dict['top'] = top
        geo_dict['bottom'] = bottom
        Geofence.geo_save_dict['name'] = geo_dict
        
        # Also add the class instance itself to the other dictionaries
        Geofence.geo_by_name['name'] = self
        Geofence.geo_by_id[self.area_id] = self
        
        # Insert the geofence in the geofence Rtree
        Geofence.geo_tree.insert(self.area_id, self.bbox)

    def intersects(self, line):
        ''' Check whether given line intersects with this geofence poly. '''
        line_path = Path(line)
        return self.border.intersects_path(line_path)
        
    @classmethod
    def reset(cls):
        ''' Reset geofence database when simulation is reset. '''
        cls.geo_by_name.clear()
        cls.geo_by_id.clear()
        cls.geo_save_dict.clear()
        cls.geo_tree = index.Index()
        cls.hits.clear()
        cls.intrusions.clear()
        
    @classmethod
    def intersecting(cls, coordinates):
        '''Get the geofences that intersect coordinates (either bbox or point).'''
        poly_ids = cls.geo_tree.intersection(coordinates)
        return [cls.geo_by_id[id] for id in poly_ids]

    @classmethod
    def detect_all(cls, traf, dtlookahead=None):
        if dtlookahead is None:
            dtlookahead = settings.geofence_dtlookahead
        # Reset the hits dict
        cls.hits.reset()
        # Linearly extrapolate current state to prefict future position
        pred_lat, pred_lon = geo.kwikpos(traf.lat, traf.lon, traf.hdg, traf.gs / aero.nm * dtlookahead)
        for idx, line in zip(traf.lat, traf.lon, pred_lat, pred_lon):
            acid = traf.id[idx]
            # First a course detection based on geofence bounding boxes
            potential_hits = areafilter.get_intersecting(*line)
            # Then a fine-grained intersection detection
            hits = []
            for geofence in potential_hits:
                if geofence.intersects(line):
                    hits.append(geofence)
            cls.hits[acid] = hits
        return
    
    @classmethod
    def detect_inside(cls, traf):
        # Reset the intrusions dict
        cls.intrusions.reset()
        for idx, point in zip(traf.lat, traf.lon, traf.alt):
            acid = traf.id[idx]
            # First, a course detection based on geofence bounding boxes
            potential_intrusions = cls.intersecting([point[0], point[1]])
            # Then a fine-grained intrusion detection
            intrusions = []
            for geofence in potential_intrusions:
                if geofence.checkInside(*point):
                    intrusions.append(geofence)
            cls.intrusions[acid] = intrusions
        return