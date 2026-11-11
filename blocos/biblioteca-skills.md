# Biblioteca de skills: guarde as que você não usa todo dia

Toda skill em `~/.claude/skills` carrega a descrição dela em **toda** sessão. Com 100 ou 150 skills, isso dá cerca de 10 mil tokens antes de você escrever a primeira palavra. As descrições também disputam o mesmo pedido, e o modelo pode escolher a errada.

A saída não é apagar. É guardar numa **biblioteca**: uma pasta fora do carregamento, com um índice. O Claude só abre essa pasta quando você pede uma skill que não está carregada.

Na máquina do autor, a biblioteca derrubou as skills carregadas de 148 para 107 e o texto das descrições de 13,7 mil para 9,6 mil tokens por sessão.

## Passo a passo

1. **Veja quais estão paradas.**
   ```bash
   python3 varrer.py . --home --uso 30
   ```
   Os achados `skill-sem-uso` listam as skills que você não chamou nos últimos 30 dias. O contador só vê a skill que o Claude chamou ou que você digitou como `/nome`. A que roda por script ou timer aparece como zero mesmo sendo usada. Por isso o passo 2 existe.

2. **Confira quem chama cada uma antes de mover.** Ela fica no global se:
   - outra skill que fica a cita: `grep -rlw <nome> ~/.claude/skills/*/SKILL.md`
   - um script, timer ou prompt de bot a chama: procure `skills/<nome>`, `/<nome>` e `Skill(skill="<nome>")` nos seus projetos e em `~/.config/systemd/user/`.

3. **Crie a biblioteca e mova.**
   ```bash
   mkdir -p ~/projetos/skills-reserva/.claude/skills
   mv ~/.claude/skills/<nome> ~/projetos/skills-reserva/.claude/skills/
   ```
   Se a skill é um link (`ls -la` mostra `->`), recrie o link lá com o alvo absoluto e apague só o link antigo:
   ```bash
   ln -s "$(readlink -f ~/.claude/skills/<nome>)" ~/projetos/skills-reserva/.claude/skills/<nome>
   rm ~/.claude/skills/<nome>
   ```

4. **Escreva o índice** em `~/projetos/skills-reserva/INDICE.md`, com uma linha por skill: nome, para que serve e as palavras que alguém usaria para pedir. Fora do carregamento, a descrição não dispara mais sozinha, então é o índice que encontra a skill.
   ```markdown
   | Skill | Para quê (palavras de busca) |
   |---|---|
   | pr-to-video | Pull request do GitHub → vídeo explicativo da mudança |
   ```

5. **Avise o Claude** com uma linha no `~/.claude/CLAUDE.md`:
   ```markdown
   - Skills guardadas fora do carregamento: `~/projetos/skills-reserva`. Quando eu pedir uma skill que não está carregada, ou algo que nenhuma carregada cobre, busque antes com `grep -i "<palavra>" ~/projetos/skills-reserva/INDICE.md`; achando, leia `~/projetos/skills-reserva/.claude/skills/<nome>/SKILL.md` e siga. Não diga que a skill não existe sem olhar lá.
   ```

6. **Meça de novo** com `python3 varrer.py . --home`. A linha "Contexto fixo" mostra quantos tokens de descrição sobraram. A mudança vale a partir da próxima sessão.

## Usar e trazer de volta

- **Usar sem trazer de volta:** peça pelo nome. O Claude acha no índice, lê o `SKILL.md` e segue.
- **Usar com todos os recursos num projeto:** `cd ~/projetos/skills-reserva && claude` carrega as skills da biblioteca naquela pasta.
- **Trazer de volta ao global:** `mv ~/projetos/skills-reserva/.claude/skills/<nome> ~/.claude/skills/` (se for link, recrie o link em `~/.claude/skills/`).

## Cuidados

- Skill de **plugin** não se move: ela volta na próxima atualização do plugin. Para essas, desligue o plugin inteiro se não usa nenhuma das skills dele.
- Guarde a lista do que moveu (nome e se era pasta ou link). É ela que permite desfazer.
