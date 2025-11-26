"""Gradient colors"""

import graphviz

def example_g_c_n():
    g = graphviz.Graph('G', format='png')
    g.attr(bgcolor='purple:pink', label='agraph', fontcolor='white')

    with g.subgraph(name='cluster1') as c:
        c.attr(fillcolor='blue:cyan', label='acluster', fontcolor='white',
               style='filled', gradientangle='270')
        c.attr('node', shape='box', fillcolor='red:yellow',
               style='filled', gradientangle='90')
        c.node('anode')
    return g

if __name__ == "__main__":
    g = example_g_c_n()
    g.view()
