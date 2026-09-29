# Maintaining Pipeline Diagrams Skill Design

## Objective

Create a reusable global skill named `maintaining-pipeline-diagrams` for keeping
Mermaid pipeline diagrams synchronized with the implementation. The same skill
must be discoverable by Claude, OpenCode, and Codex.

## Installation architecture

Maintain one canonical skill directory in the user's Obsidian `Skills`
directory. Install symbolic links to that directory in each runtime's global
skill directory:

- `~/.claude/skills/maintaining-pipeline-diagrams`
- `~/.config/opencode/skills/maintaining-pipeline-diagrams`
- `~/.codex/skills/maintaining-pipeline-diagrams`

This avoids divergent copies while retaining global discovery in all three
runtimes.

## Trigger and scope

The skill applies when an agent creates or updates a Mermaid architecture,
workflow, or pipeline diagram that communicates both implementation status and
cognitive or LLM involvement. It should update an existing authoritative
diagram instead of creating competing diagrams unless the user asks for a new
view.

## Visual contract

- Implemented and verified deterministic nodes use green fill and solid borders.
- Pending deterministic nodes use neutral gray fill and dashed borders.
- LLM or other cognitive nodes use purple fill.
- Cognitive nodes use solid borders when implemented and verified, and dashed
  borders when pending.
- Solid arrows represent wired and verified flows.
- Dashed arrows represent planned or not-yet-verified flows.
- A concise text legend accompanies the diagram.

An agent may mark a node or connection as implemented only after checking the
available code, tests, or equivalent execution evidence. Uncertainty remains
pending rather than being guessed.

## Skill contents

The canonical directory contains:

- `SKILL.md` with the workflow, visual contract, Mermaid class definitions, a
  compact example, and common mistakes.
- `agents/openai.yaml` with Codex-facing display metadata and normal implicit
  discovery enabled.

No scripts or additional references are needed for the first version.

## Validation

Before deployment:

1. Run a baseline scenario without the skill and record where an agent's output
   fails the agreed convention.
2. Create the minimum skill addressing those observed failures.
3. Run the same scenario with the skill and inspect the resulting Mermaid.
4. Run Codex's skill validator against the canonical directory.
5. Confirm all three global links resolve to the canonical directory and expose
   identical `SKILL.md` content.

## Boundaries

The skill does not decide product architecture, declare work implemented without
evidence, alter source code, or require every project to use this visual system.
It applies when this status-aware Mermaid convention is requested or already in
use.
