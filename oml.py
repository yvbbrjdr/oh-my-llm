import argparse
import datetime
from functools import lru_cache
import json
import os
import shutil
import subprocess
import sys
from typing import Any

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam


@lru_cache
def get_config_filename(suffix: str = "") -> str:
    return os.path.join(
        os.path.dirname(os.path.realpath(__file__)), f"config{suffix}.json"
    )


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


def config_handler(args: argparse.Namespace):
    if not os.path.exists(get_config_filename()):
        shutil.copy2(get_config_filename("-example"), get_config_filename())
        os.chmod(get_config_filename(), 0o600)
    editor = os.getenv("EDITOR", "vi")
    subprocess.run([editor, get_config_filename()])
    print(f"Config is at {get_config_filename()}")
    print(f"Example config is at {get_config_filename('-example')}")


def execute_handler(args: argparse.Namespace):
    if not os.path.exists(get_config_filename()):
        print("Oh-my-llm is not configured. Please run 'oml config' to set it up.")
        return

    with open(get_config_filename(), "r") as f:
        config = json.load(f)

    with open(args.messages_file, "r") as f:
        messages = json.load(f)
    messages.append({"role": "user", "content": args.query})

    client = OpenAI(
        base_url=config["openai"]["api_base"],
        api_key=config["openai"]["api_key"],
    )

    try:
        response = client.chat.completions.create(
            model=config["openai"]["model"],
            messages=[system_message(), *messages],
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

            if config.get("debug"):
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
                        assistant_message["tool_calls"][index]["function"]["name"] += (
                            name
                        )
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
    execute_parser.set_defaults(func=execute_handler)

    args = parser.parse_args()
    args.func(args)
