import json
import osmnx as ox
import geopandas as gp
from pyproj import CRS
import os
import rtree
from plugins.m2.nodesToCommands_v2 import PathPlanner, ScenarioMaker

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
    scenario = ScenarioMaker()

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

    lats, lons, turns, int_angle_list = path_planner.route(list_nodes_id)  # 1ºarg: route of node_ids

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
    print("int_angle_list: {}".format(int_angle_list))

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

    lines = scenario.Dict2Scn(scenario_dict, fplan_priority, fplan_arrivaltime, fplan_vehicle,
                              int_angle_list)
    return lines[-1].lstrip('00:00:00>')

graphs_dict={}
for i in graphs:
    j=i.rstrip(".gpkg")
    graphs_dict[j] = read_graph(GRAPH_LOCATION+'\\'+i)

#load aircraft data
aircraft = json.load(open(AIRCRAFT_LOCATION))

""" BlueSky plugin template. The text you put here will be visible
    in BlueSky as the description of your plugin. """

import numpy as np
from bluesky.tools.aero import kts, ft
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, tools #, settings, navdb, sim, scr
from shapely.geometry import Polygon, MultiPolygon, LineString,Point
import networkx as nx

def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity
    example = tactical_reroute()

    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'tactical_reroute',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }

    # init_plugin() should always return a configuration dict.
    return config

class tactical_reroute(core.Entity):
    ''' Example new entity object for BlueSky. '''
    def __init__(self):
        super().__init__()
        with self.settrafarrays():
            self.reroutes = np.array([],dtype=int)
        traf.reroutes = self.reroutes

    def create(self, n=1):
        super().create(n)
        self.reroutes[-n:] = 0
        traf.reroutes = self.reroutes

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

        if ownship.alt[acid] /ft != new_fpalt:
            stack.stack(f'DELRTE {ownship.id[acid]}')
            stack.stack(f'SPD {ownship.id[acid]} 0')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 ALT {ownship.id[acid]} {new_fpalt}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} {generate_stackcmd(new_nodeids=new_nodeids, G=temp_graph, alt=new_fpalt, droneid=ownship.id[acid],fp_landingLat=final_point[0],fp_landingLon=final_point[1],fplan_vehicle=ownship_type,fplan_priority=ownship.priority[acid])}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} SPD {ownship.id[acid]} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} LNAV {ownship.id[acid]} ON')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} VNAV {ownship.id[acid]} ON')
            # Patch for descendcheck bug, delete last wpt.
            stack.stack(f'DELWPT {ownship.id[acid]} {ownship_route.wpname[-1]}')
        else:
            stack.stack(f'DELRTE {ownship.id[acid]}')
            stack.stack(f'SPD {ownship.id[acid]} 0')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 {generate_stackcmd(new_nodeids=new_nodeids, G=temp_graph, alt=new_fpalt, droneid=ownship.id[acid],fp_landingLat=final_point[0],fp_landingLon=final_point[1],fplan_vehicle=ownship_type,fplan_priority=ownship.priority[acid])}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 SPD {ownship.id[acid]} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 LNAV {ownship.id[acid]} ON')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 VNAV {ownship.id[acid]} ON')
            # Patch for descendcheck bug, delete last wpt.
            stack.stack(f'DELWPT {ownship.id[acid]} {ownship_route.wpname[-1]}')

        self.reroutes[acid] = self.reroutes[acid] + 1
        traf.reroutes = self.reroutes

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
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} {generate_stackcmd(new_nodeids=new_nodeids, G=temp_graph, alt=new_fpalt, droneid=ownship.id[acid],fp_landingLat=final_point[0],fp_landingLon=final_point[1],fplan_vehicle=ownship_type,fplan_priority=ownship.priority[acid])}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} SPD {ownship.id[acid]} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} LNAV {ownship.id[acid]} ON')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} VNAV {ownship.id[acid]} ON')
            # Patch for descendcheck bug, delete last wpt.
            stack.stack(f'DELWPT {ownship.id[acid]} {ownship_route.wpname[-1]}')
        else:
            stack.stack(f'DELRTE {ownship.id[acid]}')
            stack.stack(f'SPD {ownship.id[acid]} 0')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 {generate_stackcmd(new_nodeids=new_nodeids, G=temp_graph, alt=new_fpalt, droneid=ownship.id[acid],fp_landingLat=final_point[0],fp_landingLon=final_point[1],fplan_vehicle=ownship_type,fplan_priority=ownship.priority[acid])}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 SPD {ownship.id[acid]} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 LNAV {ownship.id[acid]} ON')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 VNAV {ownship.id[acid]} ON')
            # Patch for descendcheck bug, delete last wpt.
            stack.stack(f'DELWPT {ownship.id[acid]} {ownship_route.wpname[-1]}')

        self.reroutes[acid] = self.reroutes[acid] + 1
        traf.reroutes = self.reroutes

        return True, f'GEOFENCE - {traf.id[acid]} has a new route'
