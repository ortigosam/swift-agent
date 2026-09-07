from infrastructure.ingestion.module.module_resolver import (
    ModuleResolver,
)


class NullModuleResolver(ModuleResolver):

    def resolve(
        self,
        source_path: str,
    ) -> str | None:

        return None
