"""Testes da aplicação da fórmula da CAT 28/2020 sobre as linhas alocadas. Rodar: python scripts/tests/test_credito.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import credito as CR  # noqa: E402


def linha(bc, vl_liq, vl_bruto=None, aliq=18.0, cst='10', st_cobrado=0.0, p_red=0.0, confirmado=True, sem_base=False, **k):
    l = dict(bc_st_usada=bc, vl_liq_usado=vl_liq, vl_merc_usado=vl_liq if vl_bruto is None else vl_bruto, aliquota_st=aliq, cst=cst,
             crt_emitente='3', uf_emitente='SP', uf_destinatario='SP', p_icms=0.0, p_red_bc_st=p_red, st_cobrado_usado=st_cobrado,
             confirmado=confirmado, sem_base_st=sem_base)
    l.update(k)
    return l


def test_anexo_v_sem_reducao():
    r = CR.calcular_linha('SN', linha(bc=1000, vl_liq=700))
    assert r['status'] == 'calculado' and r['credito'] == 54.0 and 'Anexo V' in r['linha_tabela'] and r['formula'].startswith('C = (BC ST')


def test_valor_liquido_de_desconto_resolve_o_negativo():
    # JARDIANCE: vProd 738,45, vDesc 205,08, BC ST 619,47. Com vProd o crédito seria negativo; com o líquido, positivo.
    l = linha(bc=619.47, vl_liq=738.45 - 205.08, vl_bruto=738.45)
    r = CR.calcular_linha('SN', l)
    assert r['credito'] == round((619.47 - 533.37) * 0.18, 2) and r['credito'] > 0
    assert r['alt_vprod'] < 0 and any('VlMerc líquido' in a for a in r['alertas'])
    lit = CR.calcular_linha('SN', l, valor_mercadoria='vprod')                  # leitura literal continua disponível
    assert lit['credito'] == r['alt_vprod'] and lit['credito'] < 0


def test_credito_nao_limitado_ao_st_destacado():
    r = CR.calcular_linha('SN', linha(bc=1000, vl_liq=700, st_cobrado=40.0))   # fórmula daria 54, a nota cobrou 40
    assert r['credito'] == 54.0
    r2 = CR.calcular_linha('SN', linha(bc=1000, vl_liq=700, st_cobrado=53.97))  # diferença de centavos não aciona o teto
    assert r2['credito'] == 54.0


def test_sem_base_de_st_credito_zero():
    r = CR.calcular_linha('SN', linha(bc=0.0, vl_liq=10.0, sem_base=True))
    assert r['credito'] == 0.0 and r['status'] == 'sem_base_st' and 'art. 4º' in r['alertas'][0]


def test_aliquota_ausente_nao_calcula():
    r = CR.calcular_linha('SN', linha(bc=100, vl_liq=50, aliq=None))
    assert r['credito'] is None and r['status'] == 'sem_aliquota'


def test_reducao_explicita():
    r = CR.calcular_linha('SN', linha(bc=1000, vl_liq=700, p_red=50.0, cst='70', reducao=CR.F.RED_APLICAVEL_CF))
    assert r['credito'] == round((1000 - 700) * 0.5 * 0.18, 2)                  # leitura de menor crédito
    assert r['status'] == 'calculado'


def test_rpa_anexo_iv_e_combinacao_nao_prevista():
    ok = CR.calcular_linha('RPA', linha(bc=1000, vl_liq=700))                   # RPA/RPA, retenção pelo fornecedor, sem redução
    assert ok['credito'] == 180.0 and 'Anexo IV' in ok['linha_tabela']
    an = CR.calcular_linha('RPA', linha(bc=1000, vl_liq=700, cst='60'))         # substituto anterior + fornecedor RPA: analogia
    assert an['credito'] == 180.0 and an['analogia'] and any('analogia' in a for a in an['alertas'])


def test_consolidacao_soma_com_piso_zero():
    ls = [linha(bc=100, vl_liq=50), linha(bc=10, vl_liq=40), linha(bc=300, vl_liq=100)]
    rs = [CR.calcular_linha('SN', l) for l in ls]
    c = CR.consolidar_item(ls, rs)
    assert rs[1]['credito'] < 0                                                 # linha negativa compensa dentro da mercadoria
    assert c['credito'] == round(max(0, sum(r['credito'] for r in rs)), 2)
    assert 'confirmado' not in c and 'validacao' not in c
    neg = CR.consolidar_item([linha(bc=10, vl_liq=40)], [CR.calcular_linha('SN', linha(bc=10, vl_liq=40))])
    assert neg['credito'] == 0.0 and neg['total_literal'] < 0                   # mercadoria negativa nunca gera débito


if __name__ == '__main__':
    for n, fn in list(globals().items()):
        if n.startswith('test_'):
            fn()
            print('ok', n)
