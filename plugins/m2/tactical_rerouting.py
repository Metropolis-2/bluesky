import json
import osmnx as ox
import geopandas as gp
from pyproj import CRS
import os
import re

#Set accordingly
GRAPH_LOCATION = 'plugins\\m2\\graphs'
AIRCRAFT_LOCATION = 'data\\performance\\OpenAP\\rotor\\aircraft.json'

#list all graphs in GRAPH_LOCATION
graphs = os.listdir(GRAPH_LOCATION)

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
    nodes = gp.read_file(gpkg, layer='nodes')
    edges = gp.read_file(gpkg, layer='edges')
    nodmod = node_gdf_format_from_gpkg(nodes)
    edmod = edge_gdf_format_from_gpkg(edges)
    graph = ox.graph_from_gdfs(nodmod, edmod)
    graph_dict={'graph':graph,'nodes':nodes,'edges':edges}
    return graph_dict

#TODO 30 second loading time with 5 layers, maybe we can use pooling for loading?
graphs_dict={}
for i in graphs:
    j=i.rstrip(".gpkg")
    j='_'.join(j.split('_')[:-1])
    graphs_dict[j] = read_graph(GRAPH_LOCATION+'\\'+i)

#load aircraft data
aircraft = json.load(open(AIRCRAFT_LOCATION))

""" BlueSky plugin template. The text you put here will be visible
    in BlueSky as the description of your plugin. """
from random import randint
import numpy as np
from bluesky.tools.aero import kts, ft
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf  #, settings, navdb, sim, scr

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

#TODO change to reroute overshoot
    @stack.command
    def rerouteovershoot(self, acid: 'acid'):
        ownship = traf
        ownship_route= traf.ap.route[acid]
        last_wpidx = np.argmax(ownship_route.wpname)

        initial_point = (ownship.lat[acid],ownship.lon[acid])
        final_point = (ownship_route.wplat[last_wpidx], ownship_route.wplon[last_wpidx])
        new_nodeids = shortest_path(graphs_dict['Resolution_Layer_0']['graph'],initial_point,final_point,True)

        new_fplat = graphs_dict['Resolution_Layer_0']['nodes'].set_index('osmid').loc[new_nodeids]['x'].to_numpy()
        new_fplon = graphs_dict['Resolution_Layer_0']['nodes'].set_index('osmid').loc[new_nodeids]['y'].to_numpy()
        new_fpalt = ownship.layerUpperAlt[np.where(ownship.layernames=='reso_0')[0][0]] / ft
        ownship_type = ownship.type[acid]
        try:
            new_fpgs = aircraft[ownship_type]['envelop']['v_max'] / kts #TODO make sure TUD updates with cruise speeds as per emmanuel request
        except:
            new_fpgs = 12.8611 / kts #if drone type is not found default to 25 kts


        stack.stack(f'DELRTE {ownship.id[acid]}')
        stack.stack(f'SPD {ownship.id[acid]} 0')
        stack.stack(f'{ownship.id[acid]} ATSPD 0 ALT {ownship.id[acid]} {new_fpalt}')
        for i in list(zip(new_fplat,new_fplon)):
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} ADDWPT {ownship.id[acid]} {i[1]} {i[0]} {new_fpalt} {new_fpgs}')
        stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} SPD {ownship.id[acid]} {new_fpgs}')
        stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} LNAV {ownship.id[acid]} ON')
        stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} VNAV {ownship.id[acid]} ON')
        return True, f'OVERSHOT - {traf.id[acid]} has a new route'

    @stack.command
    def reroutegeofence(self, acid: 'acid'):
        ownship = traf
        ownship_route= traf.ap.route[acid]
        last_wpidx = np.argmax(ownship_route.wpname)

        initial_point = (ownship.lat[acid],ownship.lon[acid])
        final_point = (ownship_route.wplat[last_wpidx], ownship_route.wplon[last_wpidx])
        nameCurrentLayer = ownship.aclayername[acid]
        currentLayernumber = re.findall('[0-9]+', nameCurrentLayer)[0]
        rerouteLayer = f'Resolution_Layer_{currentLayernumber}'

        new_nodeids = shortest_path(graphs_dict[rerouteLayer]['graph'],initial_point,final_point,True)

        new_fplat = graphs_dict[rerouteLayer]['nodes'].set_index('osmid').loc[new_nodeids]['x'].to_numpy()
        new_fplon = graphs_dict[rerouteLayer]['nodes'].set_index('osmid').loc[new_nodeids]['y'].to_numpy()
        new_fpalt = ownship.layerUpperAlt[np.where(ownship.layernames==f'resolution_{currentLayernumber}')[0][0]] / ft
        ownship_type = ownship.type[acid]
        try:
            new_fpgs = aircraft[ownship_type]['envelop']['v_max'] / kts #TODO make sure TUD updates with cruise speeds as per emmanuel request
        except:
            new_fpgs = 12.8611 / kts #if drone type is not found default to 25 kts

        #TODO figure out how to do turnspeeds.

        stack.stack(f'DELRTE {ownship.id[acid]}')
        stack.stack(f'SPD {ownship.id[acid]} 0')
        stack.stack(f'{ownship.id[acid]} ATSPD 0 ALT {ownship.id[acid]} {new_fpalt}')
        for i in list(zip(new_fplat,new_fplon)):
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} ADDWPT {ownship.id[acid]} {i[1]} {i[0]} {new_fpalt} {new_fpgs}')
        stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} SPD {ownship.id[acid]} {new_fpgs}')
        stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} LNAV {ownship.id[acid]} ON')
        stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} VNAV {ownship.id[acid]} ON')
        return True, f'GEOFENCE - {traf.id[acid]} has a new route'
