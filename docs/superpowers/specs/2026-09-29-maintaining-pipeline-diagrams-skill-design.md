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

The skill applies whenever an agent begins building or materially extending a
system with four or more interacting components. It also applies when an agent
is explicitly asked to create or update a Mermaid architecture, workflow, or
pipeline diagram. The agent should create one authoritative diagram early,
then maintain it as implementation progresses. If an authoritative diagram
already exists, update it instead of creating a competing view unless the user
asks for a new one.

## Visual contract

- Divide a system into coherent major stages identified by capital letters,
  such as `A — Intake` and `B — Extraction`.
- Give every component and decision within a stage a visible letter-number
  reference, such as `A1`, `A2`, and `B1`, so it can be cited unambiguously in
  discussion and documentation.
- Preserve published references when the flow remains recognizable. If a stage
  is materially reorganized, renumber that stage cohesively and update nearby
  prose references.
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

- `SKILL.md` with the workflow, grouping and numbering rules, visual contract,
  Mermaid class definitions, a compact example, and common mistakes.
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

The skill does not decide product architecture, declare work implemented
without evidence, or alter source code. Systems with three or fewer interacting
components do not trigger it automatically, though a user may still request the
convention explicitly.
