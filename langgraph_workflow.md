# LangGraph Workflow Architecture

Based on the `agent/graph/workflow.py` definitions, here is the full visual representation of the agent's workflow using Mermaid.

```mermaid
flowchart TD
  %% Nodes
  START((START))
  END((END))
  
  guardrails_input(guardrails_input)
  guardrails_output(guardrails_output)
  context_injector(context_injector)
  planner(planner)
  plan_approval(plan_approval)
  clarifier(clarifier)
  skill_manager(skill_manager)
  executor(executor)
  direct_chat(direct_chat)
  check_safety(check_safety)
  tools(tools)
  loop_recovery(loop_recovery)
  evaluator(evaluator)
  summary_node(summary_node)
  linter_node(linter_node)
  title_generator(title_generator)

  %% Main routing logic
  START --> guardrails_input
  
  guardrails_input -.->|blocked| END
  guardrails_input -.->|requires title| title_generator
  guardrails_input -.->|plan/goal mode| context_injector
  guardrails_input -.->|direct chat| direct_chat
  guardrails_input -.->|default| executor

  title_generator -.->|plan/goal mode| context_injector
  title_generator -.->|default| executor

  context_injector --> planner
  
  planner -.->|has active skill| skill_manager
  planner -.->|plan mode| plan_approval
  planner -.->|default| executor

  plan_approval -.->|done| END
  plan_approval -.->|rejected| planner
  plan_approval -.->|approved| executor

  skill_manager --> executor
  
  executor -.->|loop threshold met| loop_recovery
  executor -.->|hard loop escalated| clarifier
  executor -.->|has tool calls| check_safety
  executor -.->|goal mode, modified files| linter_node
  executor -.->|goal mode, done| evaluator
  executor -.->|done| guardrails_output

  check_safety -.->|denied / skipped| executor
  check_safety -.->|approved| tools
  tools --> executor

  linter_node -.->|failed| executor
  linter_node -.->|passed| evaluator

  evaluator -.->|not done| executor
  evaluator -.->|done| guardrails_output

  loop_recovery --> executor
  clarifier --> executor
  summary_node --> executor
  
  direct_chat --> guardrails_output
  guardrails_output --> END
```

### Key Behaviors:
- **Safety checks**: Occur on input and output (guardrails), and before every tool execution (check_safety).
- **Tool usage**: The `executor` produces tool calls, they go through `check_safety`, and then to `tools`, which routes back to the `executor`.
- **Loop recovery**: Unproductive loops are sent to `loop_recovery` or escalated to a `clarifier` node.
- **Verification**: In goal mode, any file edits are verified by a `linter_node` and then an `evaluator` before being considered done.
- **Planning**: In plan mode, a `planner` generates a plan and pauses at `plan_approval` before the `executor` proceeds.
