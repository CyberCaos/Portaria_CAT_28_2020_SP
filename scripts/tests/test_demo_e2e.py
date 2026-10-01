"""Ponta a ponta com o pacote fictício de exemplos/: SN e RPA, planilha, PDF e reconciliação."""
import os
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, '..'))
sys.path.insert(0, os.path.join(AQUI, '..', '..', 'exemplos'))
import fitz  # noqa: E402
import gerar_pacote_demo as DEMO  # noqa: E402
import gerar_relatorio as GR  # noqa: E402
import levantamento as LV  # noqa: E402
import preparar_cliente as PC  # noqa: E402
import reconciliar as REC  # noqa: E402


def _rodar(regime, tmp):
    pacote = os.path.join(tmp, 'pacote')
    DEMO.main(pacote)
    info = PC.preparar(DEMO.EMPRESA[0], DEMO.EMPRESA[1], [pacote], [pacote], os.path.join(tmp, 'out'), regime=regime)
    pasta = info['pasta']
    return pasta, LV.levantar(pasta)


def test_demo_sn_unificado_e_pdf_sem_classes():
    with tempfile.TemporaryDirectory() as tmp:
        pasta, r = _rodar('SN', tmp)
        assert r['anexo'] == 'V' and r['credito_total'] == 50.22 and r['mercadorias_definitivas'] == 5   # tudo somado
        pdf = GR.gerar_pdf(pasta)
        texto = ''.join(p.get_text() for p in fitz.open(pdf)).lower()
        assert 'crédito total' in texto and 'interpretativo' not in texto and 'definitivo' not in texto
        res, ponte, destino = REC.reconciliar(pasta, anterior_total=None)
        assert os.path.exists(destino) and res['atual_total'] == 50.22


def test_demo_rpa_anexo_iv():
    with tempfile.TemporaryDirectory() as tmp:
        pasta, r = _rodar('RPA', tmp)
        assert r['anexo'] == 'IV' and r['credito_total'] == 175.77
