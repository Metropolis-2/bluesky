import bluesky as bs
from bluesky.traffic.windsim import WindSim
from bluesky import stack
from bluesky.tools.aero import kts
import numpy as np

def init_plugin():
    ''' Plugin initialisation function. '''
    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'M2Wind',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }

    # init_plugin() should always return a configuration dict.
    return config

class M2Wind(WindSim):
    def __init__(self):
        super().__init__()
        self.magnitude = 0
        self.direction = 0
        self.windvec = np.array([0,0])

    @stack.command(name = 'SETM2WIND')
    def setm2wind(self, magnitude:'float', direction:'hdg'):
        self.magnitude = magnitude * kts
        self.direction = np.deg2rad(direction)
        # Calculate the vector
        self.windvec = np.array([np.sin(self.direction)*self.magnitude, 
                                 np.cos(self.direction)*self.magnitude])
        self.winddim = 1
        return True

    def getdata(self, lats, lons , alts):
        '''This function needs to return vnorth and veast. What we basically want to apply is
        the wind magnitude and direction on the velocity of the aircraft, without affecting its
        heading or track, just the speed.'''
        if len(lats) == 1 and bs.traf.gs[-1] == 0:
            return 0,0
    
        # Get the velocities of aircraft
        hdg = np.deg2rad(bs.traf.hdg)
        gseast = bs.traf.gs * np.sin(hdg)
        gsnorth = bs.traf.gs * np.cos(hdg)
        
        # Reshape to work with it.
        gsarr = np.reshape([gseast, gsnorth], (2, bs.traf.ntraf))
        
        # Calculate the magnitudes of the wind
        windmags = np.dot(self.windvec, gsarr)/np.linalg.norm(gsarr, axis = 0)
        
        # Create magnitudes
        veast = windmags*np.sin(hdg)
        vnorth = windmags*np.cos(hdg) 
        
        veast = np.where(bs.traf.gs < 15*kts, 0, veast)
        vnorth = np.where(bs.traf.gs < 15*kts, 0 , vnorth)
        
        return vnorth, veast