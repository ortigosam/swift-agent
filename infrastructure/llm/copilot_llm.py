import json
import os
from pathlib import Path

from copilot import CopilotClient
from copilot._mode import ToolSet
from copilot.session_events import SessionEventType


class CopilotLLM:

    def __init__(
        self,
        model: str = "gpt-5.4",
        tools: list | None = None,
    ):
        self.model = model
        self.tools = tools or []

        self.github_token = (
            os.environ.get("COPILOT_SDK_AUTH_TOKEN")
            or os.environ.get("GITHUB_TOKEN")
        )
        self.mode = (
            "empty"
            if self.github_token
            else "copilot-cli"
        )

        client_options = {
            "mode": self.mode,
            "working_directory": str(Path.cwd()),
            "github_token": self.github_token,
        }

        if self.mode == "empty":
            client_options["base_directory"] = str(
                Path.cwd() / ".copilot-sdk"
            )

        self.client = CopilotClient(
            **client_options,
        )
        self.session = None

        self.input_tokens = 0
        self.output_tokens = 0
        self.total_cost = 0.0

        self._tool_calls = {}
        self.invocations = []

    async def start(self):
        await self.client.start()

        available_tools = ToolSet()

        for tool in self.tools:
            available_tools.add_custom(tool.name)

        self.session = await self.client.create_session(
            model=self.model,
            tools=self.tools,
            available_tools=available_tools,
            working_directory=str(Path.cwd()),
            github_token=self.github_token,
            skip_custom_instructions=True,
            skip_embedding_retrieval=True,
            enable_on_demand_instruction_discovery=False,
            enable_session_store=False,
            enable_skills=False,
            enable_file_hooks=False,
            enable_host_git_operations=False,
            enable_session_telemetry=False,
        )
        print(
            "INITIAL USAGE copilot_llm: "
            f"{self.get_usage()}"
        )
        print(f"COPILOT SDK MODE: {self.mode}")


        self.session.on(self._handle_event)

    def _handle_event(self, event):

        if event.type == SessionEventType.ASSISTANT_USAGE:
            self._handle_usage(event.data)

        elif event.type == SessionEventType.ASSISTANT_TOOL_CALL_DELTA:
            self._handle_tool_call_delta(event.data)

        elif event.type == SessionEventType.TOOL_EXECUTION_COMPLETE:
            self._handle_tool_execution_complete(event.data)

    def _handle_usage(self, data):

        self.input_tokens += data.input_tokens or 0
        self.output_tokens += data.output_tokens or 0
        self.total_cost += data.cost or 0.0

        print("\n=== USAGE ===")
        print(f"Input tokens:  {data.input_tokens}")
        print(f"Output tokens: {data.output_tokens}")
        print(f"Cost:          {data.cost}")

    def _handle_tool_call_delta(self, data):

        tool_call = self._tool_calls.setdefault(
            data.tool_call_id,
            {
                "tool": data.tool_name,
                "arguments": "",
                "result": None,
            },
        )

        if data.tool_name:
            tool_call["tool"] = data.tool_name

        tool_call["arguments"] += data.input_delta

    def _handle_tool_execution_complete(self, data):

        tool_call = self._tool_calls.get(
            data.tool_call_id
        )

        if tool_call is None:
            return

        if data.result is not None:
            tool_call["result"] = data.result.content
        elif data.error is not None:
            tool_call["result"] = (
                f"Tool failed: {data.error.message}"
            )

    def reset_usage(self):

        self.input_tokens = 0
        self.output_tokens = 0
        self.total_cost = 0.0

        self._tool_calls.clear()
        self.invocations.clear()

    def get_usage(self):

        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": (
                self.input_tokens
                + self.output_tokens
            ),
            "cost": self.total_cost,
        }

    async def invoke(self, prompt: str):

        if self.session is None:
            raise RuntimeError(
                "CopilotLLM has not been started"
            )

        self._tool_calls.clear()

        usage_before = self.get_usage()

        response = await self.session.send_and_wait(
            prompt
        )

        tool_calls = list(
            self._tool_calls.values()
        )

        usage_after = self.get_usage()

        invocation = {
            "input": {
                "tokens": (
                    usage_after["input_tokens"]
                    - usage_before["input_tokens"]
                ),
                "text": prompt,
            },
            "output": {
                "tokens": (
                    usage_after["output_tokens"]
                    - usage_before["output_tokens"]
                ),
                "text": response.data.content,
            },
            "total_tokens": (
                usage_after["total_tokens"]
                - usage_before["total_tokens"]
            ),
            "cost": (
                usage_after["cost"]
                - usage_before["cost"]
            ),
            "tool_calls": tool_calls,
        }

        self.invocations.append(invocation)

        return {
            "content": response.data.content,
            "tool_calls": tool_calls,
        }

    def get_invocations(self):

        return list(self.invocations)

    async def stop(self):
        await self.client.stop()