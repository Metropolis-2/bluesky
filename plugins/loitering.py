import bluesky as bs
from bluesky import stack
from bluesky.core import Entity
from .geofence import Geofence

def init_plugin():
    ''' Plugin initialisation function. '''
    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'Loitering',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }

    # init_plugin() should always return a configuration dict.
    return config

class Loitering(Entity):
    def __init__(self):
        super().__init__()
        with self.settrafarrays():
            self.geofences = []
        
    @stack.command
    def creloiter(self, acid, actype, aclat, aclon, achdg, acalt, acspd, *geocoords):
        '''Create a loitering aircraft.'''
        # First, create aircraft
        bs.traf.cre(acid, actype, aclat, aclon, achdg, acalt, acspd)
        
        # There should be an aircraft index now
        acidx = bs.traf.id.index(acid)
        
        # Insert a geofence in the traf array
        self.geofences[acid] = Geofence(f'LOITER{acid}', geocoords)
        
    