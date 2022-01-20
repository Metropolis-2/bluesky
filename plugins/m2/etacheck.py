""" BlueSky plugin template. The text you put here will be visible
    in BlueSky as the description of your plugin. """
from random import randint
import numpy as np
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, sim, tools #, settings, navdb, scr, tools
from datetime import datetime

turn_delay=\
    {'MP30':
        {
            15:3,
            10:4,
            5:6,
            2:8
        },
    'MP20':
        {
            15:1,
            10:1,
            5:3,
            2:5
        }
    }


### Initialization function of your plugin. Do not change the name of this
### function, as it is the way BlueSky recognises this file as a plugin.
def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity
    example = etaCheck()

    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'etacheck',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }
    # init_plugin() should always return a configuration dict.
    return config

class sta:
    def __init__(self, time:int, utctime, reroutes: int):
        self.time = time  # integer
        self.utctime = utctime
        self.reroutes = reroutes

class etaCheck(core.Entity):
    ''' Example new entity object for BlueSky. '''
    def __init__(self):
        super().__init__()

        with self.settrafarrays():
            self.orignwp = np.array([], dtype=int)
            self.sta = np.array([],dtype=object)
            self.eta = np.array([])
            self.delayed = np.array([],dtype=float)
            self.turns = np.array([],dtype=object)
            self.turnspeed = np.array([],dtype=object)

        traf.orignwp = self.orignwp
        traf.sta = self.sta
        traf.eta = self.eta
        traf.delayed = self.delayed
        traf.turns = self.turns
        traf.turnspeed = self.turnspeed

    def create(self, n=1):
        super().create(n)
        # After base creation we can change the values in our own states for the new aircraft
        self.orignwp[-n:] = 0
        self.sta[-n:] = sta(time=0,utctime=0,reroutes=0)
        self.eta[-n:] = 0
        self.delayed[-n:] = False
        self.turns[-n:] = 0
        self.turnspeed[-n:] = 0

        traf.orignwp = self.orignwp
        traf.sta = self.sta
        traf.eta = self.eta
        traf.delayed = self.delayed
        traf.turns = self.turns
        traf.turnspeed = self.turnspeed

    def delete(self, idx):
        super().delete(idx)
        # update traf
        traf.orignwp = self.orignwp
        traf.sta = self.sta
        traf.eta = self.eta
        traf.delayed = self.delayed
        traf.turns = self.turns
        traf.turnspeed = self.turnspeed

    @core.timed_function(name='update_eta', dt=1)
    def update(self):
        for i in traf.id:
            acid = traf.id2idx(i)
            ac_route = traf.ap.route[acid]

            if ac_route.nwp == 0:
                continue

            if ac_route.iactwp == -1:
                continue

            if self.sta[acid].time == 0:
                self.sta[acid].time, self.sta[acid].utctime = self.calc_eta(acid)
                print(f'{traf.id[acid]} sta: {self.sta[acid].utctime}')

            #todo update reroutes in sta class when reroute tactical

            self.eta[acid], _ = self.calc_eta(acid)
            #print(f'{acid} eta: {_}')

            diff = self.check_eta(acid)
            self.delayed[acid] = diff

            traf.orignwp = self.orignwp
            traf.sta = self.sta
            traf.eta = self.eta
            traf.delayed = self.delayed

    def calc_eta(self, acid: 'acid'):

        ownship = traf
        total_distance = 0
        total_time = 0

        # get the flightplan and details
        ac_route = ownship.ap.route[acid]
        iactwp = ac_route.iactwp

        if iactwp == ac_route.nwp - 2:
            print(f'ARRIVED {traf.id[acid]} {datetime.fromtimestamp(int(sim.utc.timestamp())).strftime("%Y-%m-%d, %H:%M:%S")}')

        next_lat = ac_route.wplat[iactwp]
        next_lon = ac_route.wplon[iactwp]
        next_alt = ac_route.wpalt[iactwp]

        # use standard aircraft cruising speed for the speed.
        ownship_type = traf.type[acid]
        if ownship_type == 'MP20':
            ac_gs=20*tools.aero.kts
        elif ownship_type == 'MP30':
            ac_gs = 30*tools.aero.kts
        else:
            ac_gs = 20*tools.aero.kts


        # get the current ownship aircraft state
        ac_lat = ownship.lat[acid]
        ac_lon = ownship.lon[acid]
        ac_vs = ownship.perf.vsmax[acid]
        ac_alt = ownship.alt[acid]


        distance, time = self.calc_leg(ac_lat,ac_lon,next_lat,next_lon,ac_alt,next_alt,ac_gs,ac_vs)

        total_distance += distance
        total_time += time
        # calculate rest of route
        for idx in range(iactwp, ac_route.nwp - 1):
            # stop the loop if it is at the final waypoint
            max_wpidx = np.argmax(ac_route.wpname) - 2
            if idx == max_wpidx:
                break

            cur_lat = ac_route.wplat[idx]
            cur_lon = ac_route.wplon[idx]
            cur_gs = ac_route.wpspd[idx]

            #TODO change the vsmax at to the applicable value
            cur_vs = ownship.perf.vsmax[acid]
            cur_alt = ac_route.wpalt[idx]

            next_lat = ac_route.wplat[idx + 1]
            next_lon = ac_route.wplon[idx + 1]
            next_alt = ac_route.wpalt[idx + 1]

            distance, time = self.calc_leg(cur_lat, cur_lon, next_lat, next_lon, cur_alt, next_alt, cur_gs, cur_vs)

            total_distance += distance
            total_time += time

        # determine the eta

        eta = sim.utc.timestamp()+total_time

        eta = eta + self.turnDelay(acid)
        date_time = datetime.fromtimestamp(int(eta)).strftime("%Y-%m-%d, %H:%M:%S")

        return eta, date_time

    def check_eta(self, acid: 'acid'):

        sta = self.sta[acid].time
        eta=self.eta[acid]
        diff = sta - eta
        # print(acid,diff)
        return diff

    def horizontal_leg(self, start_lat, start_lon, end_lat, end_lon, spd):
        qdr_to_next, distance = tools.geo.kwikqdrdist(start_lat, start_lon, end_lat, end_lon)
        distance = distance * tools.geo.nm #[m]

        time = distance / spd #[sec]
        return distance, time

    def vertical_leg(self,start_alt, end_alt, vs):

        distance = abs(start_alt - end_alt) #[m]
        time = distance/abs(vs) #[sec]
        return distance, time

    def calc_leg(self,start_lat, start_lon, end_lat, end_lon, start_alt, end_alt, spd, vs):
        if start_lat == end_lat and start_lon == end_lon:
            distance, time = self.vertical_leg(start_alt, end_alt, vs)
        else:
            distance,time = self.horizontal_leg(start_lat,start_lon, end_lat, end_lon, spd)

        return distance, time

    def turnDelay(self,acid:'acid'):
        turnspd = self.turnspeed[acid]
        turns = self.turns[acid]
        ac_route = traf.ap.route[acid]
        turnspd = turnspd[np.where(turns > ac_route.iactwp)]
        ownship_type = traf.type[acid]
        delay = 0
        for i in turnspd:
            delay += turn_delay[ownship_type][i]
        return delay

    @stack.command()
    def setturns(self, acid:'acid', *turnid: int):
        ''' set turnid's and turns for acid
            Arguments:
            - acid: aircraft id
            - turnid: one or more waypoint ids that are a turn
        '''
        self.turns[acid] = np.array(turnid)
        traf.turns = self.turns
        return True

    @stack.command()
    def setturnspds(self, acid:'acid', *turnspds: int):
        ''' set turnid's and turns for acid
            Arguments:
            - acid: aircraft id
            - turnspds: turnspeeds corresponding to turns in the order the waypoint ids of setturns were supplied.
        '''
        self.turnspeed[acid] = np.array(turnspds)
        traf.turnspeed = self.turnspeed
        return True

