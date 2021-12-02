""" BlueSky plugin template. The text you put here will be visible
    in BlueSky as the description of your plugin. """
from random import randint
import numpy as np
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, sim, tools #, settings, navdb, scr, tools
from datetime import datetime

everis_sta=False

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
    def __init__(self, time, utctime,reroute=False):
        self.time = time  # integer
        self.utctime = utctime
        self.reroute = reroute# datetime

class etaCheck(core.Entity):
    ''' Example new entity object for BlueSky. '''
    def __init__(self):
        super().__init__()

        with self.settrafarrays():
            self.orignwp = np.array([], dtype=int)
            self.sta = np.array([],dtype=object)
            self.eta = np.array([])
            self.delayed = np.array([],dtype=float)

        traf.orignwp = self.orignwp
        traf.sta = self.sta
        traf.eta = self.eta
        traf.delayed = self.delayed

    def create(self, n=1):
        super().create(n)
        # After base creation we can change the values in our own states for the new aircraft
        self.orignwp[-n:] = 0
        self.sta[-n:] = 0

        traf.orignwp = self.orignwp
        traf.sta = self.sta

    @core.timed_function(name='update_eta', dt=5)
    def update(self):
        if everis_sta:
            for i in traf.id:
                acid = traf.id2idx(i)
                ac_route = traf.ap.route[acid]
                nwp = ac_route.nwp
                orignwp = self.orignwp[acid]

                if nwp == 0:
                    continue
                if self.sta[acid] == 0:
                    continue

                self.eta[acid] = self.calc_eta(acid)

                diff = self.check_eta(acid)
                self.delayed[acid] = diff



        if not everis_sta:
            for i in traf.id:
                acid = traf.id2idx(i)
                ac_route = traf.ap.route[acid]
                nwp = ac_route.nwp
                orignwp = self.orignwp[acid]

                if nwp == 0:
                    continue

                if nwp != orignwp:
                    self.sta[acid] = self.calc_eta(acid)
                    self.orignwp[acid] = nwp

                self.eta[acid] = self.calc_eta(acid)

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
        next_lat = ac_route.wplat[iactwp]
        next_lon = ac_route.wplon[iactwp]
        next_alt = ac_route.wpalt[iactwp]

        # use previous waypoint speed as aircraft speed since actual speed results in infinte or to great delay when hovering
        try:
            ac_gs =ac_route.wpspd[iactwp - 1]
        except:
            ac_gs = ac_route.wpspd[iactwp]

        # get the current ownship aircraft state
        ac_lat = ownship.lat[acid]
        ac_lon = ownship.lon[acid]
        ac_vs = ownship.perf.vsmax[acid]
        ac_alt = ownship.alt[acid]


        distance, time = self.calc_leg(ac_lat,ac_lon,next_lat,next_lon,ac_alt,next_alt,ac_gs,ac_vs)

        total_distance += distance
        total_time += time

        # calculate rest of route
        for idx in range(iactwp, ac_route.nwp + 1):
            # stop the loop if it is at the final waypoint
            max_wpidx = np.argmax(ac_route.wpname)
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

        return eta

    def check_eta(self, acid: 'acid'):

        if everis_sta:
            sta = self.sta[acid].time
        if not everis_sta:
            sta = self.sta[acid]
        eta = self.eta[acid]

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

    @stack.command
    def setsta(self, acid: 'acid',time):
        date_time = datetime.fromtimestamp(int(sim.utc.timestamp()+time)).strftime("%Y-%M-%d, %H:%M:%S")
        self.sta[acid] = sta(int(time),str(date_time))
        traf.sta=self.sta
        return True, f'{traf.id[acid]} STA is set to {date_time}'
