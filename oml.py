import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from functools import lru_cache
from typing import IO, Any, cast

import json_repair
from exa_py import Exa
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam


def config_from_dict(cls: Any, data: dict[str, Any]) -> Any:
    kwargs = {}
    for f in fields(cls):
        if f.name in data:
            value = data[f.name]
            if is_dataclass(f.type) and isinstance(value, dict):
                kwargs[f.name] = config_from_dict(f.type, cast(dict[str, Any], value))
            else:
                kwargs[f.name] = value
    return cls(**kwargs)


@dataclass(kw_only=True)
class OmlOpenAIConfig:
    api_key: str = "your-openai-api-key"
    api_base: str = "https://api.openai.com/v1"
    model: str = "gpt-5.4"
    small_model: str = "gpt-5.4-mini"


@dataclass(kw_only=True)
class OmlExaConfig:
    api_key: str = "your-exa-api-key"


@dataclass(kw_only=True)
class OmlConfig:
    debug: bool = False
    execute_failed_command: bool = True
    skip_readonly_command_verification: bool = False
    openai: OmlOpenAIConfig = field(default_factory=OmlOpenAIConfig)
    exa: OmlExaConfig = field(default_factory=OmlExaConfig)

    @staticmethod
    @lru_cache(maxsize=1)
    def get_config_filename() -> str:
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json")

    @staticmethod
    def load() -> "OmlConfig":
        try:
            with open(OmlConfig.get_config_filename(), "r") as f:
                data: Any = json_repair.load(f)
            return config_from_dict(OmlConfig, data)
        except:
            return OmlConfig()

    def save(self):
        with open(self.get_config_filename(), "w") as f:
            json.dump(asdict(self), f, indent=4)


def is_shell_command(message: str, client: OpenAI, model: str) -> bool:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that determines whether a string is a shell command or not, like a request or a sentence. The user input given to you is a string that has failed to execute as a shell command. Your task is to determine whether the user input is intended to be a shell command or not. Return true if it is a shell command, false otherwise.",
                },
                {
                    "role": "user",
                    "content": message,
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "is_command_response",
                    "description": "Determines whether the input is a shell command. Return true if it is a command, false otherwise.",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "is_command": {
                                "type": "boolean",
                                "description": "Whether the input is a shell command. Return true if it is a command, false otherwise.",
                            }
                        },
                        "required": ["is_command"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
        )
        assert isinstance(response.choices[0].message.content, str)
        result: Any = json_repair.loads(response.choices[0].message.content)
        return result.get("is_command", False)
    except Exception as e:
        print(f"Error determining if message is shell command: {e}", file=sys.stderr)
        return False


def is_shell_command_readonly(message: str, client: OpenAI, model: str) -> bool:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that determines whether a shell command is readonly or it modifies the system or has side effects.",
                },
                {
                    "role": "user",
                    "content": message,
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "is_command_readonly_response",
                    "description": "Determines whether the input is a readonly shell command. Return true if it is a readonly command, false otherwise.",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "is_command_readonly": {
                                "type": "boolean",
                                "description": "Whether the input is a readonly shell command. Return true if it is a readonly command, false otherwise.",
                            }
                        },
                        "required": ["is_command_readonly"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
        )
        assert isinstance(response.choices[0].message.content, str)
        result: Any = json_repair.loads(response.choices[0].message.content)
        return result.get("is_command_readonly", False)
    except Exception as e:
        print(
            f"Error determining if message is readonly shell command: {e}",
            file=sys.stderr,
        )
        return False


def getcwd():
    while True:
        try:
            return os.getcwd().replace(os.path.expanduser("~"), "~")
        except FileNotFoundError:
            os.chdir("..")


def system_message() -> ChatCompletionMessageParam:
    return {
        "role": "system",
        "content": f"You are oh-my-llm, an AI-infused zsh environment. Today's date is {datetime.datetime.now().strftime('%Y-%m-%d')}. Current working directory is {getcwd()}. The operating system is {str(os.uname())}.",
    }


class Tool:
    def __init__(self, description: str, parameters: dict[str, Any]):
        self.description = description
        self.parameters = parameters

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Tool execution not implemented")


class ShellTool(Tool):
    def __init__(
        self, client: OpenAI, model: str, skip_readonly_command_verification: bool
    ):
        super().__init__(
            "Execute a shell command on the host and return its stdout and stderr. If you need to execute Python code for some task, use this tool.",
            {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        )
        self._client = client
        self._model = model
        self._skip_readonly_command_verification = skip_readonly_command_verification

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        command = args["command"]
        if not (
            self._skip_readonly_command_verification
            and is_shell_command_readonly(command, self._client, self._model)
        ):
            try:
                user_input = input(f"Allow execution of command: {command}? [Y/n] ")
            except EOFError:
                print()
                user_input = "n"
            except KeyboardInterrupt:
                print()
                user_input = "n"
            if user_input.strip().lower() not in ("y", "yes", ""):
                return {"error": "Command execution cancelled by user."}
        else:
            print(f"\033[90mExecuting command: {command}\033[0m")

        p = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        def forward_output(pipe: IO[bytes], log: list[str], is_stderr: bool = False):
            for line in iter(pipe.readline, b""):
                decoded = line.decode()
                print(
                    f"\033[90m{decoded}\033[0m",
                    end="",
                    flush=True,
                    file=sys.stderr if is_stderr else sys.stdout,
                )
                log.append(decoded)
            pipe.close()

        stdout: list[str] = []
        stderr: list[str] = []
        stdout_thread = threading.Thread(target=forward_output, args=(p.stdout, stdout))
        stderr_thread = threading.Thread(
            target=forward_output, args=(p.stderr, stderr, True)
        )
        stdout_thread.start()
        stderr_thread.start()

        while True:
            try:
                p.wait()
                break
            except KeyboardInterrupt:
                p.send_signal(signal.SIGINT)
                print()
        stdout_thread.join()
        stderr_thread.join()
        outputs: dict[str, Any] = {
            "returncode": p.returncode,
            "stdout": "".join(stdout),
            "stderr": "".join(stderr),
        }
        return outputs


class SearchTool(Tool):
    def __init__(self, api_key: str):
        super().__init__(
            "Search the web and return relevant results with titles, URLs, and content snippets.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        )
        self._client = Exa(api_key)

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args["query"]
        print(f"\033[90mSearching for: {query}\033[0m")
        return {
            "results": [
                asdict(result)
                for result in self._client.search(
                    query, contents={"highlights": True}
                ).results
            ]
        }


class FetchTool(Tool):
    def __init__(self, api_key: str):
        super().__init__(
            "Fetch the content of a web page given its URL. Use this tool when you need to access information from a specific web page.",
            {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the web page to fetch.",
                    }
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        )
        self._client = Exa(api_key)

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        url = args["url"]
        print(f"\033[90mFetching URL: {url}\033[0m")
        return asdict(self._client.get_contents(url, text=True).results[0])


def config_handler(args: argparse.Namespace):
    OmlConfig.load().save()
    editor = os.getenv("EDITOR", "vi")
    subprocess.run([editor, OmlConfig.get_config_filename()])
    OmlConfig.load().save()


def execute_handler(args: argparse.Namespace):
    if not os.path.exists(OmlConfig.get_config_filename()):
        print("Oh-my-llm is not configured. Please run 'oml config' to set it up.")
        return

    config = OmlConfig.load()

    client = OpenAI(
        base_url=config.openai.api_base,
        api_key=config.openai.api_key,
    )

    if args.failed_command and (
        not config.execute_failed_command
        or is_shell_command(args.query, client, config.openai.small_model)
    ):
        return

    with open(args.messages_file, "r") as f:
        messages = json.load(f)
    messages.append({"role": "user", "content": args.query})

    tools: dict[str, Tool] = {
        "shell": ShellTool(
            client, config.openai.small_model, config.skip_readonly_command_verification
        ),
        **(
            {
                "search": SearchTool(config.exa.api_key),
                "fetch": FetchTool(config.exa.api_key),
            }
            if config.exa.api_key != OmlExaConfig().api_key
            else {}
        ),
    }

    while True:
        try:
            response = client.chat.completions.create(
                model=config.openai.model,
                messages=[system_message(), *messages],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": tool.description,
                            "parameters": tool.parameters,
                        },
                    }
                    for name, tool in tools.items()
                ],
                stream=True,
            )
        except Exception as e:
            print(f"oml: error: {e}", file=sys.stderr)
            return

        assistant_message: dict[str, Any] = {"role": "assistant", "content": ""}
        messages.append(assistant_message)
        reasoning_mode = False
        has_output = False
        try:
            for chunk in response:
                delta = chunk.choices[0].delta

                if config.debug:
                    print(f"\n[DEBUG] Delta: {delta}\n")

                tool_calls = delta.tool_calls
                if tool_calls:
                    assistant_tool_calls: list[Any] = assistant_message.get(
                        "tool_calls", []
                    )
                    assistant_message["tool_calls"] = assistant_tool_calls
                    for tool_call in tool_calls:
                        index = tool_call.index
                        id = tool_call.id
                        function = tool_call.function
                        assert function is not None
                        name = function.name
                        arguments = function.arguments
                        type = tool_call.type
                        while len(assistant_message["tool_calls"]) <= index:
                            assistant_message["tool_calls"].append(
                                {
                                    "type": "",
                                    "id": "",
                                    "function": {
                                        "name": "",
                                        "arguments": "",
                                    },
                                }
                            )
                        if id:
                            assistant_message["tool_calls"][index]["id"] += id
                        if name:
                            assistant_message["tool_calls"][index]["function"][
                                "name"
                            ] += name
                        if arguments:
                            assistant_message["tool_calls"][index]["function"][
                                "arguments"
                            ] += arguments
                        if type:
                            assistant_message["tool_calls"][index]["type"] = type

                reasoning_content = getattr(delta, "reasoning", None) or getattr(
                    delta, "reasoning_content", None
                )
                if reasoning_content:
                    if not reasoning_mode:
                        reasoning_mode = True
                    print(f"\033[90m{reasoning_content}\033[0m", end="", flush=True)
                    has_output = True
                    if hasattr(delta, "reasoning_content") and isinstance(
                        getattr(delta, "reasoning_content"), str
                    ):
                        assistant_reasoning_content: str = assistant_message.get(
                            "reasoning_content", ""
                        )
                        assistant_message["reasoning_content"] = (
                            assistant_reasoning_content
                            + getattr(delta, "reasoning_content")
                        )

                content = delta.content
                if content:
                    if reasoning_mode:
                        reasoning_mode = False
                        print()
                    print(content, end="", flush=True)
                    has_output = True
                    assistant_message["content"] += content
        except KeyboardInterrupt:
            print()
            return
        except Exception as e:
            print(f"\noml: error during response: {e}", file=sys.stderr)
            return
        if has_output:
            print()

        if assistant_message.get("tool_calls"):
            for tool_call in assistant_message["tool_calls"]:
                name = tool_call["function"]["name"]
                arguments: Any = json_repair.loads(tool_call["function"]["arguments"])
                id = tool_call["id"]
                tool = tools.get(name)
                if not tool:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": id,
                            "content": f"Error: Tool '{name}' not found.",
                        }
                    )
                    continue
                try:
                    result = tool.execute(arguments)
                except Exception as e:
                    result = {"error": str(e)}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": id,
                        "content": json.dumps(result),
                    }
                )
            continue

        break

    with open(args.messages_file, "w") as f:
        json.dump(messages, f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Infuse your zsh with AI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="Configure oh-my-llm")
    config_parser.set_defaults(func=config_handler)

    execute_parser = subparsers.add_parser("execute", help="Execute a command with AI")
    execute_parser.add_argument("query", help="The query to execute")
    execute_parser.add_argument(
        "messages_file",
        help="The file path containing the current conversation messages in JSON format",
    )
    execute_parser.add_argument(
        "--failed-command",
        action="store_true",
        help="Execute the failed command with AI",
    )
    execute_parser.set_defaults(func=execute_handler)

    args = parser.parse_args()
    args.func(args)
