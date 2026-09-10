from langchain_core.tools import BaseTool


class ToolSelector:

    def select(
        self,
        task: str,
        tools: list[BaseTool],
    ) -> list[BaseTool]:

        task_lower = task.lower()

        selected = []

        for tool in tools:
            if tool.name == "search_code":
                if any(
                    keyword in task_lower
                    for keyword in [
                        "search",
                        "find",
                        "locate",
                        "code",
                        "repository",
                        "implementation",
                        "class",
                        "function",
                        "file",
                    ]
                ):
                    selected.append(tool)

            if tool.name == "read_file":
                if any(
                    keyword in task_lower
                    for keyword in [
                        "read",
                        "explain",
                        "where",
                        "implementation",
                        "class",
                        "function",
                        "file",
                    ]
                ):
                    selected.append(tool)

            if tool.name == "retrieve_evidence":
                if any(
                    keyword in task_lower
                    for keyword in [
                        "analyze",
                        "depend",
                        "dependency",
                        "explain",
                        "find",
                        "flow",
                        "implementation",
                        "locate",
                        "trace",
                        "where",
                    ]
                ):
                    selected.append(tool)

        return selected