from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)


class MessageSelector:

    def select(
        self,
        messages: list[BaseMessage],
        token_budget: int,
    ) -> list[BaseMessage]:

        candidates = []

        for index, message in enumerate(messages):

            candidates.append(
                {
                    "index": index,
                    "message": message,
                    "tokens": self._estimate_tokens(message),
                    "priority": self._priority(message),
                }
            )

        candidates.sort(
            key=lambda item: (
                item["priority"],
                item["index"],
            ),
            reverse=True,
        )

        selected = []
        used_tokens = 0

        for candidate in candidates:

            if (
                used_tokens
                + candidate["tokens"]
                > token_budget
            ):
                continue

            selected.append(candidate)

            used_tokens += candidate["tokens"]

        selected.sort(
            key=lambda item: item["index"]
        )

        return [
            item["message"]
            for item in selected
        ]

    def _priority(
        self,
        message: BaseMessage,
    ) -> int:

        if isinstance(message, ToolMessage):
            return 3

        if isinstance(message, AIMessage):
            return 2

        if isinstance(message, HumanMessage):
            return 2

        return 1

    def _estimate_tokens(
        self,
        message: BaseMessage,
    ) -> int:

        content = str(message.content)

        return max(1, len(content) // 4)