import argparse


def execute_handler(args: argparse.Namespace):
    print(f"hello, {args.query}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Infuse your zsh with AI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    execute_parser = subparsers.add_parser("execute", help="Execute a command with AI")
    execute_parser.add_argument("query", help="The query to execute")
    execute_parser.add_argument(
        "messages", help="The current conversation messages in JSON format"
    )
    execute_parser.add_argument(
        "next_messages",
        help="The file path to write the next conversation messages in JSON format",
    )
    execute_parser.set_defaults(func=execute_handler)

    args = parser.parse_args()
    args.func(args)
