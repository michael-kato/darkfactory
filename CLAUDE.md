# darkfactory

AI-driven software development factory. Each project lives in `projects/<name>/`.

## Factory Structure
```
darkfactory/
  projects/           All sub-projects
    <name>/           One project (any stack, any domain)
      CLAUDE.md       Project-specific conventions
      test.sh         Project test runner (called by hooks after every edit)
      specs/          Work items for this project
  .claude/
    settings.json     Hook configuration (PostToolUse tests, Stop gate)
    hooks/            Factory automation scripts
    runs/             Session records (JSON, one per invoke.sh run)
  invoke.sh           Factory trigger: ./invoke.sh projects/<name>/specs/<spec>.md
  CLAUDE.md           This file — factory-level conventions
```

## Adding a New Project
1. Create `projects/<name>/`
2. Write `projects/<name>/CLAUDE.md` — stack, conventions, test command
3. Write `projects/<name>/test.sh` — runs the project's test suite, exits 0 on pass
4. Write `projects/<name>/specs/<NN>-<slug>.md` — first work item
5. Run: `./invoke.sh projects/<name>/specs/<NN>-<slug>.md`

## Automated Commit Format
- Subject: `[automated] <project>: <description>`
- Branch: commit directly to the current branch — do not create a new branch
- Tests must be green before committing (enforced by Stop hook)

## Factory Hook Behavior
- Every file edit triggers the project's `test.sh` automatically
- Claude cannot finish a session while tests are red
- Run records saved to `.claude/runs/` with session ID for resumability

## Projects

| Project | Description | Stack |
|---|---|---|
| asscheck | 3D asset QA pipeline for VR games — geometry/UV/texture/PBR/armature checks before Unity import | Python · Blender 5.0.1 headless · Unity 6 |
