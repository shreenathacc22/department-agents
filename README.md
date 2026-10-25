# Department agents

One AI agent for each of three departments, HR, Finance and IT, with a router in front that sends each request
to the right one. Built on the Claude API with the official `anthropic` Python SDK. Every department has three
tools backed by synthetic company data, and every tool call is recorded so you can see what the agent did.

```
employee request -> router (structured output) -> HR | Finance | IT agent -> tools -> answer
```

| Department | Tools |
|---|---|
| HR | `get_leave_balance`, `request_leave`, `lookup_hr_policy` |
| Finance | `get_budget`, `submit_expense`, `expense_policy` |
| IT | `open_ticket`, `search_knowledge_base`, `check_system_status` |

## Run it

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
export ANTHROPIC_API_KEY=...        # or `ant auth login`; the key is never read by this code directly
.venv/bin/deptagents departments
.venv/bin/deptagents ask "I'm E-1001, how many annual leave days do I have left?"
.venv/bin/deptagents ask --department finance "claim 45 for a customer lunch, I'm E-1002"
.venv/bin/deptagents --show-tools chat
```

Settings, all optional: `DEPTAGENTS_MODEL` (default `claude-opus-5-5`), `DEPTAGENTS_EFFORT` (`low` to `max`,
default `medium`), `DEPTAGENTS_STATE` (a JSON file that keeps leave requests, expenses and tickets between runs;
unset means memory only), `DEPTAGENTS_DATA` (another data folder in the same shape as `data/`).

## How it works

- **Router** (`router.py`): one short call at low effort with a JSON schema output, so the answer is always a
  department key, a confidence and a reason. `none` means no department fits.
- **Agent** (`agent.py`): a hand-written tool-use loop. Claude gets the department's system prompt and strict tool
  schemas; the loop runs each tool, sends every result back in one message, and stops at `end_turn`. Refusals,
  truncated answers and runaway loops are reported, not hidden. The server-side refusal fallback is on by default
  so a policy decline is retried on a fallback model inside the same call; drop `fallbacks` in `agent.py` to turn it off.
- **Tools** (`tools.py`, `departments/`): JSON schema plus a handler. Handlers raise `ToolError` for anything the
  model should be told about, which goes back as an error result rather than crashing the conversation.
- **Store** (`store.py`): loads `data/*.json` and holds the records the agents create.

Thinking is always on with Claude Opus 5.5, so the code never sends a `thinking` parameter; effort is the dial.

## Tests

```bash
.venv/bin/python -m pytest -q
```

The tests use a fake client that replays scripted responses, so they run without a key and without network.
They cover every tool, the router's request shape, the loop (results fed back, parallel calls in one message,
errors with `is_error`, refusal, `max_tokens`, loop limit), per-department sessions, and the CLI.

## Data

Everything under `data/` is invented. Employees are ids and roles, never names. See `data/README.md`.
