#!/usr/bin/env python3
"""varrer.py — audita o seu Claude Code para o Fable 5.2.

Procura, sem rede e sem mudar nada, as linhas escritas para modelos anteriores
("herança invisível") que a Anthropic manda revisar ao migrar para o Fable 5.2,
e mede quanto texto entra em toda sessão (CLAUDE.md, memórias, skills, hooks).

Duas camadas:
  fable52  — os 10 pontos da página "Prompting Claude Fable 5.2" (Anthropic)
  volume   — peso do contexto fixo, skills repetidas ou sem uso, memórias velhas

Uso:
  python3 varrer.py [PASTA ...] [--home] [--json] [--html arq.html] [--saida-json arq.json]
                    [--uso DIAS] [--anonimo] [--fundo N] [--estrito]
  python3 varrer.py --correcoes A003,A007 --de relatorio.json [--saida correcoes.md]

    --home        também lê ~/.claude (CLAUDE.md, settings, agents, skills, commands, memórias, plugins)
    --html        grava o relatório com gráficos (abre no navegador, sem internet)
    --saida-json  grava o relatório em JSON (é dele que sai o correcoes.md)
    --uso DIAS    lê os logs de sessão (~/.claude/projects/*.jsonl) e marca skills não usadas em DIAS dias
    --anonimo     troca a sua pasta pessoal por ~ (para publicar o relatório)
    --fundo N     profundidade máxima ao varrer cada PASTA (padrão 6)
    --estrito     sai com código 1 se houver achado de severidade alta (para CI)
    --correcoes   gera o pedido de correção para o Claude só com os IDs aprovados

Fonte das regras: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2
(lida em 11/11/2026). O script só sinaliza; quem decide é você.
"""
import argparse, html, json, os, re, sys, time
from datetime import date, datetime
from pathlib import Path

VERSAO = '1.0.1'
DOC = 'https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2'
HOME = str(Path.home())
IGNORAR_DIR = {'.git', 'node_modules', '.venv', 'venv', 'env', '__pycache__', 'dist', 'build', '.next', '.cache',
               'site-packages', '.mypy_cache', '.pytest_cache', '.tox', 'target', 'vendor', '.audite-backup',
               'output', 'guia', 'exemplos'}
EXT_SCRIPT = {'.sh', '.bash', '.py', '.js', '.mjs', '.cjs', '.ts', '.service', '.yml', '.yaml', '.toml'}
NOMES_INSTRUCAO = {'CLAUDE.md', 'CLAUDE.local.md', 'AGENTS.md', 'LESSONS.md', 'SKILL.md', 'MEMORY.md', 'GEMINI.md'}
DIRS_INSTRUCAO = {'agents', 'commands', 'skills', 'memory', 'prompts', 'rules'}
MAX_BYTES = 1_000_000
MAX_ARQ = 20_000

PONTOS = {
    1: 'Esforço', 2: 'Parada antecipada', 3: 'Aprovações', 4: 'Dono do código', 5: 'Silêncio / progresso',
    6: 'Subagentes', 7: 'Cautela acumulada', 8: 'Instruções antigas', 9: 'Relatório final', 10: 'Recusas',
}
SEVS = ['alta', 'media', 'baixa', 'info']

# ---------------------------------------------------------------- regras de linha (camada fable52)
# em: 'inst' = arquivos de instrução (.md), 'script' = scripts, 'ambos'
REGRAS = [
    dict(cod='raciocinio-no-texto', ponto=10, sev='alta', em='ambos',
         re=r'(mostre|escreva|explique|exponha|detalhe)\s+(o\s+)?(seu|teu)\s+racioc[ií]nio|racioc[ií]nio\s+passo\s+a\s+passo'
            r'|pense\s+passo\s+a\s+passo\s+e\s+(escreva|mostre)|show\s+(your|the)\s+(reasoning|thinking|work)'
            r'|think\s+step[- ]by[- ]step|chain[- ]of[- ]thought|explain\s+your\s+reasoning',
         motivo='Pedir o raciocínio no texto da resposta pode disparar a recusa "reasoning_extraction" do Fable 5.2 e a skill para de funcionar.',
         sugestao='Apague o pedido. Peça o resultado e um resumo do porquê. Para ver o raciocínio, use o resumo de pensamento (display "summarized").'),
    dict(cod='pense-menos', ponto=8, sev='media', em='ambos',
         re=r'sem\s+(pensar|deliberar|raciocinar)|n[ãa]o\s+pense|pense\s+menos|responda\s+(r[áa]pido|direto)\s+sem'
            r'|without\s+deliberat|think\s+less|don\'?t\s+think|answer\s+directly\s+without',
         motivo='No Fable 5.2 a linha "responda sem pensar" não reduz o pensamento a partir do esforço medium.',
         sugestao='Apague a linha e baixe o esforço (low para tarefa rápida).'),
    dict(cod='orcamento-tokens', ponto=8, sev='media', em='ambos',
         re=r'(no\s+m[áa]ximo|at[ée]|limite\s+de|or[çc]amento\s+de|budget\s+de|use\s+only|you\s+have)\s+\d[\d.,]*\s*(k|mil)?\s*tokens'
            r'|tokens?\s+(restantes|left|remaining)',
         motivo='Orçamento de tokens escrito no prompt muda quanto o Fable 5.2 gasta; nos testes da Anthropic, tirar um orçamento grande baixou o custo com o mesmo resultado.',
         sugestao='Teste a tarefa sem o orçamento no texto. (Não vale para o recurso "task budgets" da API.)'),
    dict(cod='resposta-encerrada', ponto=8, sev='media', em='ambos',
         re=r'trate\s+a\s+resposta\s+anterior\s+como|n[ãa]o\s+(revise|reveja|reexamine)\s+(as\s+)?respostas?\s+anteriores'
            r'|treat\s+(that|the\s+previous|the\s+earlier|earlier)\s+answer\s+as\s+(done|final)|focus\s+your\s+thinking\s+on\s+the\s+new\s+message',
         motivo='Com essas linhas o Fable 5.2 pensa menos nas perguntas seguintes, mas quase para de apontar os próprios erros.',
         sugestao='Tire onde você quer que ele revise o que já respondeu; nos outros lugares, teste antes de manter.'),
    dict(cod='estilo-rigido', ponto=8, sev='media', em='ambos',
         re=r'(no\s+m[áa]ximo|at[ée]|≤)\s*\d+\s+palavras\s+por\s+(frase|resposta|mensagem)|\d+\s+words\s+or\s+fewer|responda\s+telegr[áa]fic|terse\s+like\s+caveman'
            r'|use\s+fragments|em\s+fragmentos|uma\s+instru[çc][ãa]o\s+por\s+frase|one\s+instruction\s+per\s+sentence',
         motivo='O Fable 5.2 segue regra de estilo ao pé da letra; limite duro de palavras ou "telegráfico" deixa o texto picotado.',
         sugestao='Apague a regra e, se quiser, cole blocos/relatorio-claro.md.'),
    dict(cod='delegar-sempre', ponto=6, sev='media', em='inst',
         re=r'\b(sempre|always)\b[^.\n]{0,15}\b(use|usar|spawn|dispatch|deploy|lance|dispare|delegue|launch)\w*\b[^.\n]{0,20}\b(sub-?agent\w*|subagente\w*|agentes?)\b'
            r'|\b(deploy|spawn|dispatch|use|lance|dispare)\w*\s+(fresh\s+|new\s+|novos\s+|v[áa]rios\s+|multiple\s+|many\s+)?(sub-?agent\w*|subagente\w*)\b[^.\n]{0,40}\b(all|todo|toda|tudo|every|cada|each)\b'
            r'|\bdelegue\s+(tudo|sempre)|delegate\s+(everything|always)|agent\s+army|ex[ée]rcito\s+de\s+agentes',
         motivo='Ordem fixa de delegar faz o Fable 5.2 abrir mais subagentes do que a tarefa precisa (cada um custa uma sessão).',
         sugestao='Troque "sempre" por quando vale: tarefas independentes que rodam em paralelo. Diga o custo antes do motivo.'),
    dict(cod='obrigacao-absoluta', ponto=7, sev='media', em='ambos',
         re=r'\b1\s?%\s+(de\s+)?chance|YOU\s+DO\s+NOT\s+HAVE\s+A\s+CHOICE|ABSOLUTELY\s+MUST|not\s+negotiable|n[ãa]o\s+[ée]\s+negoci[áa]vel'
            r'|SEM\s+EXCE[ÇC][ÃA]O',
         motivo='Ordem absoluta em caixa alta, sem alcance, é seguida à risca pelo Fable 5.2 e trava trabalho de rotina.',
         sugestao='Reescreva dizendo quando a regra vale e por quê. Se vier de plugin, anote no CLAUDE.md global que ela não vale.'),
    dict(cod='nunca-repetir', ponto=7, sev='media', em='ambos',
         re=r'(nunca|never|n[ãa]o)\s+(tente\s+de\s+novo|tentar\s+de\s+novo|retry|re-?tente|repita\s+a\s+(chamada|tentativa|requisi[çc][ãa]o|comando))|pare\s+no\s+primeiro\s+erro|stop\s+at\s+the\s+first\s+error',
         motivo='Nos testes da Anthropic, uma nota "nunca repita" entre outras doze fez o modelo deixar de tentar de novo quando a ferramenta estava ocupada.',
         sugestao='Diga quais chamadas são seguras para repetir e liste a nova tentativa entre os passos que NÃO precisam de aprovação.'),
    dict(cod='aprovacao-ampla', ponto=3, sev='media', em='inst',
         re=r'(pe[çc]a|pedir|precisa\s+de|exige|ask\s+for|requires?)\s+(sua\s+)?(aprova[çc][ãa]o|autoriza[çc][ãa]o|confirma[çc][ãa]o|permission|approval)'
            r'\s+(antes\s+de|para|before)\s+(qualquer|toda|todo|tudo|any|every|anything)',
         motivo='O Fable 5.2 aplica a regra de aprovação como está escrita; regra que cobre "qualquer coisa" segura metade do trabalho de rotina.',
         sugestao='Nomeie as ações exatas que precisam de aprovação (ex.: apagar, publicar, gastar crédito) e as que não precisam.'),
    dict(cod='continue-vago', ponto=3, sev='baixa', em='script',
         re=r'claude\b[^\n]*\s-p\s+["\'](continue|continua|continuar|vai|segue|go|ok|sim|yes)["\']',
         motivo='"Continue" sem dizer o quê deixa o Fable 5.2 sem saber o que foi aprovado.',
         sugestao='Diga a ação: "sim, rode a migração no banco de teste".'),
    dict(cod='dono-do-codigo', ponto=4, sev='info', em='inst',
         re=r'o\s+c[óo]digo\s+[ée]\s+(seu|teu)|voc[êe]\s+[ée]\s+o\s+dono\s+do\s+c[óo]digo|this\s+codebase\s+is\s+yours|the\s+code\s+is\s+yours|you\s+own\s+(this|the)\s+code',
         motivo='Com essa frase o Fable 5.2 reorganiza o código, gasta ~1,5x mais e muda coisa que ninguém pediu (1 em 6 a 10 tentativas).',
         sugestao='Mantenha só onde você quer reorganização, e revise o diff inteiro, não só o resumo. Para mudança mínima, tire.'),
    dict(cod='esforco-max-fixo', ponto=1, sev='media', em='ambos',
         re=r'--effort[= ]max\b|^\s*effort:\s*max\b|"effortLevel"\s*:\s*"max"',
         motivo='"max" serve para medir o teto do modelo; como padrão gasta muito mais tempo e tokens.',
         sugestao='Use high como padrão; xhigh/max só onde você mediu ganho.'),
]
for r in REGRAS:
    r['rx'] = re.compile(r['re'], re.I | re.M)

# P7 — "nunca" sem motivo
RX_NUNCA = re.compile(r'\b(nunca|jamais|proibido|never)\b', re.I)
RX_MOTIVO = re.compile(r'porque|pois\b|motivo|\bwhy\b|because|para\s+n[ãa]o|para\s+evitar|sen[ãa]o\b|caso\s+contr[áa]rio|risco|'
                       r'\b\d{1,2}/\d{1,2}(/\d{2,4})?\b|\b20\d\d-\d\d|\(.{6,}\)|exceto|exce[çc][ãa]o|unless|except', re.I)
RX_PROTEGIDA = re.compile(r'\bAPI\b|cr[ée]dito|credencia|chave|senha|secret|token\s+de|irrevers|exclu|apag|delet|rm\s+-rf|--force|'
                          r'pagamento|pago\b|dinheiro|seguran|security|publica|push|produ[çc][ãa]o|e-?mail', re.I)

# P2 / P5 / P9 — blocos que deveriam existir em algum arquivo de instrução global
AUSENCIAS = [
    dict(cod='sem-bloco-terminar', ponto=2, bloco='blocos/terminar-tarefa.md',
         re=r'n[ãa]o\s+pare|evite\s+parar|avoid\s+stopping|finishing\s+work|termin(e|ar)\s+a\s+tarefa|at[ée]\s+o\s+fim|carry\s+on',
         motivo='Em tarefas longas o Fable 5.2 às vezes encerra o turno antes do fim (mais em low/medium). A Anthropic dá um texto que separa obstáculo comum de bloqueio de verdade.',
         sugestao='Se você vê paradas no meio, cole blocos/terminar-tarefa.md no CLAUDE.md global. Custo medido: +~30% de tokens de saída.'),
    dict(cod='sem-aviso-progresso', ponto=5, bloco='blocos/avisar-progresso.md',
         re=r'diga\s+em\s+uma\s+linha|say\s+in\s+a\s+line|antes\s+da\s+primeira\s+ferramenta|before\s+your\s+first\s+tool|atualiza[çc][õo]es\s+breves|brief\s+updates',
         motivo='O Fable 5.2 trabalha calado em sequências longas de ferramentas e às vezes age sem dizer o que vai fazer.',
         sugestao='Onde uma pessoa acompanha ao vivo, cole blocos/avisar-progresso.md. Custo medido: +~20% de tokens de saída.'),
    dict(cod='sem-relatorio-claro', ponto=9, bloco='blocos/relatorio-claro.md',
         re=r'leitor\s+sem\s+contexto|pouco\s+contexto|comunicar\s+com\s+clareza|low-context\s+reader|communicating\s+clearly'
            r'|mais\s+importante\s+primeiro|key\s+points\s+in\s+the\s+first',
         motivo='Quem lê o relatório final não viu as ferramentas nem os arquivos; sem instrução, o resumo sai cheio de termo inventado.',
         sugestao='Cole blocos/relatorio-claro.md (antes, tire regras rígidas de estilo).'),
]
for a in AUSENCIAS:
    a['rx'] = re.compile(a['re'], re.I)

RX_FRONT = re.compile(r'^---\s*\n(.*?)\n---', re.S)


def ler(p):
    try:
        if p.stat().st_size > MAX_BYTES:
            return None
        return p.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None


def citado(txt, pos):
    """True se a posição está entre aspas na mesma linha (é exemplo citado, não ordem)."""
    ini = txt.rfind('\n', 0, pos) + 1
    antes = txt[ini:pos]
    return antes.count('“') > antes.count('”') or antes.count('"') % 2 == 1 or antes.count('«') > antes.count('»')


def frontmatter(txt):
    m = RX_FRONT.match(txt or '')
    out = {}
    if not m:
        return out
    chave = None
    for ln in m.group(1).splitlines():
        mm = re.match(r'^([A-Za-z_-]+):\s*(.*)$', ln)
        if mm:
            chave = mm.group(1)
            out[chave] = mm.group(2).strip().strip('"\'')
        elif chave and ln.startswith((' ', '\t')):
            out[chave] = (out[chave] + ' ' + ln.strip()).strip()
    return out


def tipo_arquivo(p):
    if p.name in NOMES_INSTRUCAO:
        return 'inst'
    partes = set(p.parts)
    if p.suffix == '.md' and (partes & DIRS_INSTRUCAO or '.claude' in partes):
        return 'inst'
    if p.suffix in EXT_SCRIPT:
        return 'script'
    return None


def eh_terceiro(p):
    s = str(p)
    return '/.claude/plugins/' in s or '/plugins/cache/' in s or '/plugins/marketplaces/' in s


def andar(raiz, fundo):
    raiz = Path(raiz).expanduser()
    if raiz.is_file():
        yield raiz
        return
    base = len(raiz.parts)
    n = 0
    for d, subs, arqs in os.walk(raiz):
        dp = Path(d)
        if len(dp.parts) - base >= fundo:
            subs[:] = []
        subs[:] = [s for s in subs if s not in IGNORAR_DIR and s not in ('tests', 'test', 'plugins')
                   and not s.startswith('temp_git') and not (s.startswith('.') and s not in ('.claude',))]
        for a in arqs:
            p = dp / a
            if tipo_arquivo(p):
                n += 1
                if n > MAX_ARQ:
                    return
                yield p


def alvos_home():
    c = Path(HOME) / '.claude'
    out = []
    for p in [c / 'CLAUDE.md', c / 'CLAUDE.local.md']:
        if p.exists():
            out.append(p)
    for sub, padrao in [('agents', '*.md'), ('commands', '**/*.md'), ('skills', '*/SKILL.md'),
                        ('projects', '*/memory/*.md')]:
        out += [p for p in (c / sub).glob(padrao) if p.is_file()]
    return out + plugins_instalados(c / 'plugins' / 'cache')


def plugins_instalados(cache):
    """Só a versão mais nova de cada plugin instalado (cache/<loja>/<plugin>/<versão>); marketplaces e temp_git ficam fora."""
    out = []
    if not cache.is_dir():
        return out
    for loja in cache.iterdir():
        if not loja.is_dir() or loja.name.startswith('temp_git'):
            continue
        for plug in loja.iterdir():
            if not plug.is_dir():
                continue
            versoes = [v for v in plug.iterdir() if v.is_dir()]
            if not versoes:
                continue
            v = max(versoes, key=lambda x: x.stat().st_mtime)
            out += [p for p in v.glob('skills/*/SKILL.md')]
            out += [p for p in v.glob('hooks/*') if p.is_file() and p.suffix in EXT_SCRIPT | {'.md', '.json'}]
            out += [p for p in v.glob('agents/*.md')]
    return out


def settings_arqs(raizes, home):
    out = []
    for r in raizes:
        r = Path(r).expanduser()
        if r.is_dir():
            out += list((r / '.claude').glob('settings*.json'))
    if home:
        out += list((Path(HOME) / '.claude').glob('settings*.json'))
    vistos, final = set(), []
    for p in out:
        if p.resolve() not in vistos:
            vistos.add(p.resolve())
            final.append(p)
    return final


class Auditoria:
    def __init__(self, anonimo=False):
        self.achados = []
        self.anonimo = anonimo
        self.arquivos = 0
        self.contexto = {}       # fonte -> tokens estimados
        self.skills = []         # dicts nome, desc, arq
        self.textos_inst = []    # (arquivo, texto) dos globais/raiz para as ausências
        self._vistos = set()

    def nome(self, p):
        s = str(p)
        return s.replace(HOME, '~', 1) if self.anonimo and s.startswith(HOME) else s

    def add(self, camada, cod, ponto, sev, arq, linha, trecho, motivo, sugestao, protegida=False, terceiro=False):
        chave = (cod, str(arq), linha)
        if linha and chave in self._vistos:
            return
        self._vistos.add(chave)
        self.achados.append(dict(camada=camada, regra=cod, ponto=ponto, ponto_nome=PONTOS.get(ponto, 'Volume'),
                                 sev=sev, arquivo=self.nome(arq), linha=linha, trecho=(trecho or '').strip()[:220],
                                 motivo=motivo, sugestao=sugestao, protegida=protegida, terceiro=terceiro))

    # ---------------- camada fable52: linha a linha
    def varrer_arquivo(self, p):
        tipo = tipo_arquivo(p) or ('inst' if p.suffix == '.md' else 'script')
        txt = ler(p)
        if txt is None:
            return
        self.arquivos += 1
        terceiro = eh_terceiro(p)
        linhas = txt.splitlines()
        if p.name == 'SKILL.md' or (p.suffix == '.md' and 'agents' in p.parts):
            fm = frontmatter(txt)
            if p.name == 'SKILL.md':
                self.skills.append(dict(nome=fm.get('name') or p.parent.name, desc=fm.get('description', ''),
                                        arq=self.nome(p), terceiro=terceiro))
        for r in REGRAS:
            if r['em'] != 'ambos' and r['em'] != tipo:
                continue
            for m in r['rx'].finditer(txt):
                ln = txt.count('\n', 0, m.start()) + 1
                linha_txt = linhas[ln - 1] if ln - 1 < len(linhas) else m.group(0)
                if tipo == 'script' and re.match(r'\s*(#|//|echo\b|log\b|print)', linha_txt):
                    continue
                if tipo == 'inst' and citado(txt, m.start()):  # em script o prompt fica entre aspas: conta
                    continue
                sug = r['sugestao']
                if terceiro:
                    sug += ' Arquivo de plugin: não edite (volta na atualização); anote no CLAUDE.md global.'
                self.add('fable52', r['cod'], r['ponto'], r['sev'], p, ln, linha_txt, r['motivo'], sug, terceiro=terceiro)
        if tipo == 'inst':
            self.nunca_sem_motivo(p, linhas, terceiro)

    def nunca_sem_motivo(self, p, linhas, terceiro):
        dentro_codigo = False
        for i, ln in enumerate(linhas):
            if ln.strip().startswith('```'):
                dentro_codigo = not dentro_codigo
                continue
            if dentro_codigo or not RX_NUNCA.search(ln):
                continue
            viz = ln + ' ' + (linhas[i + 1] if i + 1 < len(linhas) else '')
            if RX_MOTIVO.search(viz):
                continue
            protegida = bool(RX_PROTEGIDA.search(ln))
            if protegida:
                sev, sug = 'info', 'Regra de segurança: mantenha. Só acrescente o alcance (quando vale) e o motivo.'
            else:
                sev, sug = 'baixa', ('Veja se o motivo ainda vale. Se vale, escreva o motivo e quando a regra se aplica; '
                                     'se não vale mais, apague.')
            if terceiro:
                sug += ' Arquivo de plugin: não edite; anote no CLAUDE.md global.'
            self.add('fable52', 'nunca-sem-motivo', 7, sev, p, i + 1, ln,
                     'Regra absoluta sem motivo nem alcance. O Fable 5.2 segue à risca e pode segurar trabalho de rotina.',
                     sug, protegida=protegida, terceiro=terceiro)

    # ---------------- camada fable52: esforço nos settings
    def varrer_settings(self, p):
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError):
            return
        txt = p.read_text()

        def linha_de(chave, valor=None):
            pad = f'"{chave}"' + (rf'\s*:\s*"{valor}"' if valor else '')
            m = re.search(pad, txt)
            return txt.count('\n', 0, m.start()) + 1 if m else 0

        ef = d.get('effortLevel')
        if ef in ('xhigh', 'max'):
            self.add('fable52', 'esforco-padrao-alto', 1, 'alta' if ef == 'max' else 'media', p, linha_de('effortLevel', ef),
                     f'"effortLevel": "{ef}"', f'Esforço {ef} como padrão global gasta muito sem ganho medido.',
                     'Use high como padrão; suba só nas tarefas onde você mediu ganho.')
        for mod, cfg in (d.get('modelSettings') or {}).items():
            e = (cfg or {}).get('effortLevel')
            ln = linha_de(mod)
            if re.search(r'fable-5-2|fable-5\.2', mod) and e in ('low', 'medium'):
                self.add('fable52', 'fable52-esforco-baixo', 1, 'baixa', p, ln, f'"{mod}": effortLevel "{e}"',
                         'No Fable 5.2 a parada antes do fim é mais comum em low e medium (Anthropic).',
                         'Mantenha medium no dia a dia, mas rode as tarefas longas em high (/effort high ou --effort high).')
            elif re.search(r'fable-5(-1)?$|fable-5-1|opus-4', mod):
                self.add('fable52', 'esforco-modelo-antigo', 1, 'info', p, ln, f'"{mod}": effortLevel "{e}"',
                         'Ajuste feito para um modelo anterior. O mesmo nome de esforço pensa diferente em cada modelo.',
                         'Não copie para o 5.2: refaça o teste de esforço (ab.sh do kit esforco-certo).')
            if e in ('xhigh', 'max') and re.search(r'fable-5-2', mod):
                self.add('fable52', 'esforco-padrao-alto', 1, 'media', p, ln, f'"{mod}": effortLevel "{e}"',
                         f'{e} no Fable 5.2: nos testes internos subiu pouco a nota e gastou muito mais.',
                         'Comece em high e suba só onde mediu ganho.')
        hooks = d.get('hooks') or {}
        nh = sum(len(v) if isinstance(v, list) else 1 for v in hooks.values())
        plug = [k for k, v in (d.get('enabledPlugins') or {}).items() if v]
        if nh or plug:
            self.add('volume', 'hooks-e-plugins', 0, 'info', p, linha_de('hooks') or linha_de('enabledPlugins'),
                     f'{nh} grupos de hook; plugins ligados: {", ".join(plug) or "nenhum"}',
                     'Hooks e plugins injetam texto em toda sessão. É lá que costuma morar regra rígida de estilo ou ordem absoluta.',
                     'Liste o que cada hook escreve no início da sessão; desligue o que não usa.')

    # ---------------- camada volume
    def volume(self, raizes, home, uso_dias):
        fontes = []
        for r in raizes:
            r = Path(r).expanduser()
            for n in ('CLAUDE.md', 'AGENTS.md', 'CLAUDE.local.md'):
                if (r / n).is_file():
                    fontes.append((f'{n} da pasta', r / n))
        if home:
            c = Path(HOME) / '.claude'
            if (c / 'CLAUDE.md').is_file():
                fontes.append(('CLAUDE.md global', c / 'CLAUDE.md'))
            for r in raizes:  # só o índice do projeto aberto entra na sessão
                slug = re.sub(r'[^A-Za-z0-9]', '-', str(Path(r).expanduser().resolve()))
                m = c / 'projects' / slug / 'memory' / 'MEMORY.md'
                if m.is_file():
                    fontes.append(('MEMORY.md do projeto', m))
        for rot, p in fontes:
            t = ler(p) or ''
            self.contexto[rot] = self.contexto.get(rot, 0) + len(t) // 4
            nl = t.count('\n') + 1
            self.textos_inst.append((p, t))
            if p.name == 'MEMORY.md' and nl > 150:
                self.add('volume', 'indice-memoria-longo', 0, 'baixa', p, 1, f'{nl} linhas',
                         'Cada linha do índice de memória entra em toda sessão. Índice longo carrega nota velha junto.',
                         'Mova projetos encerrados para um arquivo à parte e deixe no índice só o que está vivo.')
            elif p.name != 'MEMORY.md' and nl > 200:
                self.add('volume', 'instrucao-longa', 0, 'baixa', p, 1, f'{nl} linhas (~{len(t)//4} tokens)',
                         'Instrução longa entra inteira em toda sessão; é onde cautelas antigas se acumulam.',
                         'Passe o que é de um tema só para um runbook lido sob demanda.')
        # skills: descrições entram em toda sessão
        tot = sum(len(s['desc']) for s in self.skills) // 4
        if self.skills:
            self.contexto['descrições de skills'] = tot
            nprop = sum(1 for s in self.skills if not s['terceiro'])
            if len(self.skills) > 60:
                self.add('volume', 'muitas-skills', 0, 'info', Path(HOME) / '.claude' / 'skills', 0,
                         f'{len(self.skills)} skills ({nprop} suas, {len(self.skills)-nprop} de plugins), ~{tot} tokens de descrição',
                         'As descrições de todas as skills entram em toda sessão e competem pelo mesmo gatilho.',
                         'Rode com --uso 30 para ver as que não usa; arquive as paradas.')
        # duplicadas (mesmo nome ou descrição parecida)
        por_nome = {}
        for s in self.skills:
            por_nome.setdefault(s['nome'].split(':')[-1].lower(), []).append(s)
        for nome, lst in por_nome.items():
            if len(lst) > 1:
                self.add('volume', 'skill-repetida', 0, 'baixa', lst[0]['arq'], 0,
                         f'"{nome}" em {len(lst)} lugares: ' + '; '.join(x['arq'] for x in lst[:4]),
                         'A mesma skill em dois lugares carrega duas descrições e o modelo pode escolher a errada.',
                         'Fique com uma cópia.')
        def pal(t):
            return {w for w in re.findall(r'[a-zà-ú]{4,}', t.lower())}
        ss = [s for s in self.skills if len(s['desc']) > 60]
        for i in range(len(ss)):
            for j in range(i + 1, len(ss)):
                a, b = pal(ss[i]['desc']), pal(ss[j]['desc'])
                if a and b and ss[i]['nome'] != ss[j]['nome'] and len(a & b) / len(a | b) >= 0.6:
                    self.add('volume', 'skill-parecida', 0, 'info', ss[i]['arq'], 0,
                             f'"{ss[i]["nome"]}" ≈ "{ss[j]["nome"]}"',
                             'Duas descrições quase iguais disputam o mesmo pedido.',
                             'Junte as duas ou deixe claro na descrição quando usar cada uma.')
        # memórias velhas
        if home:
            hoje = time.time()
            for d in (Path(HOME) / '.claude').glob('projects/*/memory'):
                velhas = []
                for m in d.glob('*.md'):
                    if m.name != 'MEMORY.md' and (hoje - m.stat().st_mtime) / 86400 > 60:
                        velhas.append(m.name)
                if velhas:
                    self.add('volume', 'memoria-velha', 7, 'info' if len(velhas) < 20 else 'baixa', d, 0,
                             f'{len(velhas)} notas sem mudança há mais de 60 dias: ' + ', '.join(sorted(velhas)[:6])
                             + (' …' if len(velhas) > 6 else ''),
                             'Nota antiga pode carregar cautela cujo motivo já passou; o Fable 5.2 obedece.',
                             'Releia as notas; apague as que perderam o motivo (guarde cópia antes).')
        if uso_dias:
            self.uso_skills(uso_dias)

    def uso_skills(self, dias):
        lim = time.time() - dias * 86400
        usadas = {}
        for j in (Path(HOME) / '.claude' / 'projects').glob('*/*.jsonl'):
            try:
                if j.stat().st_mtime < lim:
                    continue
                with open(j, encoding='utf-8', errors='replace') as f:
                    for ln in f:
                        if '"Skill"' not in ln and '<command-name>' not in ln:
                            continue
                        for n in re.findall(r'"skill"\s*:\s*"([^"]+)"', ln) + re.findall(r'<command-name>/?([^<]+)</command-name>', ln):
                            k = n.split(':')[-1].lower()
                            usadas[k] = usadas.get(k, 0) + 1
            except OSError:
                continue
        for s in self.skills:
            if s['terceiro']:
                continue
            if usadas.get(s['nome'].split(':')[-1].lower(), 0) == 0:
                self.add('volume', 'skill-sem-uso', 0, 'baixa', s['arq'], 0, f'"{s["nome"]}": 0 usos em {dias} dias',
                         'Skill parada ainda carrega a descrição em toda sessão.',
                         'Arquive (mova para fora de ~/.claude/skills) se não for usar.')

    def ausencias(self):
        if not self.textos_inst:
            return
        junto = '\n'.join(t for _, t in self.textos_inst)
        alvo = self.textos_inst[0][0]
        for a in AUSENCIAS:
            if not a['rx'].search(junto):
                self.add('fable52', a['cod'], a['ponto'], 'info', alvo, 0, f'nenhum texto do tipo "{a["bloco"]}"',
                         a['motivo'], a['sugestao'])

    def finalizar(self):
        ordem = {s: i for i, s in enumerate(SEVS)}
        self.achados.sort(key=lambda a: (a['camada'] != 'fable52', ordem[a['sev']], a['ponto'] or 99, a['arquivo'], a['linha']))
        for i, a in enumerate(self.achados, 1):
            a['id'] = f'A{i:03d}'

    def resumo(self):
        por_ponto, por_sev, por_arq = {}, {}, {}
        for a in self.achados:
            k = f"P{a['ponto']} {a['ponto_nome']}" if a['camada'] == 'fable52' else 'Volume'
            por_ponto[k] = por_ponto.get(k, 0) + 1
            por_sev[a['sev']] = por_sev.get(a['sev'], 0) + 1
            por_arq[a['arquivo']] = por_arq.get(a['arquivo'], 0) + 1
        return dict(versao=VERSAO, data=date.today().isoformat(), fonte=DOC, arquivos_lidos=self.arquivos,
                    total=len(self.achados), por_ponto=por_ponto, por_sev=por_sev,
                    top_arquivos=sorted(por_arq.items(), key=lambda x: -x[1])[:10],
                    contexto_tokens=self.contexto, skills=len(self.skills))


def rodar(raizes, home=False, anonimo=False, fundo=6, uso=0):
    au = Auditoria(anonimo)
    vistos = set()
    alvos = []
    for r in raizes:
        alvos += list(andar(r, fundo))
    if home:
        alvos += alvos_home()
    for p in alvos:
        try:
            k = p.resolve()
        except OSError:
            continue
        if k in vistos or k.name == 'varrer.py':
            continue
        vistos.add(k)
        au.varrer_arquivo(p)
    for s in settings_arqs(raizes, home):
        au.varrer_settings(s)
    au.volume(raizes, home, uso)
    au.ausencias()
    au.finalizar()
    return au


# ---------------------------------------------------------------- saídas
def texto(au):
    r = au.resumo()
    out = [f'audite-seu-claude {VERSAO} — {r["arquivos_lidos"]} arquivos lidos, {r["total"]} achados', '']
    out.append('Por ponto: ' + ', '.join(f'{k}={v}' for k, v in sorted(r['por_ponto'].items())))
    out.append('Por severidade: ' + ', '.join(f'{s}={r["por_sev"].get(s, 0)}' for s in SEVS))
    if r['contexto_tokens']:
        out.append('Contexto fixo (tokens estimados): ' + ', '.join(f'{k}≈{v}' for k, v in r['contexto_tokens'].items()))
    out.append('')
    resto = {}
    for a in au.achados:
        if a['sev'] in ('baixa', 'info') and a['regra'] in ('nunca-sem-motivo', 'skill-sem-uso', 'skill-repetida', 'skill-parecida'):
            resto[a['regra']] = resto.get(a['regra'], 0) + 1
            continue
        loc = f"{a['arquivo']}:{a['linha']}" if a['linha'] else a['arquivo']
        tag = ' [protegida]' if a['protegida'] else (' [plugin]' if a['terceiro'] else '')
        out.append(f"{a['id']} [{a['sev']}] P{a['ponto'] or '-'} {a['regra']}{tag} — {loc}")
        out.append(f"     {a['trecho'][:140]}")
        out.append(f"     → {a['sugestao']}")
    out.append('')
    if resto:
        out.append('Mais (lista completa no --html / --saida-json): ' + ', '.join(f'{k}={v}' for k, v in resto.items()))
    return '\n'.join(out)


CABECALHO_CORRECOES = """# Correções aprovadas — audite-seu-claude

Para o Claude: estas são as correções que eu aprovei depois de ler o relatório do audite-seu-claude
({data}). Aplique os itens abaixo, um por vez, nesta ordem.

1. Antes de mudar um arquivo, copie o original para `.audite-backup/{data}/` mantendo o caminho.
2. Mude só a linha indicada (ou o trecho dela). Não reescreva o resto do arquivo.
3. Item marcado PROTEGIDA: não apague a regra. Só acrescente quando ela vale e por quê.
4. Item marcado PLUGIN: não edite o arquivo do plugin. Escreva no CLAUDE.md global uma linha dizendo que aquela
   regra não vale aqui.
5. Item de "bloco ausente": cole o texto do arquivo indicado em `blocos/` no fim do CLAUDE.md global.
6. Depois de cada item, diga em uma linha o que mudou. No fim, liste o que ficou sem aplicar e por quê.

Esta lista vale como aprovação só para estas edições de texto, nestes arquivos. Qualquer outra mudança, pergunte.
"""


def correcoes(dados, ids, data=None):
    data = data or date.today().isoformat()
    sel = [a for a in dados['achados'] if a['id'] in ids]
    falt = sorted(set(ids) - {a['id'] for a in sel})
    out = [CABECALHO_CORRECOES.format(data=data)]
    for a in sel:
        tag = ' · PROTEGIDA' if a.get('protegida') else (' · PLUGIN' if a.get('terceiro') else '')
        loc = f"`{a['arquivo']}` linha {a['linha']}" if a['linha'] else f"`{a['arquivo']}`"
        out.append(f"## {a['id']} — P{a['ponto'] or '-'} {a['ponto_nome']} ({a['regra']}){tag}\n")
        out.append(f"- Onde: {loc}")
        out.append(f"- Trecho: `{a['trecho'].replace('`', '')}`")
        out.append(f"- Por quê: {a['motivo']}")
        out.append(f"- O que fazer: {a['sugestao']}\n")
    if falt:
        out.append(f"IDs não encontrados no relatório (ignorar): {', '.join(falt)}\n")
    return '\n'.join(out)


def svg_barras(itens, largura=560, cor='var(--amb)', rotulo_larg=190):
    if not itens:
        return '<p class="mut">Nada para mostrar.</p>'
    mx = max(v for _, v in itens) or 1
    alt = 26 * len(itens) + 8
    barra_max = largura - rotulo_larg - 60
    linhas = []
    for i, (k, v) in enumerate(itens):
        y = 8 + i * 26
        w = max(2, int(barra_max * v / mx))
        kk = html.escape(k if len(k) <= 30 else '…' + k[-29:])
        linhas.append(f'<text x="{rotulo_larg-8}" y="{y+14}" text-anchor="end" class="rot">{kk}</text>'
                      f'<rect x="{rotulo_larg}" y="{y}" width="{w}" height="18" rx="4" fill="{cor}"/>'
                      f'<text x="{rotulo_larg+w+6}" y="{y+14}" class="val">{v}</text>')
    return (f'<svg viewBox="0 0 {largura} {alt}" role="img" class="grafico" preserveAspectRatio="xMinYMin meet">'
            + ''.join(linhas) + '</svg>')


def relatorio_html(au):
    r = au.resumo()
    pontos = sorted(r['por_ponto'].items(), key=lambda x: (x[0] == 'Volume', int(re.sub(r'\D', '', x[0].split()[0]) or 99)))
    sev = [(s, r['por_sev'].get(s, 0)) for s in SEVS]
    ctx = sorted(r['contexto_tokens'].items(), key=lambda x: -x[1])
    dados = json.dumps(dict(resumo=r, achados=au.achados), ensure_ascii=False).replace('</', '<\\/')
    linhas = []
    for a in au.achados:
        loc = f"{a['arquivo']}:{a['linha']}" if a['linha'] else a['arquivo']
        tag = '<span class="tag pro">protegida</span>' if a['protegida'] else ('<span class="tag plug">plugin</span>' if a['terceiro'] else '')
        linhas.append(
            f'<tr data-sev="{a["sev"]}" data-cam="{a["camada"]}"><td><input type="checkbox" value="{a["id"]}" '
            f'{"" if a["protegida"] or a["sev"] == "info" else ""}></td><td class="id">{a["id"]}</td>'
            f'<td><span class="sev {a["sev"]}">{a["sev"]}</span></td>'
            f'<td>{"P"+str(a["ponto"]) if a["ponto"] else "Vol"} {html.escape(a["ponto_nome"])}</td>'
            f'<td><code>{html.escape(loc)}</code> {tag}<div class="tre">{html.escape(a["trecho"])}</div>'
            f'<div class="mot">{html.escape(a["motivo"])}</div><div class="sug">→ {html.escape(a["sugestao"])}</div></td></tr>')
    alta = r['por_sev'].get('alta', 0)
    media = r['por_sev'].get('media', 0)
    tokens = sum(r['contexto_tokens'].values())
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Relatório Fable 5.2</title>
<style>
:root{{--bg:#0c0c10;--card:#16161e;--line:#272730;--txt:#e9e9ee;--mut:#9a9aa6;--amb:#FACC15;--sky:#38bdf8;--red:#E0736F;--warm:#F2B45C}}
@media (prefers-color-scheme: light){{:root{{--bg:#f6f7f9;--card:#fff;--line:#e1e3ea;--txt:#1a1a22;--mut:#5b5b68;--amb:#a16207;--sky:#0369a1;--red:#b42318;--warm:#b45309}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--txt);font:15px/1.55 Inter,system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 64px}}h1,h2{{font-family:Sora,Inter,system-ui,sans-serif;line-height:1.2}}
h1{{font-size:28px;margin:0 0 4px}}h1 b{{color:var(--amb)}}.mut{{color:var(--mut)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:20px 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}}.card b{{font:700 26px Sora,Inter,sans-serif;display:block}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,480px),1fr));gap:16px}}
.grafico{{width:100%;height:auto}}.rot{{fill:var(--mut);font-size:12px}}.val{{fill:var(--txt);font-size:12px;font-weight:600}}
table{{width:100%;border-collapse:collapse;margin-top:12px}}td{{border-top:1px solid var(--line);padding:10px 6px;vertical-align:top}}
td.id{{font-family:'JetBrains Mono',monospace;white-space:nowrap}}code{{font-size:12px;word-break:break-all}}
.tre{{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--mut);margin:4px 0;word-break:break-word}}.mot{{font-size:13px}}.sug{{font-size:13px;color:var(--amb)}}
.sev{{font-size:11px;padding:2px 8px;border-radius:99px;border:1px solid var(--line)}}.sev.alta{{color:var(--red)}}.sev.media{{color:var(--warm)}}
.tag{{font-size:11px;padding:1px 6px;border-radius:6px;border:1px solid var(--line);color:var(--sky)}}
.barra{{position:sticky;top:0;background:var(--bg);padding:10px 0;display:flex;gap:8px;flex-wrap:wrap;align-items:center;border-bottom:1px solid var(--line);z-index:2}}
button,select{{font:600 14px Sora,Inter,sans-serif;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--txt);padding:8px 12px;cursor:pointer}}
button.pri{{background:var(--amb);color:#1a1206;border:0}}textarea{{width:100%;min-height:220px;background:var(--card);color:var(--txt);border:1px solid var(--line);border-radius:10px;font:12px 'JetBrains Mono',monospace;padding:10px;display:none;margin-top:10px}}
@media (max-width:640px){{td:nth-child(4){{display:none}}}}
</style></head><body><main>
<h1>Seu Claude está pronto para o <b>Fable 5.2</b>?</h1>
<p class="mut">audite-seu-claude {VERSAO} · {r['data']} · {r['arquivos_lidos']} arquivos lidos · regras da página oficial da Anthropic (<a style="color:var(--sky)" href="{DOC}">Prompting Claude Fable 5.2</a>). Só leitura: nada foi mudado.</p>
<div class="cards"><div class="card"><b>{r['total']}</b>achados</div><div class="card"><b style="color:var(--red)">{alta}</b>alta (trava ou recusa)</div>
<div class="card"><b style="color:var(--warm)">{media}</b>média</div><div class="card"><b>{r['skills']}</b>skills carregadas</div>
<div class="card"><b>~{format(tokens, ',').replace(',', '.')}</b>tokens fixos por sessão</div></div>
<div class="grid">
<section class="card"><h2>Achados por ponto da Anthropic</h2>{svg_barras(pontos)}</section>
<section class="card"><h2>Por severidade</h2>{svg_barras(sev, cor='var(--sky)', rotulo_larg=90)}</section>
<section class="card"><h2>Arquivos com mais achados</h2>{svg_barras(r['top_arquivos'], rotulo_larg=230)}</section>
<section class="card"><h2>Peso do contexto fixo (tokens estimados)</h2>{svg_barras(ctx, cor='var(--warm)', rotulo_larg=200)}</section>
</div>
<h2>Sugestões</h2>
<p class="mut">Marque o que você aprova e gere o <code>correcoes.md</code>. Depois diga ao seu Claude: <i>"aplique o correcoes.md"</i>. Regras <span class="tag pro">protegida</span> nunca são apagadas, só ganham alcance e motivo.</p>
<div class="barra"><select id="f"><option value="">todas</option><option value="fable52">só Fable 5.2</option><option value="volume">só volume</option>
<option value="alta">só alta</option><option value="media">só média</option></select>
<button id="tudo">marcar visíveis (sem info)</button><button class="pri" id="gerar">gerar correcoes.md</button><span id="n" class="mut"></span></div>
<textarea id="saida" readonly></textarea>
<table><tbody id="t">{''.join(linhas)}</tbody></table>
</main>
<script id="dados" type="application/json">{dados}</script>
<script>
const D=JSON.parse(document.getElementById('dados').textContent);
const CAB={json.dumps(CABECALHO_CORRECOES, ensure_ascii=False)};
const t=document.getElementById('t'),f=document.getElementById('f'),n=document.getElementById('n');
function conta(){{n.textContent=t.querySelectorAll('input:checked').length+' marcadas'}}
t.addEventListener('change',conta);
f.onchange=()=>{{for(const tr of t.rows){{const v=f.value;tr.style.display=(!v||tr.dataset.cam===v||tr.dataset.sev===v)?'':'none'}}}};
document.getElementById('tudo').onclick=()=>{{for(const tr of t.rows){{if(tr.style.display!=='none'&&tr.dataset.sev!=='info')tr.querySelector('input').checked=true}}conta()}};
document.getElementById('gerar').onclick=()=>{{
 const ids=[...t.querySelectorAll('input:checked')].map(i=>i.value);if(!ids.length){{n.textContent='marque ao menos um item';return}}
 const data=D.resumo.data;let s=CAB.replaceAll('{{data}}',data)+'\\n';
 for(const a of D.achados.filter(a=>ids.includes(a.id))){{
  const tag=a.protegida?' · PROTEGIDA':(a.terceiro?' · PLUGIN':'');const loc=a.linha?'`'+a.arquivo+'` linha '+a.linha:'`'+a.arquivo+'`';
  s+=`## ${{a.id}} — P${{a.ponto||'-'}} ${{a.ponto_nome}} (${{a.regra}})${{tag}}\\n\\n- Onde: ${{loc}}\\n- Trecho: \\`${{a.trecho.replaceAll('`','')}}\\`\\n- Por quê: ${{a.motivo}}\\n- O que fazer: ${{a.sugestao}}\\n\\n`}}
 const ta=document.getElementById('saida');ta.style.display='block';ta.value=s;
 try{{const b=new Blob([s],{{type:'text/markdown'}});const l=document.createElement('a');l.href=URL.createObjectURL(b);l.download='correcoes.md';l.click()}}catch(e){{}}
 n.textContent=ids.length+' itens no correcoes.md (baixado; o texto também está abaixo)'}};
</script></body></html>"""


def main(argv=None):
    ap = argparse.ArgumentParser(prog='varrer.py', description='Audita o seu Claude Code para o Fable 5.2 (só leitura).')
    ap.add_argument('pastas', nargs='*')
    ap.add_argument('--home', action='store_true')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--html')
    ap.add_argument('--saida-json')
    ap.add_argument('--uso', type=int, default=0)
    ap.add_argument('--anonimo', action='store_true')
    ap.add_argument('--fundo', type=int, default=6)
    ap.add_argument('--estrito', action='store_true')
    ap.add_argument('--correcoes')
    ap.add_argument('--de')
    ap.add_argument('--saida')
    ap.add_argument('--versao', action='version', version=VERSAO)
    a = ap.parse_args(argv)

    if a.correcoes:
        if not a.de:
            ap.error('--correcoes precisa de --de relatorio.json')
        dados = json.loads(Path(a.de).read_text())
        ids = [x.strip().upper() for x in a.correcoes.split(',') if x.strip()]
        md = correcoes(dados, ids, dados.get('resumo', {}).get('data'))
        if a.saida:
            Path(a.saida).write_text(md)
            print(f'ok: {a.saida} ({len(ids)} itens)')
        else:
            print(md)
        return 0

    pastas = a.pastas or ([] if a.home else ['.'])
    au = rodar(pastas, a.home, a.anonimo, a.fundo, a.uso)
    dados = dict(resumo=au.resumo(), achados=au.achados)
    if a.saida_json:
        Path(a.saida_json).write_text(json.dumps(dados, ensure_ascii=False, indent=1))
    if a.html:
        Path(a.html).write_text(relatorio_html(au))
    if a.json:
        print(json.dumps(dados, ensure_ascii=False, indent=1))
    else:
        print(texto(au))
        if a.html:
            print(f'\nrelatório: {a.html}')
    if a.estrito and dados['resumo']['por_sev'].get('alta'):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
