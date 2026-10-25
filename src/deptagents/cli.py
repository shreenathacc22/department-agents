"""deptagents ask "..." [--department hr|finance|it]    one question
   deptagents chat                                      a conversation
   deptagents departments                               list departments and tools
Needs ANTHROPIC_API_KEY (or an `ant auth login` profile) to talk to Claude."""

import argparse
import sys

import anthropic

from deptagents import __version__, config
from deptagents.agent import Orchestrator, Result
from deptagents.departments import build_all
from deptagents.store import Store


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="deptagents", description="One AI agent per department, with a router in front.")
    p.add_argument("--version", action="version", version=f"deptagents {__version__}")
    p.add_argument("--model", help=f"Claude model id (default {config.DEFAULT_MODEL})")
    p.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], help="reasoning effort")
    p.add_argument("--show-tools", action="store_true", help="print every tool call the agent made")
    sub = p.add_subparsers(dest="cmd", required=True)
    ask = sub.add_parser("ask", help="ask one question")
    ask.add_argument("message")
    ask.add_argument("--department", choices=["hr", "finance", "it"], help="skip the router")
    chat = sub.add_parser("chat", help="talk to the agents in a loop; 'quit' to leave")
    chat.add_argument("--department", choices=["hr", "finance", "it"], help="stay in one department")
    sub.add_parser("departments", help="list departments and their tools")
    return p


def print_result(r: Result, show_tools: bool) -> None:
    label = r.department.upper() if r.department != "none" else "ROUTER"
    if r.route and r.department != "none":
        print(f"[{label}, routed at {r.route.confidence:.2f}: {r.route.reason}]")
    if show_tools:
        for c in r.tool_calls:
            flag = " (error)" if c.is_error else ""
            print(f"  tool {c.name}{flag} {c.arguments} -> {c.result[:160].replace(chr(10), ' ')}")
    print(r.answer)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "departments":
        for d in build_all(Store()).values():
            print(f"{d.key}: {d.description}")
            for t in d.tools:
                print(f"    {t.name}: {t.description}")
        return 0
    try:
        orch = Orchestrator(model=args.model, effort=args.effort)
        if args.cmd == "ask":
            print_result(orch.handle(args.message, args.department), args.show_tools)
            return 0
        print("deptagents chat. Type 'quit' to leave.")
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print(); return 0
            if line.lower() in ("quit", "exit"):
                return 0
            if line:
                print_result(orch.handle(line, args.department), args.show_tools)
    except anthropic.AuthenticationError:
        print("No valid Anthropic credentials. Set ANTHROPIC_API_KEY or run `ant auth login`.", file=sys.stderr)
        return 2
    except TypeError as e:
        # The SDK raises this at the first request when it finds no credentials at all.
        if "authentication" not in str(e).lower():
            raise
        print("No Anthropic credentials found. Set ANTHROPIC_API_KEY or run `ant auth login`.", file=sys.stderr)
        return 2
    except anthropic.RateLimitError:
        print("Rate limited by the API. Try again in a minute.", file=sys.stderr)
        return 3
    except anthropic.APIStatusError as e:
        print(f"API error {e.status_code}: {e.message}", file=sys.stderr)
        return 3
    except anthropic.APIConnectionError:
        print("Could not reach the Anthropic API. Check the network.", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
