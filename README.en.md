# audite-seu-claude

**🇧🇷 [Português](README.md) · 🇺🇸 English · 🇪🇸 [Español](README.es.md)**

## 📖 User guide

Complete guide (landing page + walkthrough): **https://inematds.github.io/audite-seu-claude/guia/en/**

## What it is

An auditor for your Claude Code before (or after) switching to **Claude Fable 5.2**. It reads your `CLAUDE.md`, skills, agents, memories, hooks, plugins, and scripts, and finds lines written for earlier models that now get in the way — the “invisible inheritance.” It generates a report with charts and a list of suggestions; you mark what you approve, and your own Claude applies only those changes.

Read-only: `varrer.py` does not change any files. No network access, only Python 3 (standard library).

## Why

Anthropic published the [Prompting Claude Fable 5.2](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2) page with 10 points to watch. Fable 5.2 follows instructions literally, so old lines can have a different effect: asking it to show its reasoning in the response can lead to refusals, “answer without thinking” does not reduce reasoning, instructions to “always use subagents” multiply costs, and accumulated “never” rules hold up routine work. Anthropic’s recommended order: set effort to `high`, clean up old instructions, run long tasks, and fix one symptom at a time while measuring.

## Quick start

```bash
git clone https://github.com/inematds/audite-seu-claude.git ~/audite-seu-claude
cd ~/meu-projeto
python3 ~/audite-seu-claude/varrer.py . --home --html relatorio.html --saida-json relatorio.json
# open relatorio.html, mark what you approve, click "gerar correcoes.md"
# in Claude Code: "aplique o correcoes.md"
```

## What it looks for

| Layer | Rule | Anthropic point | Severity |
|---|---|---|---|
| Fable 5.2 | Asks for reasoning in the response text | P10 Refusals | high |
| Fable 5.2 | “Answer without thinking” / “think less” | P8 Old instructions | medium |
| Fable 5.2 | Token budget written in the prompt | P8 | medium |
| Fable 5.2 | “Treat the previous response as final” | P8 | medium |
| Fable 5.2 | Rigid style rule (word limit, telegraphic wording) | P8 | medium |
| Fable 5.2 | Instruction to always delegate to subagents | P6 Subagents | medium |
| Fable 5.2 | Absolute instruction in all caps (“non-negotiable”) | P7 Accumulated caution | medium |
| Fable 5.2 | “Never try again” / “stop at the first error” | P7 | medium |
| Fable 5.2 | Approval for “any action” | P3 Approvals | medium |
| Fable 5.2 | `claude -p "continue"` in a script | P3 | low |
| Fable 5.2 | “Never” with no reason or scope (a safety rule becomes “protected”) | P7 | low / info |
| Fable 5.2 | “The code is yours” | P4 Code ownership | info |
| Fable 5.2 | Fixed `max` effort, default `xhigh`, old model setting, Fable 5.2 on low/medium | P1 Effort | high → info |
| Fable 5.2 | Missing wording for finishing the task / reporting progress / clear reporting | P2, P5, P9 | info |
| Volume | Fixed context weight (CLAUDE.md, MEMORY.md, skill descriptions) | — | chart |
| Volume | Many skills, duplicate or similar skills, unused skill (`--uso 30`) | — | low / info |
| Volume | Memories unchanged for more than 60 days; enabled hooks and plugins | P7 | info |

## Contents

| File | What it does |
|---|---|
| `varrer.py` | The auditor. Options: `--home`, `--html`, `--saida-json`, `--json`, `--uso DAYS`, `--anonimo`, `--fundo N`, `--estrito` (CI), `--correcoes IDs --de relatorio.json`. |
| `blocos/` | Ready-to-paste text for `CLAUDE.md`: `terminar-tarefa.md`, `avisar-progresso.md`, `relatorio-claro.md` (translations of the official texts, with costs measured by Anthropic), and `aprovacoes.md` (template with a list of named actions). Originals in `blocos/en/`. |
| `skill/audite-seu-claude/` | Skill for Claude Code: audits, waits for your approval, applies `correcoes.md`. Copy it to `~/.claude/skills/`. |
| `tests/` | 18 tests with no network access: `python3 -m unittest discover tests`. |

## The process, from start to finish

| # | Step | Command | Who |
|---|---|---|---|
| 1 | Download the kit | `git clone https://github.com/inematds/audite-seu-claude.git ~/audite-seu-claude` | 🧠 you |
| 2 | Set Fable 5.2 to `high` for long tasks | `/effort high` (or `--effort high` in bots) | 🧠 you |
| 3 | Audit | `python3 ~/audite-seu-claude/varrer.py . --home --html relatorio.html --saida-json relatorio.json` | ⚙️ script |
| 4 | Read the report and mark what you approve | open `relatorio.html` → "gerar correcoes.md" | 🧠 you |
| 5 | Apply only approved changes | in Claude Code: "aplique o correcoes.md" | 🤖 Claude |
| 6 | Check | run step 3 again and compare | ⚙️ script |
| 7 | Run the longest task and note where it stops, goes quiet, or delegates too much | — | 🧠 you |
| 8 | For each symptom, paste the right block and measure (one at a time) | `blocos/*.md` | 🧠 + 🤖 |

## Cautions

- The auditor flags issues; you decide what to do. Safety rules (API, credits, deleting, publishing) are marked as **protected**: the suggestion is to give them scope and a reason, never to delete them.
- Plugin file: do not edit it (it will revert on update). Write in the global `CLAUDE.md` that the rule does not apply.
- The text in `blocos/` costs tokens (finishing: +~30%; progress updates: +~20%, Anthropic figures). Paste it only if you see the symptom.

MIT License.