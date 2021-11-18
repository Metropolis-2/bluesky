import config
import geopandas as gp
import json
import math
import networkx as nx
import os
import osmnx as ox
import warnings
from pyproj import CRS
from shapely.geometry import LineString, Point
from shapely.geometry.polygon import Polygon

'''ENVIRONMENT VARIABLES'''
# Total Airspace Unc GPKG
GPKG_PATH = config.GPKG_PATH
# Flight Planes TXT
FP_PATH = config.FP_PATH
# Aircraft Json
AIRCRAFT_PATH = config.AIRCRAFT_PATH
# Drone Features
VELOCITY_INDEX = config.VELOCITY_INDEX
DEPARTURE_INDEX = config.DEPARTURE_INDEX
INITIAL_LOCATION_INDEX = config.INITIAL_LOCATION_INDEX
FINAL_LOCATION_INDEX = config.FINAL_LOCATION_INDEX
STATUS_INDEX = config.STATUS_INDEX
# Drone Status
PENDING_STATUS = config.PENDING_STATUS
APPROVED_STATUS = config.APPROVED_STATUS
# Maximum pesoL Value
MAX_PESOL = config.MAX_PESOL
# Graph Plot
LAT = config.LAT
LON = config.LON
DIST = config.DIST

'''CONSTANTS'''
# Timestamp Conversion
MINUTS_CONVERSION = config.MINUTS_CONVERSION
SECONDS_CONVERSION = config.SECONDS_CONVERSION

'''FUNCTIONS'''
def edge_gdf_format_from_gpkg(edges):
    edge_dict = edges.to_dict()
    edge_gdf = gp.GeoDataFrame(edge_dict, crs = CRS.from_user_input(4326))
    edge_gdf.set_index(['u', 'v', 'key'], inplace = True)
    
    return edge_gdf

def node_gdf_format_from_gpkg(nodes):
    node_dict = nodes.to_dict()
    node_gdf = gp.GeoDataFrame(node_dict, crs = CRS.from_user_input(4326))
    node_gdf.set_index(['osmid'], inplace = True)
    
    return node_gdf

def get_sec(time_str):# Convert hh:mm:ss forat to tiemstamp seconds
    h, m, s = time_str.split(':')
    
    return int(h) * MINUTS_CONVERSION + int(m) * SECONDS_CONVERSION + int(s)

def shortest_path(G, origin, destination):# Calculate the nodes route from an origin (lat, lon) to a destinetion (lat, lon)
    origin_node, d1 = ox.nearest_nodes(G, origin[1], origin[0], return_dist = True)# (lon, lat)
    dest_node, d2 = ox.nearest_nodes(G, destination[1], destination[0], return_dist = True)# (lon, lat)
    osmid_route = ox.shortest_path(G, origin_node, dest_node, weight = 'pesoL')
    
    return osmid_route

def nodeIsFree(osmid_node, timestamp):# Check if node is free or taked in the timestamp instant
    time_list = nodes.loc[osmid_node].Ocupation.strip('[]').split(',')
    print('Node', osmid_node, ';', 'Ocuppation Time', time_list, ';', 'Timestamp', timestamp)
    if(time_list == ['None']):# Free Node
        return True
    else:
        time_list = [int(x) for x in time_list]
        if(timestamp in time_list):# Unavailable Node
            return False
        return True# Free Node

def edgeIsFree(osmid_nodeA, osmid_nodeB, timestamp_tuple):# Check if the links between two nodes are free in the slot time
    if(osmid_nodeA == osmid_nodeB):# No edge exist between same nodes
        return True
    else:
        slot_time_list = edges.loc[osmid_nodeA, osmid_nodeB, 0].Ocupation
        print('Edge Ocuppation Slot Time', slot_time_list, ';', 'Slot Timestamp', timestamp_tuple, '\n')
        if(slot_time_list == '[None]'):# Free Edge
            return True
        else:
            for slot_time in eval(slot_time_list):
                if(eval(slot_time) == timestamp_tuple):# Unavailable Edge
                    return False
            else:
                return True# Free Edge

def travel_time(nodeA, nodeB, speed, timestamp_nodeA, edges):
    if(nodeA == nodeB):
        return 0
    else:
        length = edges.loc[(nodeA, nodeB, 0), 'length']
        slot_time = math.ceil(length / speed)# Ceil: Round up
        
        return slot_time + timestamp_nodeA

def get_paths(fp_plans, G, nodes, edges):
    paths = []
    for i, fp in enumerate(fp_plans):
        if(i == 0):
            path = fp_evaluations(fp, G, nodes, edges)
        else:
            while True:
                path = fp_evaluations(fp, path[1], nodes, edges)
                if not(path[0] == 0):
                    break
        paths.append(path[0])
        
    return paths

def fp_evaluations(fp, G, nodes, edges):
    if(fp[STATUS_INDEX] == PENDING_STATUS):
        nodes_route = shortest_path(G, 
                                    tuple(float(s) for s in fp[INITIAL_LOCATION_INDEX].strip('()').split(',')), 
                                    tuple(float(s) for s in fp[FINAL_LOCATION_INDEX].strip('()').split(',')))
        departure_time = get_sec(str(fp[DEPARTURE_INDEX]))
        speed = json.load(open(AIRCRAFT_PATH))[str(fp[VELOCITY_INDEX])]['envelop']['v_max']
        
        print('Generated Path', nodes_route, '\n')
        
        if(len(nodes_route) > 0):
            nodeA = nodes_route[0]
            time, timestamp_nodeA = 0, 0
            nodes_time = {}
            edges_slotTime = {}
            for node_id in nodes_route:
                nodeB = node_id
                time = travel_time(nodeA, nodeB, speed, departure_time + timestamp_nodeA, edges)
                timestamp_nodeB = time
                
                if(nodeIsFree(node_id, time)):# Free Node
                    edge_slot_time = (timestamp_nodeA, timestamp_nodeB)
                    
                    if(edgeIsFree(nodeA, nodeB, edge_slot_time)):# Free Edge
                        
                        if(nodeA != nodeB):
                            nodes_time[node_id] = time
                            edges_slotTime[(nodeA, nodeB, 0)] = str(edge_slot_time)
                            
                    else:# Unavailable Edge
                        print('Unavailable Edge')
                        edges.loc[(nodeA, nodeB, 0), 'pesoL'] = MAX_PESOL# Update 'pesoL' field
                        G = ox.graph_from_gdfs(nodes, edges)
                        return 0, G
                    
                else:# Unavailable Node
                    print('Unavailable Node')
                    edges.loc[(nodeA, nodeB, 0), 'pesoL'] = MAX_PESOL# Update 'pesoL' field
                    G = ox.graph_from_gdfs(nodes, edges)
                    return 0, G
                
                nodeA = nodeB
                timestamp_nodeA = timestamp_nodeB
                
        else:
            print('No Possible Paths')
            
        for k, v in nodes_time.items():
            if(nodes.loc[k, 'Ocupation'] == '[None]'):
                nodes.loc[k, 'Ocupation'] = str([v])# Insert node ocupation field
            else:
                aux_lix = nodes.loc[k, 'Ocupation'].strip("[]").split(',')
                aux_list = list(map(int, aux_lix))
                aux_list.append(v)
                nodes.loc[k, 'Ocupation'] = str(aux_list)# Update node ocupation field
                
        for k, v in edges_slotTime.items():
            # edges.loc[k, 'Ocupation'] = str([v])
            if(edges.loc[k, 'Ocupation'] == '[None]'):
                edges.loc[k, 'Ocupation'] = str([v])# Insert edge ocupation field
            else:
                aux_list = edges.loc[k, 'Ocupation']
                aux_list = list(eval(aux_list))
                aux_list.append(v)
                edges.loc[k, 'Ocupation'] = str(aux_list)# Update edge ocupation field
                
        G = ox.graph_from_gdfs(nodes, edges)
        fp[STATUS_INDEX] = APPROVED_STATUS
        
    return (nodes_route, G)

'''MAIN'''
warnings.filterwarnings('ignore')

# Load Graph Data
nodes = gp.read_file(GPKG_PATH, layer = 'nodes')
edges = gp.read_file(GPKG_PATH, layer = 'edges')
nodmod = node_gdf_format_from_gpkg(nodes)
edmod = edge_gdf_format_from_gpkg(edges)

G = ox.graph_from_gdfs(nodmod, edmod)
nodes, edges = ox.graph_to_gdfs(G)

# Load Flight Planes File
fp_plans = []
file = open(FP_PATH)
line = file.readline()
while line:
    fp_plans.append(line.rstrip().split('\t'))
    line = file.readline()
file.close()

# Load Aircraft File
aircraft = open(AIRCRAFT_PATH)

# Run FP Evaluations and Get Paths
paths = get_paths(fp_plans, G, nodes, edges)

'''NODES & EDGES GRAPH PLOT'''
ox.graph_to_gdfs(G, edges = False).unary_union.centroid
bbox = ox.utils_geo.bbox_from_point((LAT, LON), dist = DIST)
fig, ax = ox.plot_graph_routes(G, paths, ax = None, bbox = bbox)
# fig, ax = ox.plot_graph_routes(G, paths, ['y', 'r'], ax = None, bbox = bbox)# Add different colors for each path (y: yellow, r: red, ...)