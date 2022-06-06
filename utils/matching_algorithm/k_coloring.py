class Graph:
    # Constructor
    def __init__(self, edges, nodes, n):
        self.adjList = [[] for _ in range(len(nodes))]
        self.nodes = nodes
        self.nodes_idx = {nodes[i]: i for i in range(len(self.nodes))}
        for (src, dest) in edges:
            self.adjList[self.nodes_idx[src]].append(self.nodes_idx[dest])
            self.adjList[self.nodes_idx[dest]].append(self.nodes_idx[src])
 
 
# Function to check if it is safe to assign color `c` to vertex `v`
def isSafe(graph, color, v, c):
    # check the color of every adjacent vertex of `v`
    for u in graph.adjList[graph.nodes_idx[v]]:
        if color[graph.nodes_idx[u]] == c:
            return False
    return True
 
 
def kColoring(g, color, k, v, n):
 
    # if all colors are assigned, return the solution
    if v == n:
        return [c for c in color]
 
    # try all possible combinations of available colors
    for c in range(1, k + 1):
        if isSafe(g, color, v, c):
            color[v] = c 
            kColoring(g, color, k, v + 1, n) 
            color[v] = 0
 