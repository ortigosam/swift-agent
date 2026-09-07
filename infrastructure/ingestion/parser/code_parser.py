from abc import ABC, abstractmethod


class CodeParser(ABC):

    @abstractmethod
    def parse(self, source: str):
        pass