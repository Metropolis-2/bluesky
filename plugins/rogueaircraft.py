import numpy as np

import bluesky as bs
from bluesky import stack
from bluesky.core import Entity
from bluesky.core.simtime import timed_function

def init_plugin():
    ''' Plugin initialisation function. '''

    # initliaze rogue traffic
    roguetraffic = RogueTraffic()
    
    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'rogueaircraft',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',

        # update function
        'update':   roguetraffic.update,
        }

    # init_plugin() should always return a configuration dict.
    return config

class RogueTraffic(Entity):

    def __init__(self):
        super().__init__()

        self.rogue_level = 0
        self.potential_acids = {f'R{i}' for i in range(0,408)}

        with self.settrafarrays():
            self.rogue_bool = np.array([], dtype=np.bool8)

        bs.traf.roguetraffic = self



    def create(self, n=1):
        super().create(n)

        # default value of rogue bool is always False
        self.rogue_bool[-n:] = False

        return
    
    @staticmethod
    @stack.command
    def crerogue(acid:'txt', actype:'txt', aclat:'lat', aclon:'lon', achdg:'hdg', acalt:'alt', acspd:'spd'):
        '''Create a rogue aircraft.'''
        # First, create aircraft
        bs.traf.cre(acid, actype, aclat, aclon, achdg, acalt, acspd)

        # get the index of the rogue aircraft
        acidx = bs.traf.id2idx(acid)

        # Now set rogue bool to true
        bs.traf.roguetraffic.rogue_bool[acidx] = True


    @staticmethod
    @stack.command
    def roguelevel(level:'int'):
        '''Set the number of concurrent rogue aircrafts.'''
        
        bs.traf.roguetraffic.rogue_level = level

    def update(self):
        '''Update the rogue aircraft.'''

        # get the number of rogue aircrafts
        nrogue = np.sum(bs.traf.roguetraffic.rogue_bool)

        # if there are less aircraft than the specified number of rogue aircraft create them.
        if nrogue < bs.traf.roguetraffic.rogue_level and bs.traf.ntraf != nrogue:

            # get the number of rogue aircraft to create
            n_rogues_to_create = bs.traf.roguetraffic.rogue_level - nrogue

            # get the acids of the flying rogue airctaft
            existing_acids = set(np.array(bs.traf.id)[bs.traf.roguetraffic.rogue_bool])

            # get a numpy array of the potential acids
            potential_acids =  np.array(list(self.potential_acids - existing_acids))

            # randomly select n_rogues_to_create from potential acids
            selected_acids = np.random.choice(potential_acids, n_rogues_to_create, replace=False)

            # loop through the selected acids and create them
            for acid in selected_acids:
                stack.stack(f'PCALL rogues/{acid}.scn')
            
        return
