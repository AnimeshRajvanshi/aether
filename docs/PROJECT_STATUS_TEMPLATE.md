# PROJECT_STATUS_TEMPLATE.md

**Instructions for Claude:** Fill this template accurately based on current repo state (README.md, CLAUDE.md, ADRs, recent commits, code, stage outputs). Update YAML frontmatter and all sections. Keep it concise but complete for agent context. Commit with message like "chore: update PROJECT_STATUS.md for [sprint]".

```yaml
phase: "[e.g. Sprint 1 - Ontology and Eval Harness]"
status: "[In Progress | Blocked | Complete]"
last_updated: "2026-06-08"
updated_by: "Claude"
confidence: "[High | Moderate | Low]"
links:
  notion_hub: "[link to Notion Project page]"
  adrs: ["docs/adr/0001-xxx.md"]
  key_commits: ["abc1234"]
key_files:
  - "packages/ontology/"
  - "eval/harness.py"
open_tasks:
  - "[Task description with owner and due]"
blockers:
  - "[Any blockers]"
recent_changes:
  - "[Summary of last changes and rationale]"
validation_status:
  tests: "[e.g. 54 tests passing]"
  sprint_gate: "[e.g. aether reproduce <event_id> for EMIT proof-of-life]"
next_milestones:
  - "[Next actions]"
notes_for_agents:
  "Read CLAUDE.md fully before changes. Run uv run pytest and aether-eval run before committing. Never fabricate data."
```

## Executive Summary
[1-2 paragraph overview of current state and goals]

## Architecture Overview
[High-level from README + CLAUDE.md layers]

## Key Decisions & ADRs
[List or link recent ADRs with one-sentence rationale]

## Open Tasks & Blockers
[Detailed list]

## Validation & Testing
[Current test status, Sprint 1 gate progress]

## Next Steps
[Prioritized]

## Context for Future Agents
[Any special notes from CLAUDE.md or current state, including data source locks and scientific integrity rules]
