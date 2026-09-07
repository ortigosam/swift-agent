from pathlib import Path
from typing import List, Optional

import yaml

from ..domain.task_type import TaskType
from ..domain.task_type_name import TaskTypeName


class TaskTypeRegistry:

    def __init__(self, path: str):
        self._task_types = self._load(path)

    def get_all(self) -> List[TaskType]:
        return list(self._task_types)

    def get(self, name: TaskTypeName) -> Optional[TaskType]:
        for task_type in self._task_types:
            if task_type.name == name:
                return task_type

        return None

    def _load(self, path: str) -> List[TaskType]:
        with Path(path).open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        task_types = []

        for item in data["task_types"]:
            name = TaskTypeName(item["name"])

            task_types.append(
                TaskType(
                    name=name,
                    description=item["description"],
                )
            )

        return task_types