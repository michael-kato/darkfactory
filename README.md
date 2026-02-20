# darkfactory

AI-driven software development factory. Write a spec, run `invoke.sh`, get working code.

## How It Works

```
specs/ (per project)
  └── describe WHAT, not HOW
        │
        ▼
  invoke.sh
        │
        ▼
  Claude Code agent
  ├── explores the project
  ├── implements the spec
  ├── iterates on test failures (hooks auto-run tests on every edit)
  └── commits when green
```

The Stop hook blocks Claude from finishing until all tests pass. Hooks dispatch to each
project's own `test.sh`, so any language or test runner is supported.

## Usage

```bash
# Run a spec through the factory
./invoke.sh projects/<name>/specs/<spec>.md

# Resume a checkpointed run (session ID in .claude/runs/)
./invoke.sh projects/<name>/specs/<spec>.md --resume <session-id>
```

## Adding a Project

1. `mkdir -p projects/<name>/specs`
2. Write `projects/<name>/CLAUDE.md` — conventions, never-touch paths, test command
3. Write `projects/<name>/test.sh` — runs tests, exits 0 on pass
4. Write `projects/<name>/specs/01-<first-feature>.md` — acceptance criteria, not implementation
5. `./invoke.sh projects/<name>/specs/01-<first-feature>.md`

## Projects

| Name | Description | Stack |
|---|---|---|
| [asscheck](projects/asscheck/) | 3D asset QA pipeline for VR games | Python · Blender headless · Unity 6 |

## Architecture

```
darkfactory/
  projects/             Sub-projects (any stack, any domain)
    <name>/
      CLAUDE.md         Project conventions (injected into every agent run)
      test.sh           Project test runner
      specs/            Work items
  .claude/
    settings.json       Hook wiring
    hooks/
      run-tests.sh      PostToolUse → routes to project test.sh
      require-green.sh  Stop gate → blocks finish if tests are red
    runs/               JSON session records
  invoke.sh             Factory entry point
  CLAUDE.md             Factory-level conventions
```
