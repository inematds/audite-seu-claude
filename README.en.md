# audite-seu-claude

[![audite-seu-claude](guia/assets/banner-en.jpg)](https://inematds.github.io/audite-seu-claude/guia/en/)

🇧🇷 [Português](README.md) · **🇺🇸 English** · 🇪🇸 [Español](README.es.md)

## 📖 User guide

Complete guide (landing page + walkthrough): **https://inematds.github.io/audite-seu-claude/guia/en/**

## What it is

An auditor for your Claude Code before (or after) switching to **Claude Fable 5.2**. It reads your `CLAUDE.md`, skills, agents, memories, hooks, plugins, and scripts, and finds lines written for earlier models that now get in the way—the “invisible inheritance.” It generates a report with charts and a list of suggestions; you choose what to approve, and your own Claude applies only those changes.

Read-only: `varrer.py` does not change any files. No network access; Python 3 only (standard library).

## Why

Anthropic published the [Prompting Claude Fable 5.2](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2) page with 10 points to watch. Fable 5.2 follows instructions to the letter, so old lines can have a different effect: asking it to show its reasoning in the response can lead to a refusal, “answer without thinking” does not reduce thinking, an instruction to “always use subagents” multiplies costs, and accumulated “never” rules hold up routine work. Anthropic’s recommended order: set effort to `high`, clean up old instructions, run the long tasks, and fix one symptom at a time while measuring.

## Quick start

```bash
git clone https://github.com/inematds/audite-seu-claude.git ~/audite-seu-claude
cd ~/meu-projeto
python3 ~/audite-seu-claude/varrer.py . --home --html relatorio.html --saida-json relatorio.json
# open relatorio.html, select what to approve, click "gerar correcoes.md"
# in Claude Code: "aplique o correcoes.md"
```

## What it looks for

| Layer | Rule | Anthropic point | Severity |
|---|---|---|---|
| Fable 5.2 | Requests reasoning in the response text | P10 Refusals | high |
| Fable 5.2 | “Answer without thinking” / “think less” | P8 Old instructions | medium |
| Fable 5.2 | Token budget written in the prompt | P8 | medium |
| Fable 5.2 | “Treat the previous answer as finished” | P8 | medium |
| Fable 5.2 | Rigid style rule (word limit, telegraphic style) | P8 | medium |
| Fable 5.2 | Instruction to always delegate to subagents | P6 Subagents | medium |
| Fable 5.2 | Absolute instruction in all caps (“non-negotiable”) | P7 Accumulated caution | medium |
| Fable 5.2 | “Never try again” / “stop at the first error” | P7 | medium |
| Fable 5.2 | Approval for “any action” | P3 Approvals | medium |
| Fable 5.2 | `claude -p "continue"` in a script | P3 | low |
| Fable 5.2 | “Never” without a reason or scope (a safety rule becomes “protected”) | P7 | low / info |
| Fable 5.2 | “The code is yours” | P4 Code ownership | info |
| Fable 5.2 | Fixed `max` effort, default `xhigh`, old model adjustment, Fable 5.2 on low/medium | P1 Effort | high → info |
| Fable 5.2 | Missing instructions to finish the task / report progress / provide a clear report | P2, P5, P9 | info |
| Volume | Fixed context weight (`CLAUDE.md`, MEMORY.md, skill descriptions) | — | chart |
| Volume | Too many skills, duplicate or similar skills, unused skill (`--uso 30`) | — | low / info |
| Volume | Memories unchanged for more than 60 days; enabled hooks and plugins | P7 | info |

## Contents

| File | What it does |
|---|---|
| `varrer.py` | The auditor. Options: `--home`, `--html`, `--saida-json`, `--json`, `--uso DIAS`, `--anonimo`, `--fundo N`, `--estrito` (CI), `--correcoes IDs --de relatorio.json`. |
| `blocos/` | Ready-to-paste text for `CLAUDE.md`: `terminar-tarefa.md`, `avisar-progresso.md`, `relatorio-claro.md` (translations of the official texts, with the cost measured by Anthropic), and `aprovacoes.md` (template with a list of named actions). Originals in `blocos/en/`. More in `biblioteca-skills.md`: how to keep the skills you don’t use every day. |
| `skill/audite-seu-claude/` | Skill for Claude Code: audits, waits for your approval, and applies `correcoes.md`. Copy it to `~/.claude/skills/`. |
| `tests/` | 18 tests with no network access: `python3 -m unittest discover tests`. |

## The process, start to finish

| # | Step | Command | Who |
|---|---|---|---|
| 1 | Download the kit | `git clone https://github.com/inematds/audite-seu-claude.git ~/audite-seu-claude` | 🧠 you |
| 2 | Set Fable 5.2 to `high` for long tasks | `/effort high` (or `--effort high` in bots) | 🧠 you |
| 3 | Audit | `python3 ~/audite-seu-claude/varrer.py . --home --html relatorio.html --saida-json relatorio.json` | ⚙️ script |
| 4 | Read the report and select what to approve | open `relatorio.html` → “gerar correcoes.md” and move the downloaded file to the project folder (or `varrer.py --correcoes A001,A004 --de relatorio.json --saida correcoes.md`) | 🧠 you |
| 5 | Apply only what was approved | in Claude Code: “aplique o correcoes.md” | 🤖 Claude |
| 6 | Check | run step 3 again and compare | ⚙️ script |
| 7 | Run the longest task and note where it stops, goes quiet, or delegates too much | — | 🧠 you |
| 8 | For each symptom, paste the right block and measure (one at a time) | `blocos/*.md` | 🧠 + 🤖 |

## Tip: skills library

Every skill in `~/.claude/skills` loads its description in every session. Instead of deleting the ones you rarely use, keep them in a **library**: a folder outside the loading path (e.g., `~/projetos/skills-reserva/.claude/skills`) with an `INDICE.md` (name, purpose, search terms). A line in the global `CLAUDE.md` tells Claude to look in the index when you ask for a skill that isn’t loaded. Before moving one, check whether another skill, script, or timer calls it. On the author’s machine: 148 → 107 loaded skills, 13.7k → 9.6k description tokens per session. Step-by-step instructions and the ready-to-use line: [`blocos/biblioteca-skills.md`](blocos/biblioteca-skills.md).

## Cautions

- The auditor flags items; you decide. Safety rules (API, credits, deleting, publishing) appear as **protected**: the suggestion is to clarify scope and reason, never to delete them.
- Plugin file: do not edit it (your changes will be overwritten in an update). Write in the global `CLAUDE.md` that the rule does not apply.
- Text in `blocos/` uses tokens (finish: +~30%; report progress: +~20%, Anthropic figures). Paste only if you see the symptom.

MIT License.