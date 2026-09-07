from infrastructure.ingestion.parser.ast_walker import ASTWalker

class ASTInspector:

    def __init__(self):
        self.walker = ASTWalker()

    def print_tree(self, tree):

        for node, depth in self.walker.walk(
            tree.root_node
        ):

            indent = "  " * depth

            print(
                f"{indent}{node.type}"
            )