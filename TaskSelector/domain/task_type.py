from TaskSelector.domain.task_type_name import TaskTypeName
from dataclasses import dataclass

@dataclass(frozen=True)
class TaskType:
    name: TaskTypeName
    description: str