"""Color specifications"""

import graphviz

def example_colors():
    g = graphviz.Graph(format='png')

    g.node('RGB: #40e0d0', style='filled', fillcolor='#40e0d0')
    g.node('RGBA: #ff000042', style='filled', fillcolor='#ff000042')
    g.node('HSV: 0.051 0.718 0.627', style='filled', fillcolor='0.051 0.718 0.627')
    g.node('name: deeppink', style='filled', fillcolor='deeppink')
    return g

if __name__ == "__main__":
    g = example_colors()
    g.view()
