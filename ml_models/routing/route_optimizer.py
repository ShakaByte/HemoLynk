"""
route_optimizer.py

Builds a graph of all facilities using haversine distances as edge weights,
then runs Dijkstra's algorithm to find the shortest path between any two
facilities. Used by the redistribution engine to find optimal transport routes.

In real app: edge weights will be replaced by actual road distances from
Google Maps API. For now, straight-line (haversine) distance is used.
"""

import math
import heapq
import pandas as pd


# Max distance (km) to consider two facilities as connected neighbours
# Facilities beyond this are not directly connected in the graph
MAX_EDGE_KM = 150


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi       = math.radians(lat2 - lat1)
    dlambda    = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_graph(facilities_df):
    """
    Builds an adjacency list graph where:
      - Each node is a facility_id
      - Each edge weight is haversine distance in km
      - Only facilities within MAX_EDGE_KM of each other are connected

    Returns: dict {facility_id: [(neighbour_id, distance_km), ...]}
    """
    graph = {row['facility_id']: [] for _, row in facilities_df.iterrows()}

    fac_list = facilities_df.to_dict('records')

    for i, fac_a in enumerate(fac_list):
        for j, fac_b in enumerate(fac_list):
            if i >= j:
                continue  # avoid duplicate edges

            dist = haversine_km(
                fac_a['latitude'], fac_a['longitude'],
                fac_b['latitude'], fac_b['longitude']
            )

            if dist <= MAX_EDGE_KM:
                graph[fac_a['facility_id']].append((fac_b['facility_id'], dist))
                graph[fac_b['facility_id']].append((fac_a['facility_id'], dist))

    return graph


def dijkstra(graph, source):
    """
    Standard Dijkstra's algorithm.
    Returns:
        dist : dict {facility_id: shortest_distance_from_source}
        prev : dict {facility_id: previous_node_in_shortest_path}
    """
    dist = {node: float('inf') for node in graph}
    prev = {node: None for node in graph}
    dist[source] = 0

    # Priority queue: (distance, facility_id)
    pq = [(0, source)]

    while pq:
        current_dist, current_node = heapq.heappop(pq)

        # Skip if we already found a shorter path
        if current_dist > dist[current_node]:
            continue

        for neighbour, weight in graph[current_node]:
            new_dist = current_dist + weight
            if new_dist < dist[neighbour]:
                dist[neighbour] = new_dist
                prev[neighbour] = current_node
                heapq.heappush(pq, (new_dist, neighbour))

    return dist, prev


def shortest_path(graph, source, target):
    """
    Returns the shortest path and total distance from source to target.

    Returns:
        path       : list of facility_ids from source to target
        total_dist : float, total km
    """
    dist, prev = dijkstra(graph, source)

    if dist[target] == float('inf'):
        return None, float('inf')  # no path exists

    # Reconstruct path by walking back through prev
    path = []
    node = target
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()

    return path, round(dist[target], 2)


def get_route_plan(facilities_df, source_id, target_id):
    """
    Full route plan between two facilities.
    Returns a dict with path, distance, and facility names.
    """
    graph = build_graph(facilities_df)
    path, total_dist = shortest_path(graph, source_id, target_id)

    if path is None:
        return {
            "source"     : source_id,
            "target"     : target_id,
            "path"       : None,
            "total_km"   : None,
            "reachable"  : False,
            "message"    : f"No route found between {source_id} and {target_id} within graph"
        }

    # Attach facility names to path
    fac_names = facilities_df.set_index('facility_id')['name'].to_dict()
    named_path = [f"{fid} ({fac_names.get(fid, '?')})" for fid in path]

    return{
        "source"      : source_id,
        "target"      : target_id,
        "path"        : path,
        "named_path"  : named_path,
        "total_km"    : total_dist,
        "hops"        : len(path) - 1,
        "reachable"   : True,
        "feasible_for": {comp: is_transport_feasible(comp, total_dist)for comp in ["Platelets","Whole Blood","RBC","Plasma"]},
        "message"     : f"Route found: {' → '.join(named_path)} ({total_dist} km)"
    }

# Max transport distance per component (realistic shelf-life based)
MAX_TRANSPORT_KM = {
    "Platelets"  : 50,
    "Whole Blood": 150,
    "RBC"        : 150,
    "Plasma"     : 300,
}

def is_transport_feasible(component, total_km):
    """
    Returns True if the route distance is within safe transport
    range for the given component.
    """
    limit = MAX_TRANSPORT_KM.get(component, 150)
    return total_km <= limit

if __name__ == "__main__":
    facilities_df = pd.read_csv("../../data/facilities.csv")

    graph = build_graph(facilities_df)

    total_edges = sum(len(v) for v in graph.values()) // 2
    print(f"Graph built: {len(graph)} nodes, {total_edges} edges\n")

    # Test 1: same district
    r1 = get_route_plan(facilities_df, "FAC001", "FAC009")
    print("=== TEST 1: Same district ===")
    print(r1['message'])
    print(f"Hops: {r1['hops']} | Feasible for: {r1['feasible_for']}\n")

    # Test 2: cross district
    r2 = get_route_plan(facilities_df, "FAC001", "FAC046")
    print("=== TEST 2: Cross district ===")
    print(r2['message'])
    print(f"Hops: {r2['hops']} | Feasible for: {r2['feasible_for']}\n")

    # Test 3: Raichur reachability
    r3 = get_route_plan(facilities_df, "FAC001", "FAC028")
    print("=== TEST 3: FAC001 → Raichur ===")
    print(r3['message'])
    print(f"Hops: {r3['hops']} | Feasible for: {r3['feasible_for']}\n")

    # Test 4: all facilities reachable?
    dist, _ = dijkstra(graph, "FAC001")
    unreachable = [fid for fid, d in dist.items() if d == float('inf')]
    print(f"=== TEST 4: Reachability from FAC001 ===")
    print(f"Unreachable facilities: {len(unreachable)}")
    if unreachable:
        print("Unreachable:", unreachable)
    else:
        print("All 54 facilities reachable ✅")