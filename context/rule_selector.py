class RuleSelector:

    def select(self, task: str) -> list[str]:

        rules = [
            "Do not modify code unless explicitly requested.",
            "Use available tools instead of guessing.",
            "Base conclusions on repository evidence.",
        ]

        task_lower = task.lower()

        if any(
            keyword in task_lower
            for keyword in [
                "search",
                "find",
                "locate",
            ]
        ):
            rules.append(
                "Use search_code when inspecting source code."
            )

        if any(
            keyword in task_lower
            for keyword in [
                "architecture",
                "architect",
            ]
        ):
            rules.append(
                "Prefer existing architectural patterns "
                "over introducing new ones."
            )

        return rules