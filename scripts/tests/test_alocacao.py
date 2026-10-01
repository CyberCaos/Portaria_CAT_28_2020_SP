"""Testes da alocação de notas e do fator de conversão. Rodar: python scripts/tests/test_alocacao.py"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import alocacao as A  # noqa: E402
import fator_conversao as F  # noqa: E402


def nf(dia, qtd=10, vl=100.0, **k):
    base = dict(chave_nfe=f'NF{dia}', n_item='1', data_emissao=dia, qtd=qtd, qtd_trib=qtd, vl_merc=vl, vbc_st=0.0, vbc_st_ret=0.0,
                p_icms_st=0.0, p_fcp_st=0.0, p_st=0.0, p_fcp_st_ret=0.0, vbc_fcp_st_ret=0.0, cst='10', situacao='Normal',
                c_stat='100', fin_nfe='1', cfop='5403', descricao='PRODUTO X 10MG C/30 COMP', ean='7891000000001', unid_comercial='UN',
                crt_emitente='3', uf_emitente='SP', uf_destinatario='SP', p_red_bc_st=0.0, cod_produto='x')
    base.update(k)
    return base


FATOR1 = lambda item, linha: dict(fator=1.0, origem='teste', confianca='A', observacao='')
REV = date(2026, 1, 1)


# ---------------------------------------------------------------- regra 4: só antes da vigência
def test_elegibilidade():
    assert A.elegivel(nf('2025-12-31'), REV) == (True, '')
    assert not A.elegivel(nf('2026-01-01'), REV)[0] and not A.elegivel(nf('2026-03-01'), REV)[0]
    assert A.elegivel(nf('2025-01-01', situacao='Cancelada'), REV)[1] == 'nota cancelada'
    assert A.elegivel(nf('2025-01-01', c_stat='110'), REV)[1] == 'nota não autorizada'
    assert A.elegivel(nf('2025-01-01', fin_nfe='4'), REV)[1] == 'devolução'
    assert A.elegivel(nf('2025-01-01', cfop='5202'), REV)[1] == 'CFOP de devolução'
    assert A.elegivel(nf('2025-01-01', cfop='5910'), REV)[0]             # bonificação entra no estoque: elegível


# ---------------------------------------------------------------- regra 3: alíquota
def test_aliquota_prioridade():
    assert A.aliquota_st(nf('2025-01-01', p_icms_st=18.0, p_fcp_st=2.0, p_st=12.0), 25.0)[0] == 20.0          # ST da nota + FCP
    assert A.aliquota_st(nf('2025-01-01', p_st=18.0, p_fcp_st_ret=1.0), 25.0) == (18.0, 'ST retido anteriormente (pST, já inclui FCP)')   # NT 2016.002
    assert A.aliquota_st(nf('2025-01-01'), 12.0) == (12.0, 'alíquota interna do item no estoque (totalizador)')
    assert A.aliquota_st(nf('2025-01-01'), None) == (18.0, A.ORIGEM_ALIQ_PADRAO)          # sem alíquota: 18% padrão de SP


# ---------------------------------------------------------------- regras 1 e 2: várias notas, base unitária x quantidade
def test_varias_notas_mais_recente_primeiro_e_base_unitaria():
    compras = [nf('2025-01-10', qtd=10, vl=100.0, vbc_st=150.0),                       # antiga
               nf('2025-11-20', qtd=4, vl=48.0, vbc_st_ret=80.0, cst='60', p_st=18.0),   # recente: usada primeiro
               nf('2026-02-01', qtd=50, vl=500.0, vbc_st=900.0)]                       # posterior à vigência: ignorada
    item = dict(descricao='PRODUTO X', ean='7891000000001', qtd=9.0, valor=10.0, aliq_totalizador=18.0)
    consumo = {}
    r = A.alocar(item, [dict(origem='ean', confirmado=True, linhas=[0, 1, 2])], compras, REV, consumo, FATOR1)
    assert [l['chave_nfe'] for l in r['linhas']] == ['NF2025-11-20', 'NF2025-01-10']
    a, b = r['linhas']
    assert a['qtd_usada_estoque'] == 4 and b['qtd_usada_estoque'] == 5                 # a última nota entra em parte
    assert abs(a['bc_st_ret_unit'] - 20.0) < 1e-9 and a['bc_st_unit'] == 0 and abs(a['bc_st_usada'] - 80.0) < 1e-9
    assert abs(b['bc_st_unit'] - 15.0) < 1e-9 and abs(b['bc_st_usada'] - 75.0) < 1e-9  # 150/10 por unidade x 5 unidades
    assert abs(a['vl_merc_unit'] - 12.0) < 1e-9 and abs(b['vl_merc_unit'] - 10.0) < 1e-9
    assert r['qtd_coberta'] == 9 and r['qtd_descoberta'] == 0
    assert a['aliquota_st'] == 18.0 and a['aliquota_origem'].startswith('ST retido anteriormente')       # pST da nota
    assert b['aliquota_st'] == 18.0 and b['aliquota_origem'].startswith('alíquota interna do item')      # nota sem alíquota: estoque
    assert r['descartadas'] == {'emitida na vigência da exclusão ou depois': 1}


def test_estoque_maior_que_as_notas_fica_descoberto():
    compras = [nf('2025-05-01', qtd=3)]
    r = A.alocar(dict(descricao='X', ean='1', qtd=10.0, valor=1.0, aliq_totalizador=None), [dict(origem='ean', confirmado=True, linhas=[0])],
                 compras, REV, {}, FATOR1)
    assert r['qtd_coberta'] == 3 and r['qtd_descoberta'] == 7


def test_consumo_compartilhado_entre_itens_da_mesma_posicao():
    compras = [nf('2025-05-01', qtd=10)]
    consumo = {}
    g = [dict(origem='ean', confirmado=True, linhas=[0])]
    r1 = A.alocar(dict(descricao='X', ean='1', qtd=7.0, valor=1.0, aliq_totalizador=None), g, compras, REV, consumo, FATOR1)
    r2 = A.alocar(dict(descricao='Y', ean='2', qtd=7.0, valor=1.0, aliq_totalizador=None), g, compras, REV, consumo, FATOR1)
    assert r1['qtd_coberta'] == 7 and r2['qtd_coberta'] == 3                      # a mesma nota não supre duas vezes


def test_prova_obrigatoria_descarta_localizacao_e_fator_sem_prova():
    compras = [nf('2025-05-01', qtd=10), nf('2025-06-01', qtd=10, chave_nfe='NFB')]
    item = dict(descricao='X', ean='1', qtd=5.0, valor=10.0, aliq_totalizador=None)
    consumo = {}
    r = A.alocar(item, [dict(origem='descrição C', confirmado=False, linhas=[0])], compras, REV, consumo, FATOR1)
    assert r['linhas'] == [] and r['descartadas'] == {A.MOTIVO_LOCALIZACAO: 1} and consumo == {}   # não consome a nota
    fator_c = lambda it, l: dict(fator=1.0, origem='sem prova', confianca='C', observacao='') if l['chave_nfe'] == 'NFB' else FATOR1(it, l)
    r = A.alocar(item, [dict(origem='ean', confirmado=True, linhas=[0, 1])], compras, REV, consumo, fator_c)
    assert [l['chave_nfe'] for l in r['linhas']] == ['NF2025-05-01'] and r['descartadas'] == {A.MOTIVO_FATOR: 1}
    assert all(l['confirmado'] for l in r['linhas'])
    r = A.alocar(item, [dict(origem='descrição C', confirmado=False, linhas=[0])], compras, REV, {}, FATOR1, exigir_prova=False)
    assert r['qtd_coberta'] == 5 and not r['linhas'][0]['confirmado']                           # só na simulação "fora do crédito"


def test_verificar_consumo_trava_uso_alem_da_quantidade():
    compras = [nf('2025-05-01', qtd=10)]
    A.verificar_consumo({0: 10.0}, compras)
    try:
        A.verificar_consumo({0: 10.5}, compras)
    except A.ConsumoExcedido as ex:
        assert 'usado 10.5 de 10' in str(ex)
    else:
        raise AssertionError('uso além da quantidade não foi barrado')


def test_fator_divide_a_base_unitaria():
    compras = [nf('2025-05-01', qtd=2, vl=120.0, vbc_st=240.0)]
    f6 = lambda item, linha: dict(fator=6.0, origem='XML', confianca='A', observacao='')
    r = A.alocar(dict(descricao='X', ean='1', qtd=6.0, valor=1.0, aliq_totalizador=None), [dict(origem='ean', confirmado=True, linhas=[0])],
                 compras, REV, {}, f6)
    l = r['linhas'][0]
    assert l['qtd_equivalente_linha'] == 12 and abs(l['bc_st_unit'] - 20.0) < 1e-9 and abs(l['bc_st_usada'] - 120.0) < 1e-9
    assert abs(l['vl_merc_unit'] - 10.0) < 1e-9


# ---------------------------------------------------------------- fator de conversão (só descrição do estoque + XML)
def linha(desc, qtd, vl, qtrib=None, ucom='UN'):
    return dict(descricao=desc, qtd=qtd, qtd_trib=qtd if qtrib is None else qtrib, vl_merc=vl, unid_comercial=ucom)


def test_fator_xml_confirmado_pelo_preco():
    r = F.fator_linha(dict(descricao='FR GER HIGIFRAL CONFORT MED 06X08UN', valor=15.62),
                      linha('FR GER HIGIFRAL COMFORT MED 06X08UN', 1, 82.61 * 1, qtrib=6, ucom='FD'))
    assert r['fator'] == 6 and r['confianca'] == 'A' and 'XML' in r['origem']


def test_fator_display_pela_descricao_da_nota():
    r = F.fator_linha(dict(descricao='PASSAJA 4 ML', valor=5.86), linha('PASSAJA DISPLAY C/24 FLAC 4ML-SIMILAR', 1, 152.86))
    assert r['fator'] == 24 and r['confianca'] == 'B'


def test_fator_unidade_solta_quando_estoque_guarda_caixa():
    r = F.fator_linha(dict(descricao='AGULHA DESC BD C/100', valor=19.0), linha('AGULHA DESC BD', 100, 19.0 * 1))
    assert abs(r['fator'] - 0.01) < 1e-9                        # 100 agulhas soltas da nota = 1 caixa de 100 do estoque


def test_descricoes_iguais_e_preco_coerente_fator_1():
    r = F.fator_linha(dict(descricao='CLORANA 50MG C/20CP', valor=12.0), linha('CLORANA 50MG C/20 COMP', 5, 70.0))
    assert r['fator'] == 1 and r['confianca'] == 'A'


def test_numero_repetido_nas_duas_descricoes_nao_e_embalagem():
    # "30X7" é calibre da agulha nas duas descrições: não vira fator 30
    r = F.fator_linha(dict(descricao='AGULHA DESC 30X7 C/100', valor=0.39), linha('AGULHA DESC 30X7 C/100', 1, 19.46))
    assert r['fator'] != 30


def test_descricoes_iguais_com_preco_absurdo_vai_para_revisao():
    r = F.fator_linha(dict(descricao='CORISTINA D CONGEST C/120 CPR', valor=0.09), linha('CORISTINA D CONGEST C/120 CPR', 1, 195.46))
    assert r['confianca'] == 'C' and r['fator'] == 1


def test_preco_so_arbitra_nao_cria_fator():
    r = F.fator_linha(dict(descricao='GLIBENCLAMIDA 5MG C/30CP', valor=1.90), linha('GLIBENCLAMIDA 5MG C/30 COMP', 1, 10.58))
    assert r['fator'] == 1 and r['confianca'] in ('A', 'B')     # preço 5,6x o custo, mas embalagem igual: sem fator inventado


if __name__ == '__main__':
    for n, fn in list(globals().items()):
        if n.startswith('test_'):
            fn()
            print('ok', n)
