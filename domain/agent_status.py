from enum import Enum


class AgentStatus(Enum):
    START = "START"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"