class SkillSelector:

    def select(self, task: str) -> list[str]:

        task_lower = task.lower()

        skills = []

        if any(
            keyword in task_lower
            for keyword in [
                "swift",
                "ios",
                "uikit",
                "swiftui",
            ]
        ):
            skills.append("ios_development")

        if any(
            keyword in task_lower
            for keyword in [
                "architecture",
                "architect",
                "mvvm",
                "clean architecture",
            ]
        ):
            skills.append("ios_architecture")

        if any(
            keyword in task_lower
            for keyword in [
                "test",
                "testing",
                "xctest",
            ]
        ):
            skills.append("ios_testing")

        return skills