from typing import Any

from copilot import define_tool
from langchain_core.tools import BaseTool
from pydantic import BaseModel, create_model


def to_copilot_tool(
    tool: BaseTool,
):
    args_schema = tool.args_schema

    if args_schema is None:
        raise ValueError(
            f"Tool '{tool.name}' must define an args_schema"
        )

    params_type = _create_params_type(
        tool=tool,
        args_schema=args_schema,
    )

    async def handler(
        params: BaseModel,
    ):
        arguments = params.model_dump()

        return tool.invoke(
            arguments
        )

    return define_tool(
        name=tool.name,
        description=tool.description,
        params_type=params_type,
        handler=handler,
        skip_permission=True,
        defer="never",
    )


def _create_params_type(
    tool: BaseTool,
    args_schema: Any,
) -> type[BaseModel]:

    fields = {}

    for name, field in args_schema.model_fields.items():
        fields[name] = (
            field.annotation,
            field,
        )

    return create_model(
        f"{tool.name.title()}Params",
        **fields,
    )