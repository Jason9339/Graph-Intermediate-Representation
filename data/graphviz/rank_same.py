"""Nodes on same rank"""

import graphviz

def example_rank_same():
    d = graphviz.Digraph(format='png')

    with d.subgraph() as s:
        s.attr(rank='same')
        s.node('A')
        s.node('X')

    d.node('C')

    with d.subgraph() as s:
        s.attr(rank='same')
        s.node('B')
        s.node('D')
        s.node('Y')

    d.edges(['AB', 'AC', 'CD', 'XY'])
    return d

if __name__ == "__main__":
    g = example_rank_same()
    g.view()
