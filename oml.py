import argparse
from functools import lru_cache
import os
import shutil
import subprocess


@lru_cache
def get_config_filename(suffix: str = "") -> str:
    return os.path.join(
        os.path.dirname(os.path.realpath(__file__)), f"config{suffix}.json"
    )


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
