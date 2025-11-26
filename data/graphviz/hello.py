"""Simple directed graph"""

import graphviz

def example_hello():
    g = graphviz.Digraph('G', format='png')
    g.edge('Hello', 'World')
    return g

if __name__ == "__main__":
    g = example_hello()
    g.view()
