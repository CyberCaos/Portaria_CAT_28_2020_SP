import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import panorama_cat68 as P  # noqa: E402


def test_panorama_2026_datas_itens_e_posicoes():
    p = P.montar(2026, date(2026, 10, 1))
    assert len(p['rev']) == 468 and [d.strftime('%d/%m') for d in p['datas']] == ['01/01', '01/04', '01/07', '01/08', '01/10']
    assert [x[6] for x in p['resumo']] == ['31/12/2025', '31/03/2026', '30/06/2026', '31/07/2026', '30/09/2026']   # posição = dia anterior
    anexos = {a[0]: a for a in p['anexos']}
    assert 'IV' in anexos and 'XXII' in anexos and anexos['IV'][4] == 'só NCM' and anexos['XXII'][4] == 'NCM + CEST'
    assert len(p['na_st']) == 277


def test_panorama_situacao_depende_da_data_de_referencia():
    antes = P.montar(2026, date(2026, 5, 10))['resumo']
    assert antes[0][1].startswith('Já saiu') and antes[2][1].startswith('Vai sair')
    depois = P.montar(2026, date(2026, 10, 1))['resumo']
    assert depois[-1][1] == 'Sai hoje'


def test_panorama_grava_planilha():
    import openpyxl
    with tempfile.TemporaryDirectory() as tmp:
        destino, _ = P.gravar(2026, date(2026, 10, 1), tmp)
        wb = openpyxl.load_workbook(destino, read_only=True)
        nomes = wb.sheetnames
        wb.close()
        assert nomes == ['Resumo por data', 'Por anexo', 'Itens', 'Posições de estoque', 'Ainda na ST']
