from random import randint
import numpy as np
import copy
import json
import osmnx as ox
import geopandas as gp
from pyproj import CRS
import os
import rtree
from plugins.routingTactical import PathPlanner, ScenarioMaker

# Import the global bluesky objects. Uncomment the ones you need
import bluesky as bs
from bluesky import core, stack, traf, sim, settings  # , navdb, sim, scr, tools
from bluesky.tools.aero import ft, kts
import plugins.m2.descendcheck as descendcheck
import plugins.m2.ingeoFence as ingeoFence
import plugins.m2.overshootcheck as overshootcheck
import plugins.m2.etacheck as etacheck
import plugins.m2.speed_update as speed_update
import plugins.geofence as geofence_TUD
import networkx as nx

'''
These switches give the option of turning on or off specific plugins.
Set to False if plugin must be off.
'''
ingeofence = True
overshoot = True
etachecker = True
speedupdate = True
rerouting = True
descendCheck = True

### Initialization function of your plugin. Do not change the name of this
### function, as it is the way BlueSky recognises this file as a plugin.
def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity
    checkstate = checkState()

    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name': 'checkstate',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type': 'sim',
    }

    # init_plugin() should always return a configuration dict.
    return config
#creation of the sta object that will store multiple time related values.
class sta:
    def __init__(
            self,
            time:int,
            sta_dt,
            reroutes: int,
            atd,
            ata,
            atd_dt,
            ata_dt
    ):
        self.time = time  # integer
        self.sta_dt = sta_dt
        self.reroutes = reroutes
        self.atd = atd
        self.atd_datetime = atd_dt
        self.ata = ata
        self.ata_datetime = ata_dt

class checkState(core.Entity):
    ''' Example new entity object for BlueSky. '''

    def __init__(self):
        super().__init__()
        with self.settrafarrays():
            self.startDescend = np.array([], dtype=bool)  # array of booleans to check if descend can start
            self.overshot = np.array([], dtype=bool)
            self.wptdist = np.array([])
            self.ingeofence = np.array([], dtype=bool)
            self.acingeofence = np.array([], dtype=bool)
            self.geoPoly = None
            self.geoPoly_vert = None
            self.geoDictOld = dict()

            #etacheck
            self.orignwp = np.array([], dtype=int)
            self.sta = np.array([],dtype=object)
            self.eta = np.array([])
            self.delayed = np.array([],dtype=float)
            self.turns = np.array([],dtype=object)
            self.turnspeed = np.array([],dtype=object)


        # update traf
        traf.overshot = self.overshot
        traf.wptdist = self.wptdist
        traf.ingeofence = self.ingeofence
        traf.acingeofence = self.acingeofence
        traf.geoPoly = self.geoPoly
        traf.geoPoly_vert = self.geoPoly_vert
        traf.geoDictOld = self.geoDictOld
        traf.startDescend = self.startDescend

        #etacheck
        traf.orignwp = self.orignwp
        traf.sta = self.sta
        traf.eta = self.eta
        traf.delayed = self.delayed
        traf.turns = self.turns
        traf.turnspeed = self.turnspeed

        self.reference_ac = []
    def create(self, n=1):
        ''' This function gets called automatically when new aircraft are created. '''
        # Don't forget to call the base class create when you reimplement this function!
        super().create(n)
        self.startDescend[-n:] = False
        self.overshot[-n:] = False
        self.wptdist[-n:] = 99999
        self.ingeofence[-n:] = False
        self.acingeofence[-n:] = False

        #etacheck
        self.orignwp[-n:] = 0
        self.sta[-n:] = sta(time=0, sta_dt=0, reroutes=0, ata=0, ata_dt=0, atd=0, atd_dt=0)
        self.eta[-n:] = 0
        self.delayed[-n:] = False
        self.turns[-n:] = 0
        self.turnspeed[-n:] = 0

        # update traf
        traf.overshot = self.overshot
        traf.wptdist = self.wptdist
        traf.ingeofence = self.ingeofence
        traf.acingeofence = self.acingeofence
        traf.startDescend = self.startDescend

        #etacheck
        traf.orignwp = self.orignwp
        traf.sta = self.sta
        traf.eta = self.eta
        traf.delayed = self.delayed
        traf.turns = self.turns
        traf.turnspeed = self.turnspeed


    def delete(self, idx):
        super().delete(idx)

        # update traf
        traf.overshot = self.overshot
        traf.wptdist = self.wptdist
        traf.ingeofence = self.ingeofence
        traf.acingeofence = self.acingeofence
        traf.startDescend = self.startDescend

        #etacheck
        traf.orignwp = self.orignwp
        traf.sta = self.sta
        traf.eta = self.eta
        traf.delayed = self.delayed
        traf.turns = self.turns
        traf.turnspeed = self.turnspeed

    def reset(self):
        ''' Reset area state when simulation is reset. '''
        super().reset()
        # update traf
        traf.overshot = self.overshot
        traf.wptdist = self.wptdist
        traf.ingeofence = self.ingeofence
        traf.acingeofence = self.acingeofence
        traf.startDescend = self.startDescend
        traf.geoPoly = self.geoPoly
        traf.geoDictOld = self.geoDictOld
        traf.geoPoly_vert = self.geoPoly_vert

        self.reference_ac = []


    @core.timed_function(name='descendcheck', dt=5)
    def update(self):
        for i in traf.id:
            idx = traf.id2idx(i)
            if traf.priority[idx] != 5:
                '''
                Ingeofence Plugin
                This plugin checks if the current route of the aircraft interferes with a geofence.
                If so, the drone is rerouted, except when the geofence surrounds the drone or when
                the vertiport of the drone is in the geofence. If that is the case the drone ignores
                the geofence.
                '''
                if ingeofence:
                    # only run this code if there actually is a geofence somewhere and we are on the way
                    if geofence_TUD.Geofence.geo_save_dict != dict() and traf.ap.route[idx].iactwp > 1:

                        # update old dict to ensure we only recreate the multipolygon if something changed
                        if self.geoDictOld != geofence_TUD.Geofence.geo_save_dict:
                            self.geoDictOld = copy.deepcopy(geofence_TUD.Geofence.geo_save_dict)
                            self.geoPoly, self.geoPoly_vert = ingeoFence.create_multipoly(geofences=geofence_TUD.Geofence.geo_save_dict)

                        routeval, acval = ingeoFence.checker(acid=idx, multiGeofence=self.geoPoly, multiGeofence_vert=self.geoPoly_vert)
                        self.ingeofence[idx] = routeval
                        self.acingeofence[idx] = acval

                        traf.ingeofence = self.ingeofence
                        traf.acingeofence = self.acingeofence
                        traf.geoPoly = self.geoPoly
                        traf.geoDictOld = self.geoDictOld

                '''
                Overshoot Plugin
                This plugin checks if the drone has overshot its destination. The plugin uses a simple logic,
                when the distance between the drone and its final waypoint +50 meters increases
                whilst the final waypoint is active, the destination is overshot. When overshot, the drone gets
                rerouted in the reso 0 layer (multidirectional).
                '''
                if overshoot:
                    # overshoot checker (only if there is a route and we are almost at destination):
                    if traf.ap.route[idx].iactwp != -1 and traf.ap.route[idx].iactwp == np.argmax(traf.ap.route[idx].wpname):

                        dist = overshootcheck.calc_dist(idx)
                        val = overshootcheck.checker(idx, dist)
                        self.overshot[idx] = val
                        traf.overshot = self.overshot
                '''
                Etacheck Plugin
                This plugins calculates STA, ETA, ATD and ATA. ETA and STA is calculated by summing all route segments
                whilst adding additional delay for each turn, to account for acceleration and decelleration. ATA and
                ATD are simply logged at the moment of activating the last and first waypoint respectively.
                '''
                if etachecker:
                    acid = traf.id2idx(i)
                    ac_route = traf.ap.route[acid]
                    # Check if there is a route.
                    if ac_route.iactwp != -1 and ac_route.nwp != 0:

                        #First time calculation of the atd
                        if self.sta[acid].atd == 0:
                            self.sta[acid].atd = sim.utc.timestamp()
                            self.sta[acid].atd_datetime = etacheck.secToDT(sim.utc.timestamp())

                        #First time the last waypoint gets active, the ATA is logged
                        if ac_route.iactwp == ac_route.nwp - 1 and self.sta[acid].ata == 0:
                            self.sta[acid].ata = sim.utc.timestamp()
                            self.sta[acid].ata_datetime = etacheck.secToDT(sim.utc.timestamp())

                        # First time calculation of STA
                        if self.sta[acid].time == 0:
                            self.sta[acid].time = etacheck.calc_eta(acid)
                            self.sta[acid].sta_dt = etacheck.secToDT(self.sta[acid].sta_dt)

                        # Keep updating the ETA, until activation of last waypoint.
                        if ac_route.iactwp < ac_route.nwp - 1:
                            self.eta[acid] = etacheck.calc_eta(acid)
                            sta = self.sta[acid].time
                            eta = self.eta[acid]
                            diff = sta - eta
                            self.delayed[acid] = diff

                        #update Traffic variables
                        traf.orignwp = self.orignwp
                        traf.sta = self.sta
                        traf.eta = self.eta
                        traf.delayed = self.delayed

                '''
                Speedupdate Plugin
                This plugin updates the speed of the aircraft if there is a significant delay (i.e. large delta
                between STA and ETA) according to the Etacheck Plugin
                '''
                if speedupdate:
                    idx = traf.id2idx(i)
                    ac_diff = traf.delayed[idx]
                    ac_route = traf.ap.route[idx]
                    iactwp = ac_route.iactwp
                    if iactwp == ac_route.nwp - 2:
                        continue
                    if traf.resostrategy[idx] == "None":
                        speed_update.setSpeed(idx, ac_diff)

                # descend checker
                # if for some reason the startDescend boolean is true, but the aircraft was not deleted,
                # then delete the aircraft when it is below 1 ft
                # Delete the last waypoint at 0ft and 0kts
                if descendCheck:
                    if traf.id[idx] not in self.reference_ac and traf.ap.route[idx].iactwp > -1 and not traf.loiter.loiterbool[idx]:
                        traf.ap.route[idx].wpspd[-2] = 1.0
                        lastwpname = traf.ap.route[idx].wpname[-1]
                        stack.stack(f"DELWPT {traf.id[idx]} {lastwpname}")
                        self.reference_ac.append(traf.id[idx])


                    if not self.startDescend[idx] and not traf.loiter.loiterbool[idx] and traf.resostrategy[idx] == 'None':
                        self.startDescend[idx] = descendcheck.checker(idx)
                    elif traf.alt[idx] < 1.0 * ft:
                        stack.stack(f"{traf.id[idx]} DEL")

                    traf.startDescend = self.startDescend


    @stack.command
    def echoacgeofence(self, acid: 'acid'):
        ''' Print the if an acid is in conflict with a geofence '''
        geofence = self.getacgeofence(acid)
        return True, f'{traf.id[acid]} geofence conflict {geofence}.'

    def getacgeofence(self, acid: 'acid'):
        ''' return the bool value in ingeofence of a specific acid '''
        val = self.ingeofence[acid]
        return val

    @stack.command
    def echoacovershot(self, acid: 'acid'):
        ''' Print the if an acid is has overshot or not '''
        overshot = self.getacovershot(acid)
        if overshot:
            return True, f'{traf.id[acid]} has overshot.'
        elif not overshot:
            return True, f'{traf.id[acid]} has not overshot.'

    def getacovershot(self, acid: 'acid'):
        ''' return the bool value in ingeofence of a specific acid '''
        val = self.overshot[acid]
        return val

    @stack.command()
    def setturns(self, acid:'acid', *turnid: int):
        ''' set turnid's and turns for acid
            Arguments:
            - acid: aircraft id
            - turnid: one or more waypoint ids that are a turn
        '''
        self.turns[acid] = np.array(turnid)
        self.turns[acid] = self.turns[acid] -1
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

    @stack.command
    def rerouteovershoot(self, acid: 'acid'):
        ownship = traf
        ownship_route= traf.ap.route[acid]
        last_wpidx = np.argmax(ownship_route.wpname)

        initial_point = (ownship.lat[acid],ownship.lon[acid])
        final_point = (ownship_route.wplat[last_wpidx], ownship_route.wplon[last_wpidx])
        new_nodeids = shortest_path(
            graphs_dict['multi']['graph'],
            initial_point,final_point,True)

        temp_graph = graphs_dict['multi']['graph'].copy()
        new_fpalt = 30
        ownship_type = ownship.type[acid]

        try:
            new_fpgs = aircraft[ownship_type]['envelop']['v_max'] / kts
        except:
            new_fpgs = 12.8611 / kts #if drone type is not found default to 25 kts

        if ownship.alt[acid] / ft != new_fpalt:
            stack.stack(f'DELRTE {ownship.id[acid]}')
            stack.stack(f'SPD {ownship.id[acid]} 0')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 ALT {ownship.id[acid]} {new_fpalt}')
            l = generate_stackcmd(new_nodeids=new_nodeids, G=temp_graph, alt=new_fpalt, droneid=ownship.id[acid],
                                  fp_landingLat=final_point[0], fp_landingLon=final_point[1],
                                  fplan_vehicle=ownship_type,
                                  fplan_priority=ownship.priority[acid])
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} {l[0]}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} {l[1]}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} {l[2]}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} SPD {ownship.id[acid]} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATSPD {new_fpgs} LNAV {ownship.id[acid]} ON')
            stack.stack(f'{ownship.id[acid]} ATSPD {new_fpgs} VNAV {ownship.id[acid]} ON')
            # Patch for descendcheck bug, delete last wpt.
            self.reference_ac.remove(ownship.id[acid])
            self.startDescend[acid] = False
        else:
            stack.stack(f'DELRTE {ownship.id[acid]}')
            stack.stack(f'SPD {ownship.id[acid]} 0')
            l = generate_stackcmd(new_nodeids=new_nodeids, G=temp_graph, alt=new_fpalt, droneid=ownship.id[acid],
                                  fp_landingLat=final_point[0], fp_landingLon=final_point[1],
                                  fplan_vehicle=ownship_type,
                                  fplan_priority=ownship.priority[acid])
            stack.stack(f'{ownship.id[acid]} ATSPD 0 {l[0]}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 {l[1]}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 {l[2]}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 SPD {ownship.id[acid]} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 LNAV {ownship.id[acid]} ON')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 VNAV {ownship.id[acid]} ON')
            # Patch for descendcheck bug, delete last wpt.
            self.reference_ac.remove(ownship.id[acid])
            self.startDescend[acid] = False

        self.sta[acid].reroutes = self.sta[acid].reroutes + 1
        self.sta[acid].time = 0
        self.sta[acid].sta_dt = 0
        traf.sta = self.sta

        return True, f'OVERSHOT - {traf.id[acid]} has a new route'

    @stack.command
    def reroutegeofence(self, acid: 'acid'):
        ownship = traf
        ownship_route= traf.ap.route[acid]
        last_wpidx = np.argmax(ownship_route.wpname)

        initial_point = (ownship.lat[acid],ownship.lon[acid])
        final_point = (ownship_route.wplat[last_wpidx], ownship_route.wplon[last_wpidx])
        idxCurrentLayer = np.where(ownship.aclayername[acid] == ownship.layernames)[0]
        layerDirection = ownship.layerdirection[idxCurrentLayer][0]
        layerName = ownship.aclayername[acid]

        temp_graph = graphs_dict[layerDirection]['graph'].copy()


        for j in ownship.geoPoly:
            values = {}
            intersections = list(graphs_dict[layerDirection]['idx_tree'].intersection(j.bounds))
            list_intersecting_edges = [graphs_dict[layerDirection]['edges_rtree'][ii] for ii in intersections]
            for i in list_intersecting_edges:
                values[i] = {'pesoL': 9999}
            nx.set_edge_attributes(temp_graph, values)

        new_nodeids = shortest_path(temp_graph,initial_point,final_point,True)

        if ownship.alt[acid] == 0:
            new_fpalt = 0
        elif 'reso' in layerName:
            new_fpalt = ownship.layerLowerAlt[idxCurrentLayer][0] / ft
        else:
            new_fpalt = ownship.layerLowerAlt[idxCurrentLayer+1][0] / ft

        ownship_type = ownship.type[acid]
        try:
            new_fpgs = aircraft[ownship_type]['envelop']['v_max'] / kts
        except:
            new_fpgs = 12.8611 / kts #if drone type is not found default to 25 kts

        if ownship.alt[acid] /ft != new_fpalt:
            stack.stack(f'DELRTE {ownship.id[acid]}')
            stack.stack(f'SPD {ownship.id[acid]} 0')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 ALT {ownship.id[acid]} {new_fpalt}')
            l = generate_stackcmd(new_nodeids=new_nodeids, G=temp_graph, alt=new_fpalt, droneid=ownship.id[acid],
                              fp_landingLat=final_point[0], fp_landingLon=final_point[1], fplan_vehicle=ownship_type,
                              fplan_priority=ownship.priority[acid])
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} {l[0]}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} {l[1]}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} {l[2]}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} SPD {ownship.id[acid]} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} LNAV {ownship.id[acid]} ON')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} VNAV {ownship.id[acid]} ON')
            # Patch for descendcheck bug, delete last wpt.
            self.reference_ac.remove(ownship.id[acid])
            self.startDescend[acid] = False
        else:
            stack.stack(f'DELRTE {ownship.id[acid]}')
            stack.stack(f'SPD {ownship.id[acid]} 0')
            l = generate_stackcmd(new_nodeids=new_nodeids, G=temp_graph, alt=new_fpalt, droneid=ownship.id[acid],
                              fp_landingLat=final_point[0], fp_landingLon=final_point[1], fplan_vehicle=ownship_type,
                              fplan_priority=ownship.priority[acid])
            stack.stack(f'{ownship.id[acid]} ATSPD 0 {l[0]}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 {l[1]}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 {l[2]}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 SPD {ownship.id[acid]} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 LNAV {ownship.id[acid]} ON')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 VNAV {ownship.id[acid]} ON')
            # Patch for descendcheck bug, delete last wpt.
            self.reference_ac.remove(ownship.id[acid])
            self.startDescend[acid] = False


        self.sta[acid].reroutes = self.sta[acid].reroutes + 1
        self.sta[acid].time = 0
        self.sta[acid].sta_dt = 0
        traf.sta = self.sta

        return True, f'GEOFENCE - {traf.id[acid]} has a new route'

if rerouting:
    #Set accordingly
    GRAPH_LOCATION = 'plugins\\m2\\graphs'
    AIRCRAFT_LOCATION = 'data\\performance\\OpenAP\\rotor\\aircraft.json'

    #list all graphs in GRAPH_LOCATION
    graphs = []
    for file in os.listdir(GRAPH_LOCATION):
        if file.endswith(".gpkg"):
            graphs.append(file)

    #Function to obtain the dataframes of edges
    def edge_gdf_format_from_gpkg(edges):
        edge_dict = edges.to_dict()
        edge_gdf = gp.GeoDataFrame(edge_dict, crs = CRS.from_user_input(4326))
        edge_gdf.set_index(['u', 'v', 'key'], inplace = True)
        return edge_gdf

    #Function to obtain the dataframes of nodes
    def node_gdf_format_from_gpkg(nodes):
        node_dict = nodes.to_dict()
        node_gdf = gp.GeoDataFrame(node_dict, crs = CRS.from_user_input(4326))
        node_gdf.set_index(['osmid'], inplace = True)
        return node_gdf

    # %%
    # Function to calculate the nodes route from an origin (lat, lon) to a destination (lat, lon)
    def shortest_path(G, origin, destination, mode):
        #Calculate the closest node of both the origin and the destination to form the route
        origin_node, d1 = ox.nearest_nodes(G, origin[1], origin[0], return_dist = True)# (lon, lat)
        dest_node, d2 = ox.nearest_nodes(G, destination[1], destination[0], return_dist = True)# (lon, lat)
        print("shortest_path()=> From {} to {}".format(origin_node,dest_node))
        if mode:
            osmid_route = ox.shortest_path(G, origin_node, dest_node, weight = 'pesoL')
        else:
            osmid_route = ox.shortest_path(G, origin_node, dest_node)
        return osmid_route

    def read_graph(gpkg):
        print(f'loading {gpkg}')
        nodes = gp.read_file(gpkg, layer='nodes')
        edges = gp.read_file(gpkg, layer='edges')
        nodmod = node_gdf_format_from_gpkg(nodes)
        edmod = edge_gdf_format_from_gpkg(edges)
        graph = ox.graph_from_gdfs(nodmod, edmod)

        #construct rtree of the edges
        print(f'constructing {gpkg} rtree')
        edges_gdf = edges.copy()
        edge_dict = {}
        idx_tree = rtree.index.Index()
        i = 0
        for index, row in edges_gdf.iterrows():
            geom = row.loc['geometry']
            edge_dict[i] = (int(row.u), int(row.v), int(row.key))
            idx_tree.insert(i, geom.bounds)
            i += 1

        graph_dict={'graph':graph,'nodes':nodes,'edges':edges,'edges_rtree':edge_dict, 'idx_tree':idx_tree}

        return graph_dict

    def generate_stackcmd(
            new_nodeids,
            G,
            alt,
            droneid,
            fplan_priority,
            fplan_vehicle,
            fp_landingLat,
            fp_landingLon,



    ):
        # Total Airspace Unc GPKG

        path_planner = PathPlanner(G, angle_cutoff=45)
        scenario = ScenarioMaker(logger=None)

        fplan_id = droneid
        start_time = 0
        fplan_priority = str(fplan_priority)
        fplan_arrivaltime = "198"
        fplan_vehicle = fplan_vehicle
        operational_altitude = alt

        fp_landingLat = fp_landingLat
        fp_landingLon = fp_landingLon
        fp_landingAlt = 0

        list_nodes_id = new_nodeids

        lats, lons, turns, turn_indexs, turn_speeds, int_angle_list, _ = path_planner.route(list_nodes_id)  # 1ºarg: route of node_ids

        alts = []
        while (len(alts) != len(lats)):
            alts.append(operational_altitude)

        init_lat_route = lats[0]
        init_lon_route = lons[0]
        print("init position route {},{}".format(init_lat_route, init_lon_route))
        final_lat_route = lats[-1]
        final_lon_route = lons[-1]
        print("final position route {},{}".format(final_lat_route, final_lon_route))


        # LANDING
        if (final_lat_route != fp_landingLat or final_lon_route != fp_landingLon):
            lats.insert(len(lats), final_lat_route)
            lons.insert(len(lats), final_lon_route)
            alts.insert(len(lats), fp_landingAlt)
            turns.insert(len(lats), False)

        # Insert at the end (landing)
        lats.insert(len(lats), fp_landingLat)
        lons.insert(len(lons), fp_landingLon)
        alts.insert(len(alts), fp_landingAlt)
        turns.insert(len(turns), False)

        print("lats: {}".format(lats))
        print("lons: {}".format(lons))
        print("alts: {}".format(alts))
        print("turns: {}".format(turns))
#        print("int_angle_list: {}".format(int_angle_list))

        # Initialize scenario
        scenario_dict = dict()
        # Create dictionary
        scenario_dict[fplan_id] = dict()  # key is the id of fplan
        # Add start time
        scenario_dict[fplan_id]['start_time'] = start_time
        # Add lats
        scenario_dict[fplan_id]['lats'] = lats
        # Add lons
        scenario_dict[fplan_id]['lons'] = lons
        # Add alts
        scenario_dict[fplan_id]['alts'] = alts
        # Add turnbool
        scenario_dict[fplan_id]['turnbool'] = turns

        print("scenario_dict: {}".format(scenario_dict))

        lines = scenario.Dict2Scn('temp.scn', scenario_dict, fplan_priority, fplan_arrivaltime, fplan_vehicle, int_angle_list, turn_indexs, turn_speeds)

        #new_turns = np.where(turns)
        #int_angle_list = np.array(int_angle_list)[np.where(turns)]
        #turn_speeds = []
        #turnspds = ' '.join(map(str, turn_speeds))
        #turns = ' '.join(map(str, new_turns))

        for i in range(len(lines)):
            lines[i] = lines[i].lstrip("00:00:00>").rstrip(" \n")
        return lines

    graphs_dict={}
    for i in graphs:
        j=i.rstrip(".gpkg")
        graphs_dict[j] = read_graph(GRAPH_LOCATION+'\\'+i)

    #load aircraft data
    aircraft = json.load(open(AIRCRAFT_LOCATION))
