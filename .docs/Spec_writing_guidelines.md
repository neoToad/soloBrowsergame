# Spec Writing Guidelines

Specs are for communicating intent, not implementation. The CLI agent can read the codebase — don’t repeat it or second-guess it.

## Rules

- **State what, not how.** Describe the desired behaviour and constraints. Let the agent figure out which files and functions to touch.
- **No code snippets.** Avoid example implementations — they can conflict with the actual codebase and anchor the agent to a wrong approach.
- **No file or function references.** The agent will find the right places itself.
- **No migration or test instructions.** The agent knows to write these.
- **Keep it short.** If a spec needs more than a few sentences and a reference table, it’s probably too detailed.

## What a Good Spec Contains

- The feature or behaviour being added
- The core formula, rule, or logic in plain language
- Any hard constraints (e.g. “must never exceed X”)
- A reference table if exact values matter

## What a Good Spec Omits

- Which files or functions to edit
- Code examples or pseudocode
- Migration commands
- Test cases
- Anything the agent can infer from the codebase