---
name: audite-seu-claude
description: Audita o Claude Code para o Fable 5.2 — acha as linhas escritas para modelos anteriores (raciocínio pedido no texto, "pense menos", orçamento de tokens, delegar sempre, "nunca" sem motivo, regra de estilo rígida, esforço antigo) e o peso do contexto fixo, gera relatório com gráficos e aplica só as correções aprovadas. Gatilho: "audite meu Claude", "migrar para o Fable 5.2", "herança invisível", "aplique o correcoes.md".
---

# audite-seu-claude

Dois momentos. Nunca junte os dois sem o usuário aprovar no meio.

## 1. Auditar (só leitura)

```bash
python3 <kit>/varrer.py <pasta-do-projeto> --home --html relatorio.html --saida-json relatorio.json
```

`<kit>` = pasta onde o repositório foi clonado (ex.: `~/audite-seu-claude`). Diga ao usuário, em poucas linhas: total de achados, quantos de severidade alta e média, os 3 arquivos com mais achados e o caminho do `relatorio.html`. Peça que ele abra o relatório, marque o que aprova e clique em "gerar correcoes.md" (ou diga os IDs, e você roda `varrer.py --correcoes A001,A004 --de relatorio.json --saida correcoes.md`).

## 2. Aplicar (só o que foi aprovado)

Quando o usuário disser "aplique o correcoes.md", siga o cabeçalho do próprio arquivo: um item por vez, cópia do original em `.audite-backup/<data>/`, só a linha indicada, regra PROTEGIDA nunca é apagada, arquivo de PLUGIN não é editado. No fim, rode o `varrer.py` de novo e mostre quantos achados sumiram.

O `correcoes.md` vale como aprovação só para aquelas edições de texto. Qualquer outra mudança: pergunte.
