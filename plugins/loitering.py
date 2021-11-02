import bluesky as bs
from bluesky import stack
from bluesky.core import Entity
from bluesky.core.simtime import timed_function
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

check_dt = 10
class Loitering(Entity):
    def __init__(self):
        super().__init__()
        self.loitergeofences = dict()
        with self.settrafarrays():
            self.futuregeofences = []
            self.geodurations = []
        
    @stack.command
    def creloiter(self, acid, actype, aclat, aclon, achdg, acalt, acspd, geodur, *geocoords):
        '''Create a loitering aircraft.'''
        # First, create aircraft
        bs.traf.cre(acid, actype, aclat, aclon, achdg, acalt, acspd)
        
        # There should be an aircraft index now
        acidx = bs.traf.id.index(acid)
        
        # Store the geofence data in the array until it needs to be enacted
        self.futuregeofences[acidx] = geocoords
        self.geodurations[acidx] = geodur
    
    @stack.command
    def delloiter(self, acidx:'acid'):
        '''Delete loitering aircraft, add its geofence.'''
        acid = bs.traf.id[acidx]
        # First of all, add the geofence 
        self.loitergeofences[acid] = {'geofence':Geofence(f'LOITER{acid}', self.futuregeofences[acidx]), 
                                      'time_left':self.geodurations[acidx]}
        # Then delete the aircraft
        bs.traf.delete(acidx)
        
        
    @timed_function(dt = check_dt)
    def keep_track_loitering(self):
        '''Keep track of loiter geofences, and delete them when they have expired.'''
        # iterate through dictionary entries
        # This shouldn't take too long, there won't be many entries in this dictionary
        for acid in self.loitergeofences:
            # Decrement time
            self.loitergeofences[acid]['time_left'] -= check_dt
            # Check if time is negative
            if self.loitergeofences[acid]['time_left'] < 0:
                # Delete geofence
                Geofence.delete(f'LOITER{acid}')
                self.loitergeofences.pop(acid)
            
            
            
            
        
    