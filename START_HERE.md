# Token Budget — Getting Started

## What this is

Two scripts that track your Claude.ai monthly credit spend and display a live
progress bar in the Claude Code status line:

- **`get_token_budget.py`** — fetches current spend from the Claude.ai API and
  writes it to a local cache (uses your Chrome session cookies, no browser launch)
- **`token_status.py`** — reads the cache and renders the status bar; never hits
  the network

## 1. Prerequisites

- Python ≥3.12 and Poetry installed
- Google Chrome installed and logged in to claude.ai

## 2. Install dependencies

```bash
cd ~/.claude/token_budget
poetry install
```

## 3. Configure settings

Ask Claude to set up your `settings.toml`:

> Read `token_budget/START_HERE.md` and `token_budget/example_settings.toml`,
> then help me create my `settings.toml` by asking me about each setting one at a time.

Claude will read `example_settings.toml` (which documents every setting with its default and
purpose) and walk you through each one interactively before writing the file.

## 4. Run the scraper (populates the cache)

```bash
cd ~/.claude/token_budget && poetry run python get_token_budget.py
```

## 5. Set up the status bar and auto-refresh

Add the following to `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "cd <token_budget location> && poetry run python token_status.py"
},
"hooks": {
  "SessionStart": [{ "hooks": [{ "type": "command", "async": true,
    "command": "cd <token_budget location here!> && poetry run python get_token_budget.py > /dev/null 2>&1" }] }],
  "UserPromptSubmit": [{ "hooks": [{ "type": "command", "async": true,
    "command": "cd <token_budget location here!> && poetry run python get_token_budget.py > /dev/null 2>&1" }] }],
  "Stop": [{ "hooks": [{ "type": "command", "async": true,
    "command": "cd <token_budget location here!> && poetry run python get_token_budget.py > /dev/null 2>&1" }] }]
}
```

The hooks refresh the cache on session start, each prompt submit, and after each
response — so the status bar always reflects your latest spend.
