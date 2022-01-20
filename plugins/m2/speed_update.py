""" BlueSky plugin template. The text you put here will be visible
    in BlueSky as the description of your plugin. """
from random import randint
import numpy as np
import re
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, tools  #, settings, navdb, sim, scr, tools
from bluesky.tools.aero import kts
### Initialization function of your plugin. Do not change the name of this
### function, as it is the way BlueSky recognises this file as a plugin.
def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity
    example = speedUpdate()

    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'speedUpdate',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }

    # init_plugin() should always return a configuration dict.
    return config


### Entities in BlueSky are objects that are created only once (called singleton)
### which implement some traffic or other simulation functionality.
### To define an entity that ADDS functionality to BlueSky, create a class that
### inherits from bluesky.core.Entity.
### To replace existing functionality in BlueSky, inherit from the class that
### provides the original implementation (see for example the asas/eby plugin).
class speedUpdate(core.Entity):
    ''' Example new entity object for BlueSky. '''
    def __init__(self):
        super().__init__()

    # Functions that need to be called periodically can be indicated to BlueSky
    # with the timed_function decorator
    @core.timed_function(name='speedUpdate', dt=5)
    def update(self):
        for i in traf.id:
            acid = traf.id2idx(i)
            ac_diff = traf.delayed[acid]
            ac_route = traf.ap.route[acid]
            iactwp = ac_route.iactwp
            if iactwp == ac_route.nwp - 2:
                continue
            if traf.resostrategy[acid] == "None":
                self.setSpeed(acid, ac_diff)
#TODO add traf array with bools that indicates if an ac is speed updating.

    def setSpeed(self,idxown, diff):

        # Determine the layer index of the current layer of ownship
        idxCurrentLayer = np.where(traf.layernames == traf.aclayername[idxown])[0]
        nameCurrentLayer = traf.aclayername[idxown]
        ac_route = traf.ap.route[idxown]
        iactwp = ac_route.iactwp
        if re.match('cruising.+',nameCurrentLayer) is not None and traf.flightphase[idxown] == 0 and iactwp > 0:
            # get the currect layers speed limits
            lowerSpdLimit = traf.layerLowerSpd[idxCurrentLayer][0]/kts
            upperSpdLimit = traf.layerUpperSpd[idxCurrentLayer][0]/kts

            if diff < -30:
                traf.speedupdate[idxown] = True
                stack.stack(f"SPD {traf.id[idxown]} {upperSpdLimit}")
                stack.stack(f"ECHO {traf.id[idxown]} is speeding up")
                print(f'{traf.id[idxown]} too SLOW')
            elif diff > 30:
                traf.speedupdate[idxown] = True
                stack.stack(f"SPD {traf.id[idxown]} {lowerSpdLimit}")
                stack.stack(f"ECHO {traf.id[idxown]} is slowing down")
                print(f'{traf.id[idxown]} too FAST')
            elif abs(diff) < 10 and traf.speedupdate[idxown] == True:
                stack.stack(f"{traf.id[idxown]} LNAV ON")
                stack.stack(f"{traf.id[idxown]} VNAV ON")
                stack.stack(f"ECHO {traf.id[idxown]} is going back to wpt speed")
                traf.speedupdate[idxown] = False