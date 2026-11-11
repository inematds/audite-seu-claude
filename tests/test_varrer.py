"""Testes sem rede: python3 -m unittest discover tests"""
import io, json, os, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import varrer  # noqa: E402

SUJO = AQUI / 'fixtures' / 'sujo'
LIMPO = AQUI / 'fixtures' / 'limpo'


def regras(au):
    return [a['regra'] for a in au.achados]


class TestSujo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.au = varrer.rodar([str(SUJO)])
        cls.r = regras(cls.au)

    def test_raciocinio_no_texto_e_alta(self):
        a = [x for x in self.au.achados if x['regra'] == 'raciocinio-no-texto']
        self.assertTrue(a)
        self.assertEqual(a[0]['sev'], 'alta')
        self.assertEqual(a[0]['ponto'], 10)
        self.assertTrue(any(x['arquivo'].endswith('roda.sh') for x in a), 'prompt entre aspas em script tem que contar')

    def test_instrucoes_antigas(self):
        for cod in ('pense-menos', 'orcamento-tokens', 'resposta-encerrada', 'estilo-rigido'):
            self.assertIn(cod, self.r, cod)

    def test_subagentes_e_cautela(self):
        for cod in ('delegar-sempre', 'obrigacao-absoluta', 'nunca-repetir', 'aprovacao-ampla', 'dono-do-codigo'):
            self.assertIn(cod, self.r, cod)

    def test_nunca_sem_motivo_e_protegida(self):
        ns = [x for x in self.au.achados if x['regra'] == 'nunca-sem-motivo']
        self.assertTrue(any('docs' in x['trecho'] and not x['protegida'] for x in ns))
        prot = [x for x in ns if 'API' in x['trecho']]
        self.assertTrue(prot and prot[0]['protegida'] and prot[0]['sev'] == 'info')
        self.assertIn('mantenha', prot[0]['sugestao'].lower())

    def test_esforco_nos_settings(self):
        self.assertIn('esforco-padrao-alto', self.r)
        self.assertIn('esforco-modelo-antigo', self.r)
        self.assertIn('fable52-esforco-baixo', self.r)
        alta = [x for x in self.au.achados if x['regra'] == 'esforco-padrao-alto' and x['sev'] == 'alta']
        self.assertTrue(alta, 'effortLevel max global deve ser alta')

    def test_script_continue_e_effort_max(self):
        self.assertIn('continue-vago', self.r)
        cont = [x for x in self.au.achados if x['regra'] == 'continue-vago']
        self.assertEqual(len(cont), 1, 'a linha com echo é citação e não conta')
        self.assertTrue(any(x['regra'] == 'esforco-max-fixo' and x['arquivo'].endswith('roda.sh') for x in self.au.achados))

    def test_ausencias_dos_blocos(self):
        for cod in ('sem-bloco-terminar', 'sem-aviso-progresso', 'sem-relatorio-claro'):
            self.assertIn(cod, self.r)

    def test_volume_skill_repetida_e_hooks(self):
        self.assertIn('skill-repetida', self.r)
        self.assertIn('hooks-e-plugins', self.r)

    def test_ids_unicos_e_ordenados(self):
        ids = [a['id'] for a in self.au.achados]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], 'A001')
        self.assertEqual(self.au.achados[0]['sev'], 'alta')

    def test_sem_duplicata_na_mesma_linha(self):
        chaves = [(a['regra'], a['arquivo'], a['linha']) for a in self.au.achados if a['linha']]
        self.assertEqual(len(chaves), len(set(chaves)))


class TestLimpo(unittest.TestCase):
    def test_zero_achados_fable52(self):
        au = varrer.rodar([str(LIMPO)])
        f = [a for a in au.achados if a['camada'] == 'fable52']
        self.assertEqual(f, [], [(a['regra'], a['trecho']) for a in f])

    def test_citacao_entre_aspas_nao_conta(self):
        self.assertTrue(varrer.citado('ex.: "mostre seu raciocínio', 9))


class TestSaidas(unittest.TestCase):
    def test_nao_muda_nada(self):
        antes = {p: p.stat().st_mtime_ns for p in SUJO.rglob('*') if p.is_file()}
        varrer.rodar([str(SUJO)])
        depois = {p: p.stat().st_mtime_ns for p in SUJO.rglob('*') if p.is_file()}
        self.assertEqual(antes, depois)

    def test_html_tem_graficos_e_lista(self):
        au = varrer.rodar([str(SUJO)])
        h = varrer.relatorio_html(au)
        self.assertGreaterEqual(h.count('<svg'), 3)
        self.assertIn('gerar correcoes.md', h)
        self.assertIn('A001', h)
        self.assertNotIn('</script><', h.split('id="dados"')[1].split('</script>')[0])

    def test_json_e_correcoes(self):
        with tempfile.TemporaryDirectory() as d:
            j = Path(d) / 'r.json'
            md = Path(d) / 'c.md'
            with redirect_stdout(io.StringIO()):
                self.assertEqual(varrer.main([str(SUJO), '--saida-json', str(j)]), 0)
            dados = json.loads(j.read_text())
            for a in dados['achados']:
                for k in ('id', 'ponto', 'arquivo', 'linha', 'sev', 'sugestao'):
                    self.assertIn(k, a)
            with redirect_stdout(io.StringIO()):
                varrer.main(['--correcoes', 'A001,A999', '--de', str(j), '--saida', str(md)])
            t = md.read_text()
            self.assertIn('## A001', t)
            self.assertIn('A999', t)  # avisado como não encontrado
            self.assertIn('vale como aprovação só para estas edições', t)
            self.assertIn('.audite-backup/', t)

    def test_estrito(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(varrer.main([str(SUJO), '--estrito']), 1)
            self.assertEqual(varrer.main([str(LIMPO), '--estrito']), 0)

    def test_anonimo(self):
        au = varrer.Auditoria(anonimo=True)
        self.assertTrue(au.nome(Path(varrer.HOME) / 'x').startswith('~'))

    def test_texto_resumo(self):
        au = varrer.rodar([str(SUJO)])
        t = varrer.texto(au)
        self.assertIn('achados', t)
        self.assertIn('Por ponto', t)


if __name__ == '__main__':
    unittest.main()
