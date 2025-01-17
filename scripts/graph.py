import os
import ast
import networkx as nx


def find_imports(filepath):
    with open(filepath, "r") as f:
        tree = ast.parse(f.read(), filename=filepath)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = node.module if hasattr(node, "module") else node.names[0].name
            imports.append(module)
    return imports


def build_graph(root_path):
    graph = nx.DiGraph()
    for dirpath, _, filenames in os.walk(root_path):
        for file in filenames:
            if file.endswith(".py"):
                filepath = os.path.join(dirpath, file)
                imports = find_imports(filepath)
                node = os.path.relpath(filepath, root_path)
                for imp in imports:
                    if imp is None:
                        continue
                    graph.add_edge(node, imp)
    return graph


root = "."
G = build_graph(root)
nx.draw(G, with_labels=True, node_color="lightblue", edge_color="gray")
