from bluesky.core.simtime import timed_function
import bluesky as bs
import numpy as np
from bluesky import core
from bluesky import stack
from bluesky.tools.geo import kwikdist, kwikqdrdist, latlondist, qdrdist
from bluesky.tools.aero import nm, ft, kts
from bluesky.tools.misc import degto180

def init_plugin():

    # Addtional initilisation code
    nav = M2CentralSpd()
    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'M2CENTRALSPD',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim'
    }

    return config

class M2CentralSpd(core.Entity):
    def __init__(self):
        super().__init__()  
        
    @timed_function(name='navtimedfunction', dt=0.5)
    def navtimedfunction(self):
        if bs.traf.ntraf == 0:
            return
        
        in_turn = np.logical_or(bs.traf.ap.inturn, bs.traf.ap.dist2turn < 75)  # Are aircraft in a turn?
        in_vert_man = np.abs(bs.traf.vs) > 0 # Are aircraft performing a vertical maneuver?
        speed_zero = np.array(bs.traf.selspd) == 0 # The selected speed is 0, so we're at our destination and landing
        lnav_on = bs.traf.swlnav # lnav on
        rogue = bs.traf.roguetraffic.rogue_bool # rogue aircraft
        
        set_cruise_speed = np.logical_and.reduce((lnav_on, 
                                                  np.logical_not(rogue),
                                                  np.logical_not(speed_zero),
                                                  np.logical_not(in_turn),
                                                  np.logical_not(in_vert_man)))
        
        cruise_speed = np.where(bs.traf.type == 'MP20', 20, 30)
        
        bs.traf.selspd = np.where(set_cruise_speed, cruise_speed, bs.traf.selspd)
        
        return
        
        