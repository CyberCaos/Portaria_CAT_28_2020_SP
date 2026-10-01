"""Testes do núcleo. Rodar: python -m pytest scripts/tests  (ou python scripts/tests/test_core.py)."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import formulas as F


def test_rpa_rpa_sem_reducao():
    r = F.credito_item(regime_detentor=F.RPA, regime_fornecedor=F.RPA, responsavel=F.RET_FORNECEDOR,
                       operacao=F.INTERNA, bc_st=1000, vl_merc=700, aliq_interna=0.18)
    assert r.credito == 180.00 and r.anexo == 'IV'


def test_rpa_rpa_com_reducao():
    r = F.credito_item(regime_detentor=F.RPA, regime_fornecedor=F.RPA, responsavel=F.RET_FORNECEDOR,
                       operacao=F.INTERESTADUAL, reducao=F.RED_APLICAVEL_CF, bc_st=1000, vl_merc=700,
                       aliq_interna=0.18, p_red=0.3333333)
    assert abs(r.credito - 120.00) < 0.01


def test_rpa_fornecedor_sn_interestadual():
    r = F.credito_item(regime_detentor=F.RPA, regime_fornecedor=F.SN, responsavel=F.RET_FORNECEDOR,
                       operacao=F.INTERESTADUAL, bc_st=1000, vl_merc=700, aliq_interna=0.18, aliq_interestadual=0.12)
    assert r.credito == 96.00  # 1000*0.18 - 700*0.12


def test_sn_detentor():
    r = F.credito_item(regime_detentor=F.SN, regime_fornecedor=F.RPA, responsavel=F.RET_FORNECEDOR,
                       operacao=F.INTERNA, bc_st=1000, vl_merc=700, aliq_interna=0.18)
    assert r.credito == 54.00 and r.anexo == 'V'  # (1000-700)*0.18


def test_anexo_v_com_reducao_gera_alerta():
    r = F.credito_item(regime_detentor=F.SN, regime_fornecedor=F.SN, responsavel=F.ANTEC_ADQUIRENTE,
                       operacao=F.INTERESTADUAL, reducao=F.RED_NAO_APLICAVEL_CF, bc_st=1000, vl_merc=700,
                       aliq_interna=0.18, p_red=0.5)
    assert r.alertas and r.credito == round((1000 - 700 * 0.5) * 0.18, 2)


def test_rpa_rpa_substituto_anterior_por_analogia():
    r = F.credito_item(regime_detentor=F.RPA, regime_fornecedor=F.RPA, responsavel=F.RET_SUBST_ANTERIOR,
                       operacao=F.INTERNA, bc_st=1000, vl_merc=700, aliq_interna=0.18)
    assert r.credito == 180.0 and r.analogia and 'analogia' in r.linha


def test_responsavel_desconhecido_nao_previsto():
    try:
        F.credito_item(regime_detentor=F.RPA, regime_fornecedor=F.RPA, responsavel='outro',
                       operacao=F.INTERNA, bc_st=1, vl_merc=1, aliq_interna=0.18)
    except F.NaoPrevistoNaPortaria:
        return
    raise AssertionError('deveria levantar NaoPrevistoNaPortaria')


def test_anexo_iv_cobre_todas_as_combinacoes():
    """Toda combinação regime do fornecedor x responsável x operação x redução tem fórmula (literal ou por analogia)."""
    esperado_literal = {
        (F.RPA, F.RET_FORNECEDOR), (F.RPA, F.ANTEC_ADQUIRENTE), (F.SN, F.RET_FORNECEDOR)}
    for forn in (F.RPA, F.SN):
        for resp in (F.RET_FORNECEDOR, F.ANTEC_ADQUIRENTE, F.RET_SUBST_ANTERIOR):
            for oper in (F.INTERNA, F.INTERESTADUAL):
                for red, p in ((F.SEM_REDUCAO, 0.0), (F.RED_APLICAVEL_CF, 0.5), (F.RED_NAO_APLICAVEL_CF, 0.5)):
                    r = F.credito_item(regime_detentor=F.RPA, regime_fornecedor=forn, responsavel=resp, operacao=oper, reducao=red,
                                       bc_st=1000, vl_merc=700, aliq_interna=0.18, aliq_interestadual=0.12, p_red=p)
                    assert r.anexo == 'IV' and r.credito is not None
                    if (forn, resp) in esperado_literal:
                        assert not r.analogia, (forn, resp, oper, red)
    # linhas literais do fornecedor SN com substituto anterior e antecipação interestadual
    lit = lambda **k: F.credito_item(regime_detentor=F.RPA, regime_fornecedor=F.SN, bc_st=1000, vl_merc=700, aliq_interna=0.18, **k)
    assert not lit(responsavel=F.RET_SUBST_ANTERIOR, operacao=F.INTERNA).analogia
    assert not lit(responsavel=F.ANTEC_ADQUIRENTE, operacao=F.INTERESTADUAL).analogia
    assert not lit(responsavel=F.ANTEC_ADQUIRENTE, operacao=F.INTERESTADUAL, reducao=F.RED_APLICAVEL_CF, p_red=0.5).analogia
    assert lit(responsavel=F.ANTEC_ADQUIRENTE, operacao=F.INTERNA).analogia
    assert lit(responsavel=F.RET_SUBST_ANTERIOR, operacao=F.INTERNA, reducao=F.RED_APLICAVEL_CF, p_red=0.5).credito == 90.0


def test_p_red_bc():
    assert abs(F.p_red_bc(0.18, 0.12) - 1 / 3) < 1e-9


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_'):
            f(); print('ok', n)
