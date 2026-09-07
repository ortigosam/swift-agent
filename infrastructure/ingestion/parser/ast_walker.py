class ASTWalker:

    def walk(self, node, depth: int = 0):

        yield node, depth

        for child in node.children:
            yield from self.walk(
                child,
                depth + 1,
            )