"""Record-based structures"""

import graphviz

def example_structs_revisited():
    s = graphviz.Digraph('structs', format='png',
                         node_attr={'shape': 'record'})

    s.node('struct1', '<f0> left|<f1> middle|<f2> right')
    s.node('struct2', '<f0> one|<f1> two')
    s.node('struct3', r'hello\nworld |{ b |{c|<here> d|e}| f}| g | h')

    s.edges([('struct1:f1', 'struct2:f0'), ('struct1:f2', 'struct3:here')])
    return s

if __name__ == "__main__":
    g = example_structs_revisited()
    g.view()
