# Batch dispatch safety (Linux fork)

Version 0.3.8.post1 gives each CLI launch an exclusively created UUID directory under
`~/.agent-compass/cli-workers`. Briefs, stdout, stderr, final JSON, launch arguments,
and an atomic `result.json` receipt belong to that launch alone.

Use `agentcompass roll --brief a.md --brief b.md --execution-mode read-only` for
read-only batches. Explicit “read-only” / “read only” wording also narrows execution.
Currently only the Codex CLI adapter qualifies: it sets the read-only sandbox,
disables approval escalation, and ignores user configuration to avoid inheriting
MCP write tools. Unsupported providers are excluded, not launched with weaker
permissions. Read-only jobs do not reuse an existing worker with unknown permissions.
The returned answer is saved by the supervisor outside the sandbox; workers do not
need write access to the project to deliver a plan. `--cli` explicitly requests a
local CLI launch for other roles.

Each CLI worker has a supervisor. Follow the returned `next_argv` to inspect its
receipt with `agentcompass worker status <run-directory>`. A zero exit is insufficient:
completion requires a structured report with a deliverable and verification. This
checks the report format, not the correctness of its claims. The coordinator still
reviews the deliverable. Quota errors latch the account for subsequent routing.
A supervisor killed with SIGKILL or a machine crash cannot publish a terminal receipt;
check its PID if a receipt remains running after the process disappears.

Argon's separate `gemini-argon-wtu-weekly` bucket is retained and scoped to Argon.
New provider limits cannot be hidden by an old catalog's explicit `draws` list.
Unknown quota buckets are retained conservatively rather than silently discarded.

Validation on Linux, 2026-11-04:

- Seven concurrent subprocess fixtures produced seven distinct briefs, outputs and
  completed receipts. Intro-only output failed validation; a quota failure latched.
- A live two-task batch selected Codex GPT-6.1 Sol medium through the router. Both
  workers returned correct calculations from a fixture file (42 and 8). The second
  worker's single write probe failed with “Read-only file system”; no probe file exists.
- The installed quota collector reads Argon as 0% remaining, and the installed
  allocator rejects `argon_high` on that specific window.
- The pre-existing planners were left untouched. Only the tray/dashboard service
  was restarted after verifying its process group contained those two UI processes.

The router and Linux desktop are separate Python environments. After updating the
router with `uv tool install --force <wheel>`, run `packaging/install_linux.py <wheel>`
to update the desktop and restore its launcher to the environment containing Qt.
