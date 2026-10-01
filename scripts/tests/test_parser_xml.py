"""Testes do parser de XML (espelham NfeNfceParserTests/ParserFactoryTests do projeto original).
Rodar: python scripts/tests/test_parser_xml.py"""
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from decimal import Decimal as D

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, '..'))
from parser_xml import processar_arquivo, processar_entrada, processar_lote  # noqa: E402
from parser_xml import xmlhelpers as X  # noqa: E402

FIX = os.path.join(AQUI, 'fixtures')
f = lambda n: os.path.join(FIX, n)


def item(nome):
    r = processar_arquivo(f(nome))
    assert r.erro is None, r.erro
    return r.itens


def test_nfce_ibscbs_st_campos():
    it = item('nfe_com_ibscbs_st.xml')
    assert len(it) == 1
    i = it[0]
    assert i.modelo == 'NFCe' and i.sequencia == 1
    assert i.chave == '31260611950487015898550010002695021505599744'
    assert (i.emitente_documento, i.destinatario_documento) == ('11950487015898', '29062082000180')
    assert (i.ncm, i.cest, i.cfop, i.cst_icms) == ('21050010', '2300100', '6401', '10')
    assert i.p_red_bc == D('10.0000') and i.p_red_bc_st == D('5.0000')
    assert (i.emitente_uf, i.destinatario_uf) == ('MG', 'SP')
    assert i.data_emissao == datetime(2026, 6, 25, 13, 4)  # horário como escrito, sem converter fuso
    assert i.valor_item == D('20176.00') and i.icms.valor == D('2421.12')
    assert i.icms_st.base == D('39720.00') and i.icms_st.valor == D('4728.48')
    assert i.valor_contabil == D('20176.00') + D('4728.48') + D('655.72')


def test_campos_ausentes_ficam_zero():
    i = item('nfe_sem_ibscbs.xml')[0]
    assert i.modelo == 'NFe' and i.icms_st.valor == 0 and i.ipi.valor == 0
    assert i.emitente_uf == '' and i.valor_contabil == D('990.00')


def test_cpf_como_fallback():
    i = item('nfe_dest_cpf.xml')[0]
    assert i.emitente_documento == '98765432100' and i.destinatario_documento == '12345678909'


def test_valor_contabil_com_frete_seguro_outros_desconto():
    i = item('nfe_com_frete_desconto.xml')[0]
    assert i.valor_contabil == D('990.00') + 10 + 5 + 2 - 3


def test_sem_infnfe_erro_com_nome_do_arquivo():
    r = processar_arquivo(f('nfe_mod_valido_sem_infnfe.xml'))
    assert r.itens == [] and 'infNFe não encontrado' in r.erro and 'nfe_mod_valido_sem_infnfe.xml' in r.erro


def test_det_sem_prod_nao_quebra():
    i = item('nfe_det_sem_prod.xml')[0]
    assert i.codigo_produto == '' and i.valor_item == 0 and i.icms.valor == 0


def test_icms_st_retido_anteriormente():
    i = item('nfe_icms_st_retido.xml')[0]
    assert (i.icms_st_retido_ant.base, i.icms_st_retido_ant.aliquota, i.icms_st_retido_ant.valor) == (
        D('120.00'), D('18.0000'), D('21.60'))
    assert (i.fcp_st_retido_ant.base, i.fcp_st_retido_ant.valor) == (D('120.00'), D('2.40'))
    assert i.cst_icms == '60'
    assert i.orig_icms == '0'                                     # origem da mercadoria (define 4% x 12% interestadual)
    import compras
    assert compras.linha_compra(i)['orig'] == '0' and 'orig' in compras.CAMPOS_COMPRAS


def test_e_comercial_e_menor_que_soltos():
    assert item('nfe_com_caracteres_invalidos.xml')[0].descricao == 'CITONEURIN 5000 P & G, NEO < 700GR'


def test_evento_cancelamento():
    r = processar_arquivo(f('evento_cancelamento.xml'))
    assert r.erro is None and r.itens == [] and r.evento.ch_nfe == '35260629062082000180550010000394151577789420'
    assert processar_arquivo(f('evento_tipo_nao_suportado.xml')).erro
    assert processar_arquivo(f('evento_cancelamento_sem_chave.xml')).erro


def test_xml_malformado_nao_lanca():
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, 'x.xml')
        open(p, 'w').write('<nfeProc><NFe>')
        r = processar_arquivo(p)
        assert r.erro and r.itens == []
        assert processar_arquivo(os.path.join(tmp, 'nao_existe.xml')).erro
    finally:
        shutil.rmtree(tmp)


def test_lote_cancelamento_e_orfao_e_duplicata():
    lote = processar_lote([f('nfe_para_cancelar.xml'), f('nfe_para_cancelar.xml'), f('evento_cancelamento.xml'),
                           f('evento_cancelamento_chave_orfa.xml'), f('nfe_sem_ibscbs.xml')])
    assert lote.notas_duplicadas == 1
    chaves = {i.chave for i in lote.itens}
    assert len(chaves) == 2
    assert len(lote.eventos) == 2 and len(lote.eventos_orfaos) >= 1
    canc = [i for i in lote.itens if i.situacao == 'Cancelada']
    for c in canc:
        assert c.valor_item == 0 and c.icms_st_retido_ant.valor == 0 and c.ncm  # zera valor, mantém identificação


def test_pasta_e_zip_aninhado():
    tmp = tempfile.mkdtemp()
    try:
        interno = os.path.join(tmp, 'interno.zip')
        with zipfile.ZipFile(interno, 'w') as z:
            z.write(f('nfe_icms_st_retido.xml'), 'sub/a.xml')
        externo = os.path.join(tmp, 'lote.zip')
        with zipfile.ZipFile(externo, 'w') as z:
            z.write(f('nfe_sem_ibscbs.xml'), 'compras/b.xml')
            z.write(interno, 'compras/interno.zip')
        lote = processar_entrada(externo)
        assert {i.cst_icms for i in lote.itens} >= {'60'} and len(lote.itens) == 2, len(lote.itens)
    finally:
        shutil.rmtree(tmp)


def test_helpers():
    assert X.parse_dec('12.50') == D('12.50') and X.parse_dec('') == 0 and X.parse_dec('abc') == 0
    assert X.parse_data('2024-10-01') == datetime(2024, 10, 1)
    assert X.parse_data('2024-09-02T11:00:00-03:00') == datetime(2024, 9, 2, 11, 0)
    assert X.parse_data('20240902') == datetime(2024, 9, 2)
    assert X.parse_data('lixo') is None


if __name__ == '__main__':
    for n, fn in list(globals().items()):
        if n.startswith('test_'):
            fn()
            print('ok', n)
