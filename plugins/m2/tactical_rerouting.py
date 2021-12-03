import json
import osmnx as ox
import geopandas as gp
from pyproj import CRS
import os
import rtree
import re

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

#TODO check if savegraph as graphML is quicker, you dont need to assigne specific nodes and edges
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

#105 second loading time with 3 graphs, maybe we can use pooling for loading?
graphs_dict={}
for i in graphs:
    j=i.rstrip(".gpkg")
    graphs_dict[j] = read_graph(GRAPH_LOCATION+'\\'+i)

#load aircraft data
aircraft = json.load(open(AIRCRAFT_LOCATION))

""" BlueSky plugin template. The text you put here will be visible
    in BlueSky as the description of your plugin. """
from random import randint
import numpy as np
from bluesky.tools.aero import kts, ft
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, tools #, settings, navdb, sim, scr
from shapely.geometry import Polygon, MultiPolygon, LineString,Point
import networkx as nx
import itertools

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

#TODO change to reroute overshoot
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

        new_fplat = graphs_dict['multi']['nodes'].set_index('osmid').loc[new_nodeids]['x'].to_numpy()
        new_fplon = graphs_dict['multi']['nodes'].set_index('osmid').loc[new_nodeids]['y'].to_numpy()
        new_fpalt = 0 # going standard to 0 because overshoot standards reroutes in layer 0
        ownship_type = ownship.type[acid]

        try:
            new_fpgs = aircraft[ownship_type]['envelop']['v_max'] / kts #TODO make sure TUD updates with cruise speeds as per emmanuel request
        except:
            new_fpgs = 12.8611 / kts #if drone type is not found default to 25 kts

        if ownship.alt[acid] /ft != new_fpalt:
            stack.stack(f'DELRTE {ownship.id[acid]}')
            stack.stack(f'SPD {ownship.id[acid]} 0')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 ALT {ownship.id[acid]} {new_fpalt}')
            for i in list(zip(new_fplat,new_fplon)):
                stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} ADDWPT {ownship.id[acid]} {i[1]} {i[0]} {new_fpalt} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} SPD {ownship.id[acid]} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} LNAV {ownship.id[acid]} ON')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} VNAV {ownship.id[acid]} ON')
        else:
            stack.stack(f'DELRTE {ownship.id[acid]}')
            stack.stack(f'SPD {ownship.id[acid]} 0')
            for i in list(zip(new_fplat,new_fplon)):
                stack.stack(f'{ownship.id[acid]} ATSPD 0 ADDWPT {ownship.id[acid]} {i[1]} {i[0]} {new_fpalt} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 SPD {ownship.id[acid]} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 LNAV {ownship.id[acid]} ON')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 VNAV {ownship.id[acid]} ON')

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
        #TODO: loop through the list of edges in the geofence and increase the lengths of these edges
        # calculate bearings then set as edge attributes

        geofences = tools.areafilter.basic_shapes
        # geo_save_dict =
        geofence_names = geofences.keys()
        temp_graph = graphs_dict[layerDirection]['graph'].copy()



        for j in geofence_names:
            # restructure the coordinates of the BS Poly shape to cast it into a shapely Polygon
            coord_list = list(zip(geofences[j].coordinates[1::2],geofences[j].coordinates[0::2]))

            values={}

            #construct shapely Polygon object and add it to the multipolygon list
            shapely_geofence = Polygon(coord_list)
            intersections = list(graphs_dict[layerDirection]['idx_tree'].intersection(shapely_geofence.bounds))
            list_intersecting_edges = [graphs_dict[layerDirection]['edges_rtree'][ii] for ii in intersections]
            for i in list_intersecting_edges:
                values[i] = {'pesoL': 9999}
            nx.set_edge_attributes(temp_graph, values)

        new_nodeids = shortest_path(temp_graph,initial_point,final_point,True)

        new_fplat = graphs_dict[layerDirection]['nodes'].set_index('osmid').loc[new_nodeids]['x'].to_numpy()
        new_fplon = graphs_dict[layerDirection]['nodes'].set_index('osmid').loc[new_nodeids]['y'].to_numpy()
        if ownship.alt[acid] == 0:
            new_fpalt = 0
        elif 'reso' in layerName[0]:
            new_fpalt = ownship.layerLowerAlt[idxCurrentLayer][0] / ft
        else:
            new_fpalt = ownship.layerLowerAlt[idxCurrentLayer+1][0] / ft

        ownship_type = ownship.type[acid]
        try:
            new_fpgs = aircraft[ownship_type]['envelop']['v_max'] / kts #TODO make sure TUD updates with cruise speeds as per emmanuel request
        except:
            new_fpgs = 12.8611 / kts #if drone type is not found default to 25 kts

        #TODO figure out how to do turnspeeds.
        if ownship.alt[acid] /ft != new_fpalt:
            stack.stack(f'DELRTE {ownship.id[acid]}')
            stack.stack(f'SPD {ownship.id[acid]} 0')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 ALT {ownship.id[acid]} {new_fpalt}')
            for i in list(zip(new_fplat,new_fplon)):
                stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} ADDWPT {ownship.id[acid]} {i[1]} {i[0]} {new_fpalt} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} SPD {ownship.id[acid]} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} LNAV {ownship.id[acid]} ON')
            stack.stack(f'{ownship.id[acid]} ATALT {new_fpalt} VNAV {ownship.id[acid]} ON')
        else:
            stack.stack(f'DELRTE {ownship.id[acid]}')
            stack.stack(f'SPD {ownship.id[acid]} 0')
            for i in list(zip(new_fplat,new_fplon)):
                stack.stack(f'{ownship.id[acid]} ATSPD 0 ADDWPT {ownship.id[acid]} {i[1]} {i[0]} {new_fpalt} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 SPD {ownship.id[acid]} {new_fpgs}')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 LNAV {ownship.id[acid]} ON')
            stack.stack(f'{ownship.id[acid]} ATSPD 0 VNAV {ownship.id[acid]} ON')

        self.reroutes[acid] = self.reroutes[acid] + 1
        traf.reroutes = self.reroutes

        return True, f'GEOFENCE - {traf.id[acid]} has a new route'
