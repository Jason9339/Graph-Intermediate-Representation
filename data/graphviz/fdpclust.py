"""FDP cluster layout"""

import graphviz

def example_fdpclust():
    g = graphviz.Graph('G', engine='fdp', format='png')

    g.node('e')

    with g.subgraph(name='clusterA') as a:
        a.edge('a', 'b')
        with a.subgraph(name='clusterC') as c:
            c.edge('C', 'D')

    with g.subgraph(name='clusterB') as b:
        b.edge('d', 'f')

    g.edge('d', 'D')
    g.edge('e', 'clusterB')
    g.edge('clusterC', 'clusterB')
    return g

if __name__ == "__main__":
    g = example_fdpclust()
    g.view()
