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

# initialize random generator
rng = None

class RogueTraffic(Entity):

    def __init__(self):
        super().__init__()

        self.rogue_level = 0
        self.potential_acids = {f'R{i}' for i in range(0,408)}
        self.time_between_aircraft = 0

        with self.settrafarrays():
            self.rogue_bool = np.array([], dtype=np.bool8)

        bs.traf.roguetraffic = self
        
    def reset(self):
        bs.traf.roguetraffic.rogue_level = 0
        bs.traf.roguetraffic.time_between_aircraft = 0


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
    def roguelevel(level:'int', randomseed:'int'):
        '''Set the number of concurrent rogue aircrafts and random seed'''
        
        bs.traf.roguetraffic.rogue_level = level

        global rng
        rng = np.random.default_rng(randomseed)
        
        # We want to spawm the first rogue aircraft over the first 15 minutes of the simulation
        bs.traf.roguetraffic.time_between_aircraft = 900 / level

    def update(self):
        '''Update the rogue aircraft.'''
        # If we're past 1 hour of simulation time, skip
        if bs.sim.simt > 3600:
            return
        
        if bs.traf.roguetraffic.rogue_level == 0 or bs.traf.roguetraffic.time_between_aircraft == 0:
            return

        # get the number of rogue aircrafts
        nrogue = np.sum(bs.traf.roguetraffic.rogue_bool)
        
        # If we're in the first 15 minutes, spawn aircraft according to time_between_aircraft
        if bs.sim.simt < 900:
            # Check how many aircraft should be spawned by now
            nrogue_should = int(bs.sim.simt / bs.traf.roguetraffic.time_between_aircraft)
            
            # Check how many aircraft we need to spawn
            n_rogues_to_create = nrogue_should - nrogue
            
            # If greater than 0, spawn the rogue aircraft
            if n_rogues_to_create > 0:
                # get the acids of the flying rogue airctaft
                existing_acids = set(np.array(bs.traf.id)[bs.traf.roguetraffic.rogue_bool])

                # get a numpy array of the potential acids
                potential_acids =  np.sort(np.array(list(self.potential_acids - existing_acids)))

                # randomly select n_rogues_to_create from potential acids
                selected_acids = rng.choice(potential_acids, n_rogues_to_create, replace=False)

                # loop through the selected acids and create them
                for acid in selected_acids:
                    stack.stack(f'PCALL rogues/{acid}.scn')
                    
            return

        # if there are less aircraft than the specified number of rogue aircraft create them.
        if nrogue < bs.traf.roguetraffic.rogue_level and bs.traf.ntraf != nrogue:

            # get the number of rogue aircraft to create
            n_rogues_to_create = bs.traf.roguetraffic.rogue_level - nrogue

            # get the acids of the flying rogue airctaft
            existing_acids = set(np.array(bs.traf.id)[bs.traf.roguetraffic.rogue_bool])

            # get a numpy array of the potential acids
            potential_acids =  np.sort(np.array(list(self.potential_acids - existing_acids)))

            # randomly select n_rogues_to_create from potential acids
            selected_acids = rng.choice(potential_acids, n_rogues_to_create, replace=False)

            # loop through the selected acids and create them
            for acid in selected_acids:
                stack.stack(f'PCALL rogues/{acid}.scn')
            
        return
