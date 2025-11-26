"""Edges between clusters"""

import graphviz

def example_cluster_edge():
    g = graphviz.Digraph('G', format='png')
    g.attr(compound='true')

    with g.subgraph(name='cluster0') as c:
        c.edges(['ab', 'ac', 'bd', 'cd'])

    with g.subgraph(name='cluster1') as c:
        c.edges(['eg', 'ef'])

    g.edge('b', 'f', lhead='cluster1')
    g.edge('d', 'e')
    g.edge('c', 'g', ltail='cluster0', lhead='cluster1')
    g.edge('c', 'e', ltail='cluster0')
    g.edge('d', 'h')
    return g

if __name__ == "__main__":
    g = example_cluster_edge()
    g.view()
