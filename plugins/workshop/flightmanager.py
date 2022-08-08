
import numpy as np
import json
from datetime import datetime
from time import sleep

import bluesky as bs
from bluesky.core import Entity, timed_function
from bluesky import stack

from plugins.workshop import flightplanmaker as fp
from plugins.workshop import flighttelemetry as fte

flightmanager = None
def init_plugin():
    # Configuration parameters
    global flightmanager
    flightmanager = FlightManager()

    config = {
        'plugin_name': 'FLIGHTMANAGER',
        'plugin_type': 'sim',
    }
    return config

class FlightManager(Entity):
    def __init__(self):
        super().__init__()

        self.hold_sim = False
        
        with self.settrafarrays():
            self.virtual_ac = np.array([], dtype=bool)
            self.pprz_ids = np.array([], dtype=str)

            self.gs = np.array([], dtype=np.float32)
            self.vs = np.array([], dtype=np.float32)
        
    def create(self, n=1):
        super().create(n)
        self.virtual_ac[-n:] = True
        self.pprz_ids[-n:] = ''

        self.gs[-n:] = 0.0
        self.vs[-n:] = 0.0
            
    def convert_to_virtual(self, acidx):
        # TODO: go through stack and replace commands with virtual commands
        self.virtual_ac[acidx] = True
        self.pprz_ids[acidx] = ''
        stack.stack(f'LNAV {bs.traf.id[acidx]} ON')
        stack.stack(f'VNAV {bs.traf.id[acidx]} ON')
        return
    
    @timed_function(dt=0.05)
    def check_hold(self):
        # check if we are in the hold state
        if self.hold_sim:
            
            # now check if speeds of aircraft are less than 0.1 m/s
            if np.all(bs.traf.gs < 0.1) and np.all(bs.traf.vs < 0.1):
                # if so, then we can hold the simulation
                bs.sim.hold()
                self.hold_sim = False

    @timed_function(dt=1.0)
    def check_connections(self):
        now = datetime.now()

        for acidx in range(bs.traf.ntraf):

            # only do this for real aircraft
            if self.virtual_ac[acidx]:
                return

            time_diff = now - fte.telemetry.last_telemetry_update[acidx]
            # If more than 5 seconds then we convert to virtual aircraft
            if time_diff.total_seconds() > 5:
                self.convert_to_virtual(acidx)
    
    def checkactiveflightplan(self, acidx, active_fp_32bid):
        ''' Check if telemetry flight plan is the same as the one we have. '''

        # only check this if we have actually sent a flight plan
        if not fp.flightplans.fp_active[acidx]:
            return

        # check the current 32 bit id of the active flight plan,
        # if it is different from the one we have stored, then we have to push the flight plan
        # again because it did not sync
        
        if not str(fp.flightplans.drone_32bid[acidx]) == str(active_fp_32bid):
            print('different')
            print(fp.flightplans.drone_32bid[acidx])
            print(active_fp_32bid)
            # fp.flightplans.generate_fp_from_WP(acidx)

    # aircraft specific commands
    # must give acid to execute

    @stack.command
    def connect_telemetry(self, acid: str, pprz_id: str):
        '''Connect paparazzi telemetry to an existing vehicle'''
        # Make aircraft real and connect to pprz_id
        acidx = bs.traf.id2idx(acid)
        self.pprz_ids[acidx] = pprz_id
        self.virtual_ac[acidx] = False

    @stack.command()
    def sendfp(self, acid: 'acid', fp_file: str=None):
        fp.flightplans.generate_fp_from_WP(acid, fp_file)

    @stack.command()
    def takeoffac(self, acid: str):
        '''Takeoff'''
        self.send_command(acid, "TakeOff")

    @stack.command()
    def executefp(self, acid: str):
        '''Execute flight plan'''
        self.send_command(acid, "ExecuteFlightPlan")

    @stack.command()
    def holdac(self, acid: str):
        '''Hold'''
        self.send_command(acid, "Hold")

    @stack.command()
    def continuefp(self, acid: str):
        '''Continue'''
        self.send_command(acid, "Continue")

    @stack.command()
    def landac(self, acid: str):
        '''Land'''
        self.send_command(acid, "Land")

    # end of aircraft specifc commands

    # mak global commands
    @stack.command()
    def sendall(self):
        '''Make all flight plans for real aircraft'''

        for acidx, acid in enumerate(bs.traf.id):

          # if real aircraft send command
            if not self.virtual_ac[acidx]:
                fp.flightplans.generate_fp_from_WP(acidx)
            else:
                # TODO: virtual aircraft start flying
                ...

    @stack.command()
    def takeoffall(self):
        '''Takeoff all real aircraft'''
        for acidx, acid in enumerate(bs.traf.id):

            # if real aircraft send command
            if not self.virtual_ac[acidx]:
                self.send_command(acid, "TakeOff")
            else:
                # TODO: virtual aircraft start flying
                ...

    @stack.command()
    def executefpall(self):
        '''Execute flight plan for all aircraft'''
        for acidx, acid in enumerate(bs.traf.id):

            # if real aircraft send command
            if not self.virtual_ac[acidx]:
                self.send_command(acid, "ExecuteFlightPlan")

            else:
                # TODO: virtual aircraft start flying
                ...
    
    @stack.command()
    def holdall(self):
        '''Hold all aircraft'''
        for acidx, acid in enumerate(bs.traf.id):
            
            # get some values to remember speeds
            self.gs[acidx] = bs.traf.gs[acidx]
            self.vs[acidx] = bs.traf.vs[acidx]

            # if real aircraft send command
            if not self.virtual_ac[acidx]:
                self.send_command(acid, "Hold")
            else:
                # give all aircraft a speed of 0
                stack.stack(f'SPD {acid} 0')
                stack.stack(f'VS {acid} 0')
        
        # enable check that stops simulation if all aircraft have held
        self.hold_sim = True

    @stack.command()
    def continueall(self):
        '''Continue all aircraft'''
        for acidx, acid in enumerate(bs.traf.id):

            # if real aircraft send command
            if not self.virtual_ac[acidx]:
                self.send_command(acid, "Continue")
            else:
                stack.stack(f'SPD {acid} {self.gs[acidx]}')
                stack.stack(f'VS {acid} {self.vs[acidx]}')

                # only turn lnav and vnav on if there is a flight plan 
                if bs.traf.ap.route[acidx].nwp:
                    stack.stack(f'LNAV {bs.traf.id[acidx]} ON')
                    stack.stack(f'VNAV {bs.traf.id[acidx]} ON')

        # continue simulation
        bs.sim.op()

    @stack.command()
    def landall(self):
        '''Land all aircraft'''
        for acidx, acid in enumerate(bs.traf.id):

            # if real aircraft send command
            if not self.virtual_ac[acidx]:
                self.send_command(acid, "Land")
            else:
                # TODO: virtual aircraft land
                ...

    # end of global aircraft commands

    def send_command(self, acid, command):
        
        # get idx of aircraft and pprz id
        acidx = bs.traf.id2idx(acid)
        pprz_id =self.pprz_ids[acidx]

        # create command
        command_dict = {"Command": f"{command}"}

        # send command
        fp.flightplans.mqtt_client.publish(f'control/command/{pprz_id}', json.dumps(command_dict))
        sleep(0.1)

