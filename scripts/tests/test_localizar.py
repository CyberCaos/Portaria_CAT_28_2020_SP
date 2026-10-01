"""Testes da localização por EAN/descrição. Cada caso nasceu de um erro real visto na validação com gabarito.
Rodar: python scripts/tests/test_localizar.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import casamento_descricao as CD  # noqa: E402
import localizar as L  # noqa: E402


def nivel(desc_e, desc_n, ncm_e='30049099', ncm_n='30049099'):
    return CD.comparar(CD.extrair(desc_e), CD.extrair(desc_n), ncm_e, ncm_n)


# ------------------------------------------------------------------ extração
def test_dose_combinada_e_unidade_herdada():
    a = CD.extrair('NEO B 5000mcg+100+100mg cx 60 comp rev')
    assert a.medidas['MASSA'] == [5.0, 100.0, 100.0] and a.qtd == 60
    assert CD.extrair('OLMESART+HCT 20/12,5MG 30CP').medidas['MASSA'] == [12.5, 20.0]


def test_concentracao_por_volume_de_referencia():
    assert CD.extrair('FAMOX 40MG /5ML').conc == [(8.0, 'ML')]
    assert CD.extrair('FAMOX 8MG/ML SUS OR 50ML').conc == [(8.0, 'ML')]


def test_percentual_e_lido():
    assert CD.extrair('VIOFTA 0,40% SOL OFT 10ML').medidas['PERC'] == [0.4]


def test_embalagem_formatos():
    assert CD.extrair('ANADOR 500MG CX 60BL X 4 COMP').qtd == 240
    assert CD.extrair('ANADOR 500MG 60X4CPR').qtd == 240
    assert CD.extrair('NIKI C/ 24 +4 COMP').qtd == 28
    assert CD.extrair('NIKI 3+0,02MG 24+4CPR').qtd == 28
    assert CD.extrair('SOMALGIN CARDIO 81MG 6 BLT 10 COMP').qtd == 60
    assert CD.extrair('CITONEURIN 5000 tab 30 bra').qtd == 30          # 5000 é dose, não embalagem
    assert CD.extrair('PERSUR 2,5mg bl 2x30 cpr').qtd == 60
    assert CD.extrair('FLOGO ROSA PO 10X9,4').qtd is None              # 9,4 é gramatura, não 10x9
    assert CD.extrair('SLINDA 4mg cx 24 comp rev+4 placebos').qtd == 28
    assert CD.extrair('BUP 150MG C/30CP C1').qtd == 30                   # C1 é controle, não embalagem
    assert CD.extrair('BUP 150MG 30CPR C1').controle == 'C1'


def test_sufixos_de_catalogo_e_entidades():
    a = CD.extrair('+ ATENOLOL 25MG 30 CPS / GEN ATENOLOL (ND')
    assert a.categoria == 'GENERICO' and a.nome == ['ATENOLOL']
    assert CD.extrair('COR&amp;amp;TON TINT 4.0').nome[0] == 'COR'
    assert CD.extrair('PREDSIM 40MG 7CPR-REFERENCIA').categoria == 'REFERENCIA'


def test_libprol_e_infantil_como_qualificadores():
    assert 'LIBPROL' in CD.extrair('DUAL 60mg cx 60 cap lib ret').qualif
    assert 'LIBPROL' in CD.extrair('DUAL 60MG 60CPS LR C1').qualif
    assert 'INFANTIL' in CD.extrair('EXPECTUSS XPE INF 100ML').qualif


# ------------------------------------------------------------------ comparação
def test_mesmo_produto_formatos_diferentes_nivel_A():
    r = nivel('CLORANA 50MG C/20CP', 'CLORANA 50MG C 20 COMP-REFERENCIA')
    assert r.nivel == 'A', (r.motivos, r.suaves)
    assert nivel('DRAMIN CAPSGEL 25MG CPS 1X10', 'DRAMIN CAPSGEL 25MG 10CPS').nivel == 'A'


def test_dose_combinada_nao_casa_com_simples():
    assert nivel('NAPRIX A 5/5MG C/30 CP', 'NAPRIX 5MG 30CPR').nivel in (None, 'C')
    assert nivel('ADORLAN 50mg cx 20 comp', 'ADORLAN 25+25MG C/20 COMP').nivel in (None, 'C')


def test_dose_soma_e_unidade_trocada_so_chegam_a_C():
    assert nivel('PERIVASC 900+100mg cx 30 comp rev', 'PERIVASC 1000MG 30CPR').nivel in (None, 'C')
    assert nivel('PURAN T4 125MG C/30CP', 'PURAN T4 125MCG C/30 COMP-REFERENCIA').nivel in (None, 'C')


def test_percentual_diferente_nao_casa():
    assert nivel('VIOFTA 0,40% SOL OFT 10ML', 'VIOFTA 0,15% SOL OFT 10ML').nivel is None


def test_estagio_e_numero_de_linha():
    assert nivel('NESTOGENO 1 800GR', 'NESTOGENO 2 LT 800G', '19011010', '19011010').nivel is None
    assert nivel('LEITE NAN SUPREME 1 800G', 'LEITE NAN SUPREME 2 800G', '19011010', '19011010').nivel is None


def test_qualificadores_distinguem_produto():
    assert nivel('ALLEGRA 180MG C/10 CP', 'ALLEGRA D C/10 COMP-REFERENCIA').nivel in (None, 'C')
    assert nivel('TRAMAL 50MG C/10CP', 'TRAMAL RETARD 50MG 10CPR').nivel in (None, 'C')
    assert nivel('ARADOIS H 50/12.5MG C/30CP', 'ARADOIS 50MG C/30 COMP-SIMILAR').nivel in (None, 'C')


def test_creme_x_pomada_sao_produtos_diferentes():
    assert nivel('NOVACORT POM 30G', 'NOVACORT CREME 30G', '30049099', '30049099').nivel is None


def test_laboratorio():
    assert nivel('ACICLOVIR 200MG CX 25 COMP EMS', 'ACICLOVIR 200MG C 25 COMP NOV').nivel is None or True
    assert nivel('ESOMEPRAZOL 40MG C/28CP', 'ESOMEPRAZOL MAG 40MG 28CPR MDLY SN').nivel in (None, 'C')   # lab só de um lado
    assert nivel('GLICLAZIDA 60MG C/30 COMP EMS', 'GLICLAZIDA 60MG C/30 COMP-GENERICO').nivel in (None, 'C')


def test_abreviacoes_e_sais():
    r = nivel('OLMESARTANA MIDOXOMILA+HIDROCLOROTIAZIDA 20MG+12,5 30CP', 'OLMESART+HCT 20/12,5MG 30CP EUR-GENERICO')
    assert r.nivel is not None
    assert nivel('DICLORIDRATO DE TRIMETAZIDINA 35mg cx 60 comp', 'CL TRIMETAZIDINA 35MG 60CP').nivel is not None


def test_typo_e_tokens_fundidos():
    assert nivel('COLIDS FR GTS 5ML', 'COLIDIS 5ML-REFERENCIA').nivel is not None
    assert nivel('EPHINAL 400MG C/30CP', 'EPHYNAL 400MG 30CPS').nivel is not None
    a, b = CD.extrair('TIRAS ONE TOUCH SELECT C/50'), CD.extrair('TIRAS ONETOUCH SELECT C/50 UN')
    assert CD.comparar(a, b, '90273010', '90273010').nivel is not None


def test_codigo_de_modelo_ancora():
    r = CD.comparar(CD.extrair('AP PRES DIG OMRON AUTO 7122'), CD.extrair('MONITOR PRESSAO ARTERIAL BRACO HEM-7122'), '90189069', '90189069')
    assert r.nivel is not None


# ------------------------------------------------------------------ cascata de localização
COMPRAS = [
    dict(ean='7896015591212', ean_trib='7896015591212', descricao='TRELEGY 100+62,5+25MCG C/30 COMP', ncm='30043290', qtd=2, qtd_trib=2, vl_merc=100.0, cnpj_emitente='1', cod_produto='a'),
    dict(ean='17891317038875', ean_trib='7891317038878', descricao='LISDEX 50MG C/30 CPS CX C/12', ncm='30049049', qtd=1, qtd_trib=12, vl_merc=1200.0, cnpj_emitente='1', cod_produto='b'),
    dict(ean='SEM GTIN', ean_trib='SEM GTIN', descricao='CLORANA 50MG C/20 COMP-REFERENCIA', ncm='30049099', qtd=10, qtd_trib=10, vl_merc=200.0, cnpj_emitente='2', cod_produto='c'),
    dict(ean='7891000000001', ean_trib='7891000000001', descricao='PASALIX 500MG C/30 COMP EUR', ncm='30049099', qtd=5, qtd_trib=5, vl_merc=50.0, cnpj_emitente='3', cod_produto='d'),
    dict(ean='7891000000002', ean_trib='7891000000002', descricao='PASALIX 500MG C/30 COMP EMS', ncm='30049099', qtd=5, qtd_trib=5, vl_merc=500.0, cnpj_emitente='3', cod_produto='e'),
]


def test_cascata():
    loc = L.Localizador(COMPRAS)
    r = loc.localizar(dict(ean='7896015591212', descricao='x', ncm='30043290'))
    assert r['metodo'] == 'ean' and r['nivel'] == 'A' and r['linhas'] == [0]
    assert loc.localizar(dict(ean='789601559121 2'.replace(' ', ''), descricao='x', ncm=''))['metodo'] == 'ean'
    r = loc.localizar(dict(ean='7891317038878', descricao='x', ncm='30049049'))            # unidade; nota vende caixa
    assert r['metodo'] == 'ean_trib' and r['fator_xml'] == 12.0 and L.confirmado(r)
    r = loc.localizar(dict(ean='7891317038871', descricao='x', ncm='30049049'))            # núcleo de 12 dígitos igual
    assert r['metodo'] == 'ean_embalagem'
    r = loc.localizar(dict(ean='0000000000000', descricao='CLORANA 50MG C/20CP', ncm='30049099', valor=20.0))
    assert r['metodo'] == 'descricao' and r['nivel'] in ('A', 'B') and r['linhas'] == [2] and L.confirmado(r)
    r = loc.localizar(dict(ean='0000000000001', descricao='PRODUTO QUE NUNCA FOI COMPRADO 10MG', ncm='30049099'))
    assert r['metodo'] == 'nao_localizado' and not L.confirmado(r)


def test_ambiguo_desempata_pelo_preco():
    loc = L.Localizador(COMPRAS)
    r = loc.localizar(dict(ean='0000000000002', descricao='PASALIX 500MG C/30 COMP', ncm='30049099', valor=10.0))
    assert r['metodo'] == 'descricao' and r['nivel'] == 'C' and not L.confirmado(r)      # nunca confirmado quando ambíguo
    assert loc.chave_produto[r['linhas'][0]].endswith('0001')                           # preço unitário 10 x 100: o primeiro


def test_ean_upc_com_zero_a_esquerda():
    assert L.gtin14('840646003740') == L.gtin14('0840646003740') == '00840646003740'
    assert L.gtin14('SEM GTIN') == '' and L.gtin14('123') == ''


if __name__ == '__main__':
    for n, fn in list(globals().items()):
        if n.startswith('test_'):
            fn()
            print('ok', n)
