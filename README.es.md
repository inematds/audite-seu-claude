# audite-seu-claude

[![audite-seu-claude](guia/assets/banner-es.jpg)](https://inematds.github.io/audite-seu-claude/guia/es/)

🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · **🇪🇸 Español**

## 📖 Guía de uso

Guía completa (landing + paso a paso): **https://inematds.github.io/audite-seu-claude/guia/es/**

## Qué es

Un auditor para tu Claude Code antes (o después) de pasar a **Claude Fable 5.2**. Lee tu `CLAUDE.md`, skills, agentes, memorias, hooks, plugins y scripts, y encuentra las líneas escritas para modelos anteriores que ahora estorban: la «herencia invisible». Genera un informe con gráficos y una lista de sugerencias; marcas las que apruebas y tu propio Claude aplica solo esas.

Solo lectura: `varrer.py` no cambia ningún archivo. Sin red, solo Python 3 (biblioteca estándar).

## Por qué

Anthropic publicó la página [Prompting Claude Fable 5.2](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2) con 10 puntos de atención. Fable 5.2 sigue las instrucciones al pie de la letra, así que las líneas antiguas cambian de efecto: pedir el razonamiento en el texto puede causar un rechazo, «responde sin pensar» no reduce el razonamiento, ordenar «usar siempre subagentes» multiplica el costo y las reglas acumuladas de «nunca» frenan el trabajo rutinario. El orden recomendado por Anthropic: esfuerzo en `high`, limpiar las instrucciones antiguas, ejecutar las tareas largas y corregir un síntoma a la vez, midiendo.

## Inicio rápido

```bash
git clone https://github.com/inematds/audite-seu-claude.git ~/audite-seu-claude
cd ~/meu-projeto
python3 ~/audite-seu-claude/varrer.py . --home --html relatorio.html --saida-json relatorio.json
# abre relatorio.html, marca lo que apruebas, haz clic en "gerar correcoes.md"
# en Claude Code: "aplique o correcoes.md"
```

## Qué busca

| Capa | Regla | Punto de Anthropic | Severidad |
|---|---|---|---|
| Fable 5.2 | Pide el razonamiento en el texto de la respuesta | P10 Rechazos | alta |
| Fable 5.2 | «Responde sin pensar» / «piensa menos» | P8 Instrucciones antiguas | media |
| Fable 5.2 | Presupuesto de tokens escrito en el prompt | P8 | media |
| Fable 5.2 | «Trata la respuesta anterior como cerrada» | P8 | media |
| Fable 5.2 | Regla rígida de estilo (límite de palabras, telegráfico) | P8 | media |
| Fable 5.2 | Orden de delegar siempre a subagentes | P6 Subagentes | media |
| Fable 5.2 | Orden absoluta en mayúsculas («no es negociable») | P7 Precaución acumulada | media |
| Fable 5.2 | «Nunca lo intentes de nuevo» / «detente ante el primer error» | P7 | media |
| Fable 5.2 | Aprobación para «cualquier acción» | P3 Aprobaciones | media |
| Fable 5.2 | `claude -p "continue"` en un script | P3 | baja |
| Fable 5.2 | «Nunca» sin motivo ni alcance (una regla de seguridad se vuelve «protegida») | P7 | baja / info |
| Fable 5.2 | «El código es tuyo» | P4 Responsable del código | info |
| Fable 5.2 | Esfuerzo `max` fijo, `xhigh` predeterminado, ajuste de modelo antiguo, Fable 5.2 en low/medium | P1 Esfuerzo | alta → info |
| Fable 5.2 | Falta el texto para terminar la tarea / avisar del progreso / presentar un informe claro | P2, P5, P9 | info |
| Volumen | Peso fijo del contexto (CLAUDE.md, MEMORY.md, descripciones de skills) | — | gráfico |
| Volumen | Muchas skills, skills repetidas o parecidas, skills sin uso (`--uso 30`) | — | baja / info |
| Volumen | Memorias sin cambios desde hace más de 60 días; hooks y plugins activados | P7 | info |

## Contenido

| Archivo | Qué hace |
|---|---|
| `varrer.py` | El auditor. Opciones: `--home`, `--html`, `--saida-json`, `--json`, `--uso DIAS`, `--anonimo`, `--fundo N`, `--estrito` (CI), `--correcoes IDs --de relatorio.json`. |
| `blocos/` | Textos listos para pegar en `CLAUDE.md`: `terminar-tarefa.md`, `avisar-progresso.md`, `relatorio-claro.md` (traducciones de los textos oficiales, con el costo medido por Anthropic) y `aprovacoes.md` (modelo con la lista de acciones nombradas). Originales en `blocos/en/`. |
| `skill/audite-seu-claude/` | Skill para Claude Code: audita, espera tu aprobación y aplica el `correcoes.md`. Copia a `~/.claude/skills/`. |
| `tests/` | 18 pruebas sin red: `python3 -m unittest discover tests`. |

## El proceso de principio a fin

| # | Paso | Comando | Quién |
|---|---|---|---|
| 1 | Descargar el kit | `git clone https://github.com/inematds/audite-seu-claude.git ~/audite-seu-claude` | 🧠 tú |
| 2 | Poner Fable 5.2 en `high` para las tareas largas | `/effort high` (o `--effort high` en los robots) | 🧠 tú |
| 3 | Auditar | `python3 ~/audite-seu-claude/varrer.py . --home --html relatorio.html --saida-json relatorio.json` | ⚙️ script |
| 4 | Leer el informe y marcar lo que apruebas | abrir `relatorio.html` → «gerar correcoes.md» y mover el archivo descargado a la carpeta del proyecto (o `varrer.py --correcoes A001,A004 --de relatorio.json --saida correcoes.md`) | 🧠 tú |
| 5 | Aplicar solo lo aprobado | en Claude Code: «aplique o correcoes.md» | 🤖 Claude |
| 6 | Revisar | ejecutar de nuevo el paso 3 y comparar | ⚙️ script |
| 7 | Ejecutar la tarea más larga y anotar dónde se detiene, se queda callado o delega demasiado | — | 🧠 tú |
| 8 | Para cada síntoma, pegar el bloque adecuado y medir (uno a la vez) | `blocos/*.md` | 🧠 + 🤖 |

## Precauciones

- El auditor señala; tú decides. Las reglas de seguridad (API, crédito, borrar, publicar) aparecen como **protegidas**: la sugerencia es definir su alcance y motivo, nunca borrarlas.
- Archivo de plugin: no lo edites (volverá con la actualización). Escribe en el `CLAUDE.md` global que esa regla no se aplica.
- Los textos de `blocos/` cuestan tokens (terminar: +~30%; avisar del progreso: +~20%, cifras de Anthropic). Pégalos solo si observas el síntoma.

Licencia MIT.