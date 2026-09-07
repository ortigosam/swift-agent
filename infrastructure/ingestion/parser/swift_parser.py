from tree_sitter import Language, Parser
import tree_sitter_swift

from infrastructure.ingestion.parser.code_parser import CodeParser


class SwiftParser(CodeParser):

    def __init__(self):
        language = Language(tree_sitter_swift.language())
        self.parser = Parser(language)

    def parse(self, source: str):
        source_bytes = source.encode("utf-8")
        return self.parser.parse(source_bytes)