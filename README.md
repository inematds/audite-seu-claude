# audite-seu-claude

[![audite-seu-claude](guia/assets/banner.jpg)](https://inematds.github.io/audite-seu-claude/guia/)

**🇧🇷 Português · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

## 📖 Guia de uso

Guia completo (landing + passo a passo): **https://inematds.github.io/audite-seu-claude/guia/**

## O que é

Um auditor para o seu Claude Code antes (ou depois) de passar para o **Claude Fable 5.2**. Ele lê o seu `CLAUDE.md`, skills, agentes, memórias, hooks, plugins e scripts, e acha as linhas escritas para modelos anteriores que agora atrapalham — a "herança invisível". Gera um relatório com gráficos e uma lista de sugestões; você marca o que aprova, e o seu próprio Claude aplica só isso.

Só leitura: o `varrer.py` não muda nenhum arquivo. Sem rede, só Python 3 (biblioteca padrão).

## Por quê

A Anthropic publicou a página [Prompting Claude Fable 5.2](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2) com 10 pontos de atenção. O Fable 5.2 segue instruções ao pé da letra, então linhas antigas mudam de efeito: pedir o raciocínio no texto pode dar recusa, "responda sem pensar" não reduz o pensamento, ordem de "sempre usar subagentes" multiplica o custo, regras "nunca" acumuladas seguram trabalho de rotina. A ordem que a Anthropic recomenda: esforço em `high`, limpar as instruções antigas, rodar as tarefas longas, corrigir um sintoma por vez medindo.

## Começo rápido

```bash
git clone https://github.com/inematds/audite-seu-claude.git ~/audite-seu-claude
cd ~/meu-projeto
python3 ~/audite-seu-claude/varrer.py . --home --html relatorio.html --saida-json relatorio.json
# abra relatorio.html, marque o que aprova, clique em "gerar correcoes.md"
# no Claude Code: "aplique o correcoes.md"
```

## O que ele procura

| Camada | Regra | Ponto da Anthropic | Severidade |
|---|---|---|---|
| Fable 5.2 | Pede o raciocínio no texto da resposta | P10 Recusas | alta |
| Fable 5.2 | "Responda sem pensar" / "pense menos" | P8 Instruções antigas | média |
| Fable 5.2 | Orçamento de tokens escrito no prompt | P8 | média |
| Fable 5.2 | "Trate a resposta anterior como encerrada" | P8 | média |
| Fable 5.2 | Regra rígida de estilo (limite de palavras, telegráfico) | P8 | média |
| Fable 5.2 | Ordem de sempre delegar a subagentes | P6 Subagentes | média |
| Fable 5.2 | Ordem absoluta em caixa alta ("não é negociável") | P7 Cautela acumulada | média |
| Fable 5.2 | "Nunca tente de novo" / "pare no primeiro erro" | P7 | média |
| Fable 5.2 | Aprovação para "qualquer ação" | P3 Aprovações | média |
| Fable 5.2 | `claude -p "continue"` em script | P3 | baixa |
| Fable 5.2 | "Nunca" sem motivo nem alcance (regra de segurança vira "protegida") | P7 | baixa / info |
| Fable 5.2 | "O código é seu" | P4 Dono do código | info |
| Fable 5.2 | Esforço `max` fixo, `xhigh` padrão, ajuste de modelo antigo, Fable 5.2 em low/medium | P1 Esforço | alta → info |
| Fable 5.2 | Falta o texto de terminar a tarefa / avisar progresso / relatório claro | P2, P5, P9 | info |
| Volume | Peso do contexto fixo (CLAUDE.md, MEMORY.md, descrições de skills) | — | gráfico |
| Volume | Muitas skills, skill repetida ou parecida, skill sem uso (`--uso 30`) | — | baixa / info |
| Volume | Memórias sem mudança há mais de 60 dias; hooks e plugins ligados | P7 | info |

## Conteúdo

| Arquivo | O que faz |
|---|---|
| `varrer.py` | O auditor. Opções: `--home`, `--html`, `--saida-json`, `--json`, `--uso DIAS`, `--anonimo`, `--fundo N`, `--estrito` (CI), `--correcoes IDs --de relatorio.json`. |
| `blocos/` | Textos prontos para colar no `CLAUDE.md`: `terminar-tarefa.md`, `avisar-progresso.md`, `relatorio-claro.md` (traduções dos textos oficiais, com o custo medido pela Anthropic) e `aprovacoes.md` (modelo com a lista de ações nomeadas). Originais em `blocos/en/`. Mais `biblioteca-skills.md`: como guardar as skills que você não usa todo dia. |
| `skill/audite-seu-claude/` | Skill para o Claude Code: audita, espera a sua aprovação, aplica o `correcoes.md`. Copie para `~/.claude/skills/`. |
| `tests/` | 19 testes sem rede: `python3 -m unittest discover tests`. |

## O processo, do início ao fim

| # | Passo | Comando | Quem |
|---|---|---|---|
| 1 | Baixar o kit | `git clone https://github.com/inematds/audite-seu-claude.git ~/audite-seu-claude` | 🧠 você |
| 2 | Pôr o Fable 5.2 em `high` nas tarefas longas | `/effort high` (ou `--effort high` nos robôs) | 🧠 você |
| 3 | Auditar | `python3 ~/audite-seu-claude/varrer.py . --home --html relatorio.html --saida-json relatorio.json` | ⚙️ script |
| 4 | Ler o relatório e marcar o que aprova | abrir `relatorio.html` → "gerar correcoes.md" e mover o arquivo baixado para a pasta do projeto (ou `varrer.py --correcoes A001,A004 --de relatorio.json --saida correcoes.md`) | 🧠 você |
| 5 | Aplicar só o aprovado | no Claude Code: "aplique o correcoes.md" | 🤖 Claude |
| 6 | Conferir | rodar o passo 3 de novo e comparar | ⚙️ script |
| 7 | Rodar a tarefa mais longa e anotar onde ele para, cala ou delega demais | — | 🧠 você |
| 8 | Para cada sintoma, colar o bloco certo e medir (um por vez) | `blocos/*.md` | 🧠 + 🤖 |

## Dica: biblioteca de skills

Toda skill em `~/.claude/skills` carrega a descrição em toda sessão. Em vez de apagar as que você usa pouco, guarde-as numa **biblioteca**: uma pasta fora do carregamento (ex.: `~/projetos/skills-reserva/.claude/skills`) com um `INDICE.md` (nome, para quê, palavras de busca). Uma linha no `CLAUDE.md` global manda o Claude buscar no índice quando você pedir uma skill que não está carregada. Antes de mover, confira se outra skill, script ou timer chama a skill. Na máquina do autor: 148 → 107 skills carregadas, 13,7 mil → 9,6 mil tokens de descrição por sessão. Passo a passo e a linha pronta: [`blocos/biblioteca-skills.md`](blocos/biblioteca-skills.md).

## Cuidados

- O auditor sinaliza; quem decide é você. Regra de segurança (API, crédito, apagar, publicar) aparece como **protegida**: a sugestão é dar alcance e motivo, nunca apagar.
- Arquivo de plugin: não edite (volta na atualização). Escreva no `CLAUDE.md` global que aquela regra não vale.
- Os textos de `blocos/` custam tokens (terminar: +~30%; avisar progresso: +~20%, números da Anthropic). Cole só se você vê o sintoma.

Licença MIT.
