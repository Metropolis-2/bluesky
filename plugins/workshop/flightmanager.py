
import numpy as np
import json
from datetime import datetime
from time import sleep

import bluesky as bs
from bluesky.core import Entity, timed_function
from bluesky import stack
from bluesky.tools.aero import ft
from bluesky.tools.geo import qdrdist

from plugins.workshop import flightplanmaker as fp
from plugins.workshop import flighttelemetry as fte

flightmanager = None
def init_plugin():
    # Configuration parameters
    global flightmanager
    flightmanager = FlightManager()

    config = {
        'plugin_name': 'FLIGHTMANAGER',
        'plugin_type': 'sim'
    }
    return config

class FlightManager(Entity):
    def __init__(self):
        super().__init__()
        
        with self.settrafarrays():
            self.virtual_ac = np.array([], dtype=bool)
            self.pprz_ids = np.array([], dtype=str)
        
    def create(self, n=1):
        super().create(n)
        self.virtual_ac[-n:] = False
        self.pprz_ids[-n:] = ''
            
    def convert_to_virtual(self, acidx):
        self.virtual_ac[acidx] = True
        self.pprz_ids[acidx] = ''
        stack.stack(f'{bs.traf.id[acidx]} LNAV ON')
        return
    
    # @timed_function(dt=1.0)
    # def check_connections(self):
    #     now = datetime.now()
    #     # TODO: Only fo this check for real aircraft
    #     for acidx in range(bs.traf.ntraf):
    #         time_diff = now - fte.telemetry.last_telemetry_update[acidx]
    #         # If more than 5 seconds then we convert to virtual aircraft
    #         if time_diff.total_seconds() > 5:
    #             self.convert_to_virtual(acidx)
    
    def updateflightplan(self):
        ...
        # TODO: implement update flight plan
        # TODO: remember to send an update id if flight plan is updated
    
    def checkactiveflightplan(self):
        ...
        # TODO: implement check active flight plan.
        # TODO: ensure that flight plan maker matches telemetry id

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

            # if real aircraft send command
            if not self.virtual_ac[acidx]:
                self.send_command(acid, "Hold")
            else:
                # TODO: virtual aircraft hold
                ...
    
    @stack.command()
    def continueall(self):
        '''Continue all aircraft'''
        for acidx, acid in enumerate(bs.traf.id):

            # if real aircraft send command
            if not self.virtual_ac[acidx]:
                self.send_command(acid, "Continue")
            else:
                # TODO: virtual aircraft continue route
                ...

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

