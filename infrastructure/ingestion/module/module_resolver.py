from abc import ABC, abstractmethod


class ModuleResolver(ABC):

    @abstractmethod
    def resolve(self, source_path: str) -> str | None:
        pass