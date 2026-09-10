from infrastructure.ingestion.module.module_resolver import (
    ModuleResolver,
)


class CompositeModuleResolver(ModuleResolver):

    def __init__(
        self,
        resolvers: list[ModuleResolver],
    ):
        self.resolvers = resolvers

    def resolve(
        self,
        source_path: str,
    ) -> str | None:

        for resolver in self.resolvers:
            module = resolver.resolve(source_path)

            if module is not None:
                return module

        return None
