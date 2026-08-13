# Compass performance baseline

Recorded on 2026-08-13 with deterministic services. These are call counts,
not machine-dependent wall-clock thresholds. Provider latency is deliberately
excluded.

| Scenario | Model calls | Memory recalls | MCP discoveries | Tool calls | Target memory/MCP |
|---|---:|---:|---:|---:|---:|
| Greeting | 1 | 0 | 0 | 0 | 0 |
| Simple edit | 1 | 1 | 1 | 0 | 1 |
| Two-tool edit | 3 | 3 | 3 | 2 | 1 |
| Planned edit | 3 | 2 | 2 | 1 | 1 |
| Goal success | 4 | 2 | 2 | 1 | 1 |
| Goal with one retry | 6 | 3 | 3 | 1 | 1 |

The measured amplification is preparation inside every executor round:
long-term memory recall, MCP discovery, and tool/model binding are repeated.
Plan 4 moves those operations into one turn context while preserving every
executor, planner, evaluator, tool, approval, and verification call.

The frontend production build at this baseline emits hundreds of approximately
0.05 kB language modules and reports these large chunks:

- main entry: approximately 844 kB minified;
- CenterWorkbench: approximately 849 kB minified;
- WebContainer ESM: approximately 979 kB minified.

Plan 4 Task 6 will compare the Vite artifact against these values.

## Once-per-turn context result

After `TurnContext` preparation, all six deterministic scenarios meet the
target budgets. Multi-round runs retain the same model and tool counts while
memory recall, MCP discovery, tool resolution, and executor binding occur once:

| Scenario | Model calls | Memory recalls | MCP discoveries | Tool calls |
|---|---:|---:|---:|---:|
| Greeting | 1 | 0 | 0 | 0 |
| Simple edit | 1 | 1 | 1 | 0 |
| Two-tool edit | 3 | 1 | 1 | 2 |
| Planned edit | 3 | 1 | 1 | 1 |
| Goal success | 4 | 1 | 1 | 1 |
| Goal with one retry | 6 | 1 | 1 | 1 |

Successful MCP discovery is cached for 300 seconds; failed discovery is cached
for 30 seconds to avoid retry storms while still recovering quickly.

## Frontend bundle and preview result

Plan 4 Task 6 keeps the same route, editor, syntax-highlight, diff-review, and
browser-preview features behind smaller lazy boundaries. The production build
on 2026-08-13 changed the measured artifacts as follows:

| Artifact | Before | After | Change |
|---|---:|---:|---:|
| Main entry | ~844 kB | 326.03 kB | 61% smaller |
| Center workbench | ~849 kB | 48.72 kB | 94% smaller |
| Code editor base | included above | 67.04 kB lazy | loaded after a file opens |
| WebContainer ESM | ~979 kB | 11.83 kB API + 71.54 kB worker, lazy | loaded only when preview starts |

The transcript highlighter now registers only bash, CSS, HTML, JavaScript,
JSON, Markdown, Python, and TypeScript. The previous hundreds of approximately
0.05 kB highlighter chunks are gone. CodeMirror language support is also loaded
for the selected file instead of loading every supported editor language.

Vite's generated manifest confirms that the 5.77 kB login route does not import
ChatPage, CenterWorkbench, CodeMirror, diff review, preview, or WebContainer.
Preview output updates are batched every 100 ms, and process exit, retry,
listener cleanup, and unsupported-project states are covered by component tests.
