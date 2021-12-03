""" This plugin checks if it is possible for a drone to start its descend
to its destination """

from random import randint
import numpy as np
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, settings #, navdb, sim, scr, tools

### Initialization function of your plugin. Do not change the name of this
### function, as it is the way BlueSky recognises this file as a plugin.
def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity
    descendChecker = descendcheck()

    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'descendcheck',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }

    # init_plugin() should always return a configuration dict.
    return config


class descendcheck(core.Entity):
    ''' Example new entity object for BlueSky. '''
    def __init__(self):
        super().__init__()
        with self.settrafarrays():
            self.startDescend = np.array([], dtype=bool) # array of booleans to check if descend can start
        
        # update traf
        traf.startDescend = self.startDescend
        

    def create(self, n=1):
        ''' This function gets called automatically when new aircraft are created. '''
        # Don't forget to call the base class create when you reimplement this function!
        super().create(n)
        self.startDescend[-n:] = False
        traf.startDescend = self.startDescend

    def delete(self, idx):
        super().delete(idx)
        # update traf
        traf.startDescend = self.startDescend
        

    # Functions that need to be called periodically can be indicated to BlueSky
    # with the timed_function decorator

    @core.timed_function(name='descendcheck', dt=5)
    def update(self):
        
        # Only aircraft that do not have tactical conflicts should descend to the destination
        descendidxs = np.where(traf.cr.active==False)[0]
        
        for idx in descendidxs:
            
            # find out the current active waypoint
            iwpid = traf.ap.route[idx].iactwp
            
            # Proceed if the aircraft has waypoints
            if iwpid > -1:
            
                # Determine the lat lon of the last and the second last waypoints. the second last waypoint is the ToD
                sec_last_wptidx = traf.ap.route[idx].nwp-2
                sec_last_wpt_lat = traf.ap.route[idx].wplat[sec_last_wptidx]
                sec_last_wpt_lon = traf.ap.route[idx].wplon[sec_last_wptidx]
                
                # If all the conditions are satisfied, then use stack commands to descend this aircraft
                if iwpid == sec_last_wptidx and self.startDescend[idx] == False:
                    
                    # call the stacks
                    stack.stack(f"ATDIST {traf.id[idx]} {sec_last_wpt_lat} {sec_last_wpt_lon} 0.1115982 SPD {traf.id[idx]} 0")
                    stack.stack(f"ATSPD {traf.id[idx]} 0 ALT {traf.id[idx]} -5")
                    stack.stack(f"ATALT {traf.id[idx]} 5 DEL {traf.id[idx]}")
                    
                    # update the startDescend
                    self.startDescend[idx] = True

        
        # update traf
        traf.startDescend = self.startDescend
