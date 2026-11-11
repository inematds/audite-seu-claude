# CLAUDE.md — audite-seu-claude

Kit que audita o Claude Code para o Fable 5.2: `varrer.py` (stdlib, só leitura, sem rede), `blocos/` (textos oficiais traduzidos + aprovações), `skill/`, guia em `guia/` (PT) + `guia/en/` + `guia/es/`.

## Regras do projeto
- Só leitura: o `varrer.py` nunca muda arquivo; sugestões são texto. Quem edita é o Claude do usuário, com o `correcoes.md` aprovado.
- Regras e números vêm só da página oficial "Prompting Claude Fable 5.2" (lida em 11/11/2026). Não citar vídeo, canal ou autor de terceiros.
- Regra nova = regex em `REGRAS` + caso em `tests/fixtures/sujo` + garantia de zero em `tests/fixtures/limpo`.
- Exemplos publicados: `--anonimo`, sem nomes de pastas privadas.
- Tradução (blocos, guia, README): `inema-traduz`.
- Autor dos commits: `inematds <inematds@gmail.com>`.
- Testes sem rede: `python3 -m unittest discover tests`.

## Self-learning

When I correct you, or you catch yourself making a mistake: before continuing, add the lesson as a one-line rule at the TOP of the Lessons list below, so it never happens again.

## Lessons
- O índice de memória que entra na sessão é só o do projeto aberto (`projects/<caminho-com-traços>/memory/MEMORY.md`); somar todos inflou o peso de 5 mil para 46 mil tokens (11/11/2026).
- Plugins: contar só a versão mais nova em `plugins/cache/<loja>/<plugin>/`; `marketplaces/` e `temp_git_*` triplicavam os achados (11/11/2026).
- "Nunca" com inicial maiúscula: regex de palavra absoluta com `re.I` (11/11/2026).
