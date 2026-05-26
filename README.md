# Powerlifting Coach

Multi-agent AI coaching system for tkm. Built on Claude Code with subagent orchestration.

---

## Architecture

A **Head Coach** orchestrator that delegates to five specialist agents:

- **SBD Agent** — squat/bench/deadlift programming, RPE progression, peaking
- **Mobility Agent** — warmups, daily routines, asymmetry corrections, injury management
- **Diet Agent** — macros, body composition, performance fueling
- **Aesthetics Agent** — hypertrophy, accessory selection, weak-point training
- **Logging Agent** — converts natural language input into structured session logs; routes observations to the right reference files; runs weekly pattern synthesis

Each agent has its own persona file in `agents/`. The Head Coach (defined in the top-level `CLAUDE.md`) reads the situation, decides which agents need to weigh in, spawns subagents via the Task tool, and synthesizes their input into a unified recommendation.

The Logging Agent is the ingestion layer — whenever tkm describes a completed session, reports new pain, or dumps free-form notes, Head Coach spawns Logging to parse and structure it. Other agents then read structured logs rather than free-form text.

---

## Directory Structure

```
powerlifting-coach/
├── CLAUDE.md                          ← Head Coach instructions (read by Claude Code automatically)
├── README.md                          ← This file
├── agents/                            ← Specialist agent personas
│   ├── sbd-agent.md
│   ├── mobility-agent.md
│   ├── diet-agent.md
│   ├── aesthetics-agent.md
│   └── logging-agent.md
├── athlete/                           ← Athlete context
│   ├── profile.md
│   ├── injury-history.md
│   ├── current-stats.md
│   └── goals.md
├── program/                           ← Current programming
│   ├── current-block.md
│   ├── this-week.md
│   └── progression-rules.md
├── reference/                         ← Long-lived reference content
│   ├── warmup-library.md
│   ├── mobility-protocols.md
│   ├── coaching-cues.md
│   ├── exercise-substitutions.md
│   ├── nutrition-baseline.md
│   └── past-coach-programs/           ← CSVs from human coach
├── logs/
│   ├── sessions/                      ← YYYY-MM-DD.md per session
│   ├── decisions/                     ← Multi-agent decision logs
│   └── patterns/                      ← Weekly synthesis
├── inbox/                             ← Raw notes to be processed
└── scripts/
    └── parse-coach-csv.py             ← Convert coach's CSVs to markdown
```

---

## Setup

1. Clone to a local directory
2. Install Claude Code: `npm install -g @anthropic-ai/claude-code`
3. Open this directory in VSCode with the Claude Code extension
4. Fill in athlete files: `athlete/current-stats.md`, `athlete/goals.md`, `program/current-block.md`, `program/this-week.md`
5. Drop coach's CSVs into `reference/past-coach-programs/`
6. Run `python scripts/parse-coach-csv.py` if you want to generate markdown summaries
7. Start a conversation: open Claude Code in the directory and just talk

---

## Usage Patterns

### Daily workflow

**Before training:**
```
"I'm hitting [session] today. Give me my warmup and confirm the prescription."
```
Head Coach reads logs, plan, and injury history. Mobility Agent gives the warmup; SBD Agent confirms loads.

**After training (natural language dump is fine):**
```
"Yo just finished. Did squat 3 sets at 365, first two RPE 7, third was a grinder felt like 9. Left hip a bit tight but didn't flare. 4x8 bench at 185 after, felt fresh. Slept 5 hours."
```
Head Coach spawns Logging Agent → parses the dump into a structured session log → routes side-content (PRs, pain notes) to the right reference files → flags anything SBD or Mobility should weigh in on.

**Quick gym questions (via iPhone Claude app):**
The mirror Claude Project on mobile has the core context. Quick warmup or modification questions work there.

### Weekly review (Sundays)

```
"Run the weekly review."
```
Logging Agent runs the pattern synthesis first (reads all session logs from the week, writes `logs/patterns/YYYY-WW.md`). Each specialist agent then reads that synthesis and reports on their domain. Head Coach synthesizes everything and proposes next week's plan.

### Multi-agent decisions

```
"I'm scheduled for heavy squat tomorrow but my left hip is locked from yesterday's deads. Multi-agent: what should we do?"
```
Head Coach spawns SBD + Mobility, surfaces any disagreement, gives a recommendation.

---


## Sync Ritual

**At gym (iPhone):** quick capture into a synced note or directly into mobile Claude.

**Evening (laptop):** "Process inbox" — Head Coach reads, routes content to correct files, commits to git.

**Sunday (laptop):** Weekly review. Update mobile Project knowledge with any changed files.

---

## Hard Rules (See CLAUDE.md for full set)

- Never recommend pushing through sharp pain
- Always factor asymmetry patterns into programming
- Recommend PT consultation when warranted — don't try to be the PT
- Surface agent disagreements rather than hiding them
- Don't invent context not in the files

---

## Iteration

This system is a v1. Expect to:
- Refine agent personas as their gaps become visible
- Add specialist agents (recovery agent? meet prep agent?) as needs emerge
- Improve the iPhone sync workflow as friction surfaces
- Periodically consolidate logs into pattern summaries

Commit changes to git so the system evolution is traceable.
