"""Regressões dos casos identificados na revisão fiscal."""
import sys
from pathlib import Path
from datetime import date
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import credito as C
import formulas as F
import alocacao as A
import levantamento as L
from test_credito import linha
from test_alocacao import nf, FATOR1


def test_rpa_sem_teto():
    r = C.calcular_linha('RPA', linha(15000, 10000, st_cobrado=900))
    assert r['credito'] == 2700


def test_rpa_reducao_nao_alcanca_consumidor():
    r = C.calcular_linha('RPA', linha(1000, 700, p_red=50,
        reducao=F.RED_NAO_APLICAVEL_CF))
    assert r['credito'] == 180


def test_sn_distingue_alcance_da_reducao():
    assert C.calcular_linha('SN', linha(1000, 700, p_red=50))['status'] == 'dados_fiscais_pendentes'
    a = C.calcular_linha('SN', linha(1000, 700, p_red=50, reducao=F.RED_APLICAVEL_CF))
    b = C.calcular_linha('SN', linha(1000, 700, p_red=50, reducao=F.RED_NAO_APLICAVEL_CF))
    assert (a['credito'], b['credito']) == (27, 117)


def test_crt2_e_desconhecido():
    assert C.calcular_linha('RPA', linha(1000, 700, crt_emitente='2'))['credito'] == 180
    for crt in (None, '', '9'):                                    # sem CST válido, o CRT decide; CRT inválido = pendência
        assert C.calcular_linha('RPA', linha(1000, 700, cst='', crt_emitente=crt))['status'] == 'dados_fiscais_pendentes'
        assert C.calcular_linha('RPA', linha(1000, 700, crt_emitente=crt))['credito'] == 180   # CST 10 basta: RPA


def test_responsavel_pela_base_presente():
    assert C._responsavel(dict(cst='90', bc_st_unit=5.0, bc_st_ret_unit=0.0)) == F.RET_FORNECEDOR     # CST 90 com vBCST
    assert C._responsavel(dict(cst='900', bc_st_unit=0.0, bc_st_ret_unit=3.0)) == F.RET_SUBST_ANTERIOR
    assert C._responsavel(dict(cst='60')) == F.RET_SUBST_ANTERIOR and C._responsavel(dict(cst='90')) == F.RET_FORNECEDOR


def test_reducao_em_pred_bc_com_vbcst_reduzido_fica_pendente():
    compras = [nf('2025-05-01', qtd=1, vl=34.52, cst='70', vbc_st=17.28, p_icms_st=18.0, p_red_bc=61.11, p_red_bc_st=0.0)]
    r = A.alocar(dict(qtd=1, aliq_totalizador=18), [dict(origem='ean', confirmado=True, linhas=[0])], compras, date(2026, 1, 1), {}, FATOR1)
    l = r['linhas'][0]
    assert l['p_red_efetivo'] == 61.11 and l['p_red_origem'].startswith('pRedBC')
    res = C.calcular_linha('SN', l)
    assert res['status'] == 'dados_fiscais_pendentes' and 'pRedBC' in res['alertas'][0]      # não calcula como "sem redução"
    l['reducao'] = F.RED_NAO_APLICAVEL_CF                          # com o enquadramento informado, calcula
    assert C.calcular_linha('SN', l)['credito'] == round((17.28 - 34.52 * (1 - 0.6111)) * 0.18, 2)


def test_sn_interestadual_aliquota_pela_origem():
    l = linha(1000, 700, crt_emitente='1', cst='201', uf_emitente='MG')
    r = C.calcular_linha('RPA', l)                                   # sem pICMS nem origem: 12% (destino SP), com alerta
    assert r['credito'] == 96 and any('12%' in a for a in r['alertas'])
    l['orig'] = '1'                                                  # importado: 4% (Res. SF 13/2012)
    assert C.calcular_linha('RPA', l)['credito'] == round(1000 * 0.18 - 700 * 0.04, 2)
    l['aliquota_interestadual'] = 7                                  # informada prevalece
    assert C.calcular_linha('RPA', l)['credito'] == round(1000 * 0.18 - 700 * 0.07, 2)


def test_antecipacao_pelo_adquirente_com_bc_informada():
    compras = [nf('2025-05-01', qtd=2, vl=100.0, cst='00', uf_emitente='PR', bc_st_antecipacao=150.0)]
    r = A.alocar(dict(qtd=2, aliq_totalizador=18), [dict(origem='ean', confirmado=True, linhas=[0])], compras, date(2026, 1, 1), {}, FATOR1)
    l = r['linhas'][0]
    assert l['antecipacao'] and not l['sem_base_st'] and abs(l['bc_st_usada'] - 150.0) < 1e-9
    res = C.calcular_linha('RPA', dict(l, crt_emitente='3'))        # RPA/RPA antecipação: BC ST x alíquota
    assert res['credito'] == 27.0 and 'antecip' in res['linha_tabela'] and any('antecipação' in a for a in res['alertas'])


def test_cronologia_entre_grupos_e_sem_duplicacao():
    compras = [nf('2025-01-01'), nf('2025-12-01')]
    grupos = [dict(origem='ean', confirmado=True, linhas=[0]),
              dict(origem='descricao B', confirmado=True, linhas=[1, 0])]
    r = A.alocar(dict(qtd=15, aliq_totalizador=18), grupos, compras, date(2026, 1, 1), {}, FATOR1)
    assert [(l['linha_idx'], l['qtd_usada_estoque']) for l in r['linhas']] == [(1, 10), (0, 5)]


def test_orquestrador_busca_nota_recente_mesmo_com_ean_suficiente(monkeypatch):
    compras = [nf('2025-01-01'), nf('2025-12-01')]
    class Loc:
        chave_produto = {0: 'antigo', 1: 'novo'}
        def por_descricao(self, item, excluir):
            if 'novo' in excluir:
                return dict(metodo='nao_localizado')
            return dict(metodo='descricao', nivel='B', ambiguo=False, chave_produto='novo', linhas=[1])
    monkeypatch.setattr(L.F, 'fator_linha', FATOR1)
    r = L._alocar_item(dict(qtd=5, ean='1', aliq_totalizador=18),
        dict(data_revogacao=date(2026, 1, 1)),
        dict(metodo='ean', nivel='A', linhas=[0]), Loc(), compras, {}, True)
    assert [l['linha_idx'] for l in r['linhas']] == [1]


def test_consolidacao_valor_liquido():
    ls = [linha(100, 60, vl_bruto=90)]
    c = C.consolidar_item(ls, [C.calcular_linha('SN', ls[0])])
    assert c['total_vl'] == 60


# ---------------------------------------------------------------- revisão completa (30/09/2026)


def test_antecipacao_interna_fornecedor_sn_conservadora():
    r = F.credito_item(regime_detentor=F.RPA, regime_fornecedor=F.SN, responsavel=F.ANTEC_ADQUIRENTE, operacao=F.INTERNA,
                       bc_st=1000, vl_merc=700, aliq_interna=0.18)
    assert r.credito == 54.0 and r.analogia and 'retenção interna' in r.linha


def test_vprod_alternativo_so_quando_a_formula_usa_vlmerc():
    r = C.calcular_linha('RPA', linha(1000, 600, vl_bruto=700))                    # RPA/RPA: BC ST x alíquota, sem VlMerc
    assert r['alt_vprod'] is None and not any('vProd' in a for a in r['alertas'])
    r = C.calcular_linha('SN', linha(1000, 600, vl_bruto=700))
    assert r['alt_vprod'] == 54.0 and any('vProd' in a for a in r['alertas'])


def test_levantamento_exige_regime_e_colunas_fiscais(tmp_path):
    import json, csv as _csv, pytest
    rel = tmp_path / 'relatorio_parser'
    rel.mkdir()
    with open(rel / 'compras.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = _csv.writer(f, delimiter=';'); w.writerow(['chave_nfe', 'qtd']); w.writerow(['X', '1'])
    with open(rel / 'estoque.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = _csv.writer(f, delimiter=';'); w.writerow(['data_posicao', 'ean', 'qtd', 'valor', 'valor_total', 'aliq_totalizador'])
    (rel / 'intake_resumo.json').write_text('{}', encoding='utf-8')
    (tmp_path / 'cliente.json').write_text(json.dumps(dict(cliente='X', cnpj='1', regime='SN')), encoding='utf-8')
    with pytest.raises(ValueError, match='colunas fiscais'):
        L.levantar(str(tmp_path))
    with open(rel / 'compras.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = _csv.writer(f, delimiter=';'); w.writerow(['chave_nfe', 'qtd'] + list(L.OBRIGATORIAS_COMPRAS)); w.writerow(['X', '1'] + [''] * len(L.OBRIGATORIAS_COMPRAS))
    (tmp_path / 'cliente.json').write_text(json.dumps(dict(cliente='X', cnpj='1', regime='não informado')), encoding='utf-8')
    with pytest.raises(ValueError, match='Regime do detentor'):
        L.levantar(str(tmp_path))


def test_vlmerc_zero_fica_pendente_quando_a_formula_usa_vlmerc():
    assert C.calcular_linha('SN', linha(150.0, 0.0))['status'] == 'dados_fiscais_pendentes'
    assert C.calcular_linha('RPA', linha(150.0, 0.0))['credito'] == 27.0          # RPA/RPA não usa VlMerc


# ---------------------------------------------------------------- revisão fiscal de 01/10/2026: definitivo x interpretativo
def test_regime_do_fornecedor_conflito_cst_crt_fica_interpretativo():
    assert C._regime_fornecedor('10', '3') == (F.RPA, '') and C._regime_fornecedor('60', '2') == (F.RPA, '')
    assert C._regime_fornecedor('500', '1') == (F.SN, '') and C._regime_fornecedor('201', None) == (F.SN, '')
    reg, conflito = C._regime_fornecedor('102', '3')
    assert reg == F.SN and conflito
    r = C.calcular_linha('RPA', linha(1000, 700, cst='201', crt_emitente='3'))
    assert r['credito'] == 54.0 and r['classe'] == 'interpretativo' and any('conflito' in m for m in r['motivos'])


def test_aliquota_presumida_18_nao_e_definitiva():
    assert A.aliquota_st(nf('2025-01-01'), 0.0) == (18.0, A.ORIGEM_ALIQ_PADRAO)
    r = C.calcular_linha('SN', linha(150.0, 100.0, aliq=18.0, aliquota_origem=A.ORIGEM_ALIQ_PADRAO))
    assert r['credito'] == 9.0 and r['classe'] == 'interpretativo' and any('presumida' in m for m in r['motivos'])


def test_aliquota_interestadual_sem_origem_nao_e_definitiva():
    l = linha(1000, 700, crt_emitente='1', cst='201', uf_emitente='MG')
    r = C.calcular_linha('RPA', l)
    assert r['credito'] == 96.0 and r['classe'] == 'interpretativo'
    r = C.calcular_linha('RPA', dict(l, orig='0'))                   # origem informada: Res. SF 22/1989 fundamenta os 12%
    assert r['credito'] == 96.0 and r['classe'] == 'definitivo'


def test_percentual_legal_divergente_fica_interpretativo_e_exportado():
    l = linha(150.0, 100.0, p_red=33.33, reducao=F.RED_APLICAVEL_CF, cst='70', carga_legal=7.0, enq_fonte='automatico',
              enq_dispositivo='RICMS/SP Anexo II art. 3º XXIV')
    r = C.calcular_linha('RPA', l)
    assert r['credito'] == round(150 * (7 / 18) * 0.18, 2) and r['classe'] == 'interpretativo'
    assert abs(r['p_red_usado'] - 61.1111) < 0.001 and r['p_red_origem_usado'].startswith('legal')


def test_analogia_fica_fora_do_definitivo():
    r = C.calcular_linha('RPA', linha(bc=1000, vl_liq=700, cst='60'))
    assert r['credito'] == 180.0 and r['classe'] == 'interpretativo' and any('analogia' in m for m in r['motivos'])


# ---------------------------------------------------------------- critérios de evidência (revisão fiscal, 2ª rodada)
EVID = dict(enq_fonte='analise', enq_dispositivo='RICMS/SP Anexo II art. 3º XXIV', enq_evid_ok=True)


def test_enquadramento_nao_alcanca_nota_sem_reducao_do_mesmo_produto():
    compras = [dict(ean='7891000000001', cest='', ncm='30049099', p_red_bc=61.11, p_red_bc_st=0.0, vbc_st=17.28),
               dict(ean='7891000000001', cest='', ncm='30049099', p_red_bc=0.0, p_red_bc_st=0.0, vbc_st=0.0)]
    n = L._aplicar_enquadramento(compras, {'EAN': {'07891000000001': (F.RED_NAO_APLICAVEL_CF, None, 'usuario', '', True, '')}})
    assert n == 1 and compras[0]['reducao'] == F.RED_NAO_APLICAVEL_CF and compras[0]['_enq_evid_ok'] and 'reducao' not in compras[1]


def test_analise_com_evidencia_completa_e_definitiva_sem_confirmacao_humana():
    """Critério é a evidência, não quem analisou: análise com GTIN/registro sanitário, apresentação e vigência conferidas = definitivo."""
    linha_arq = dict(reducao='aplicavel', dispositivo='RICMS/SP Anexo II art. 3º XXIV', evidencia_tipo='gtin_registro_sanitario',
                     evidencia_fonte='ANVISA reg. 1.0000.0000 (paracetamol 750 mg)', apresentacao_confirmada='sim', vigencia_condicoes='sim')
    assert L._evidencia_ok(linha_arq) == (True, '')
    ok, falta = L._evidencia_ok(dict(linha_arq, evidencia_fonte='', apresentacao_confirmada=''))
    assert not ok and 'fonte' in falta and 'apresentação' in falta
    base = dict(p_red=50, reducao=F.RED_APLICAVEL_CF, cst='70')
    assert C.calcular_linha('SN', linha(1000, 700, **base, **EVID))['classe'] == 'definitivo'
    r = C.calcular_linha('SN', linha(1000, 700, **base, **dict(EVID, enq_evid_ok=False, enq_evid_falta='fonte da evidência')))
    assert r['classe'] == 'interpretativo' and any('evidência do enquadramento incompleta' in m for m in r['motivos'])


def test_anexo_v_usa_a_formula_do_enquadramento_e_so_diagnostica_o_st():
    base = dict(p_red=50, reducao=F.RED_APLICAVEL_CF, cst='70', bc_linha=1000.0, vl_liq_linha=700.0, st_linha=117.0, proprio_linha=0.0)
    r = C.calcular_linha('SN', linha(1000, 700, **base, **EVID))
    assert r['credito'] == 27.0 and r['classe'] == 'definitivo' and any('reproduziria' in a for a in r['alertas'])


def test_rpa_base_que_parece_reduzida_fica_interpretativa_com_alternativa():
    l = linha(1000.0, 700.0, p_red=50, reducao=F.RED_APLICAVEL_CF, cst='70', bc_linha=1000.0, vl_liq_linha=700.0, st_linha=120.0,
              proprio_linha=60.0, **EVID)
    r = C.calcular_linha('RPA', l)
    assert r['credito'] == 90.0 and r['classe'] == 'interpretativo' and list(r['alternativas'].values()) == [180.0]


def test_reducao_da_operacao_propria_nao_vai_para_a_formula_sem_fundamento():
    l = linha(1000.0, 700.0, cst='70', p_red_bc_st=0.0, p_red_bc=50.0, p_red_efetivo=50.0, reducao=F.RED_NAO_APLICAVEL_CF, **EVID)
    r = C.calcular_linha('SN', l)
    assert r['classe'] == 'interpretativo' and any('operação própria' in m for m in r['motivos'])


def test_linha_reproduzivel_pelos_parametros_exportados():
    l = linha(150.0, 100.0, p_red=33.33, reducao=F.RED_APLICAVEL_CF, cst='70', carga_legal=7.0, **EVID)
    r = C.calcular_linha('SN', l)
    p = r['p_red_usado'] / 100
    assert r['credito'] == round((150.0 - 100.0) * (1 - p) * r['aliquota_usada'] / 100, 2)


def test_parcelas_rpa_nunca_negativas():
    linhas = [dict(linha(1, 0), confirmado=True, chave_nfe='K', n_item='1', qtd_nf=1.0, unid_nf='UN', fator=1.0, qtd_usada_estoque=1.0,
                   desconto_usado=0.0, linha_idx=0)]
    itens = [('pos', dict(ean='1', cod_produto='1', ncm='30049099', cest='1300100', descricao='PRODUTO 10MG COMP', valor_total=1.0,
                          cest_origem='nfe_ean'),
              dict(data_revogacao=date(2026, 1, 1), anexo='IX', item='1'), dict(qtd=1), linhas, 0.0)]
    cred = L._aplicar_credito(itens, 'RPA', [])
    vals = [c[2] for c in cred['comp']]
    assert len(vals) == 12 and min(vals) >= 0 and round(sum(vals), 2) == cred['total'] == 0.18


def test_documento_sem_protocolo_interpretativo_e_janela_so_prioriza():
    assert C.calcular_linha('SN', linha(1000, 700, sem_protocolo=True))['classe'] == 'interpretativo'
    assert C.calcular_linha('SN', linha(1000, 700, revisar_entrada=True))['classe'] == 'definitivo'      # prioridade, não conformidade
    assert C.calcular_linha('SN', linha(1000, 700))['classe'] == 'definitivo'


def test_evidencia_de_entrada_e_entrada_registrada_na_vigencia():
    assert A._evidencia_entrada(dict(data_saida_entrada='2025-12-30')).startswith('dhSaiEnt do emitente')
    assert 'não comprova' in A._evidencia_entrada(dict(data_saida_entrada='2025-12-30'))
    assert A._evidencia_entrada(dict(_data_entrada='2025-12-29', _origem_entrada='EFD C100')).startswith('registro de entrada')
    ok, motivo = A.elegivel(nf('2025-12-30', _data_entrada='2026-01-02'), date(2026, 1, 1))
    assert not ok and 'entrada registrada na vigência' in motivo
    assert A.elegivel(nf('2025-12-30', _data_entrada='2025-12-31'), date(2026, 1, 1))[0]


def test_nf_complementar_incorporada_ao_item_original():
    orig = dict(chave_nfe='A' * 44, n_item='1', cod_produto='P1', ean='7891000000001', fin_nfe='1', vbc_st=100.0, vicms_st=8.0, vl_merc=80.0)
    comp = dict(chave_nfe='B' * 44, n_item='1', cod_produto='P1', ean='7891000000001', fin_nfe='2', ref_nfe='A' * 44, vbc_st=20.0, vicms_st=3.6,
                vl_merc=0.0, qtd=0)
    r = L._incorporar_complementares([orig, comp])
    assert r == dict(incorporadas=1, sem_vinculo=0) and orig['vbc_st'] == 120.0 and orig['vicms_st'] == 11.6 and orig['_complementada']
    assert not A.elegivel(dict(comp, data_emissao='2025-05-01', situacao='Normal', c_stat='100', qtd=1, cfop='5403'), date(2026, 1, 1))[0]
    orfa = dict(comp, ref_nfe='C' * 44)
    outra = dict(orig, chave_nfe='C' * 44, cod_produto='X9', ean='', n_item='7')
    assert L._incorporar_complementares([outra, orfa])['sem_vinculo'] == 1 and outra['_tem_complementar']


def test_fcp_com_base_propria_e_calculado_em_cada_base():
    """ICMS 18% sobre a BC ST (1000) e FCP 2% sobre a BC do FCP (800); Anexo IV, fornecedor RPA: 1000 x 18% + 800 x 2% = 196."""
    l = linha(1000.0, 700.0, aliq=20.0, fcp_base_diverge=True, p_fcp=2.0, bc_fcp_usada=800.0)
    r = C.calcular_linha('RPA', l)
    assert r['credito'] == 196.0 and r['classe'] == 'interpretativo' and list(r['alternativas'].values()) == [200.0]


def test_identidade_da_mercadoria_contra_a_descricao_legal():
    import identidade_cat68 as ID
    med = ID.avaliar(dict(descricao='LOSARTANA 50MG C/30 COMP', ncm='30049069', cest='', cest_origem='nao_encontrado'), 'IX', '4')
    assert med['confirmada'] and med['situacao_cest'] == 'ausente'                        # sem CEST, descrição e NCM resolvem
    sorvete = ID.avaliar(dict(descricao='ARTROGEN PLUS D po 30 saches', ncm='21069090', cest='1700100', cest_origem='nfe_ean'), 'IV', '2')
    assert not sorvete['confirmada'] and 'descrição legal' in sorvete['motivo']          # suplemento não é "preparado para sorvete"
    contra = ID.avaliar(dict(descricao='DIPIRONA 500MG 10 COMP', ncm='30049099', cest='2800100', cest_origem='nfe_ean'), 'IX', '4')
    assert not contra['confirmada'] and contra['situacao_cest'] == 'contradiz'
    xampu = ID.avaliar(dict(descricao='SHAMPOO ELSEVE 400ML', ncm='33051000', cest='', cest_origem=''), 'XI', '17')
    assert xampu['confirmada']


def test_identidade_decidida_pela_analise_com_evidencia():
    e = dict(ean='7890000000001', descricao='PAMPERS CONFORT SEC M C/70', ncm='96190000', cest='', cest_origem='')
    c = dict(anexo='XI', item='52')
    assert L._triagem_confirmada(e, c)[0] == 'nao_confirmada'                           # marca sozinha: análise
    regra = {('07890000000001', 'XI', '52'): dict(confirmado='sim', evidencia_tipo='documentacao_fabricante',
                                                   evidencia_fonte='ficha técnica P&G: fralda descartável infantil', apresentacao_confirmada='sim')}
    assert L._triagem_confirmada(e, c, regra)[0] == 'confirmada'
    regra_nao = {('07890000000001', 'XI', '52'): dict(confirmado='nao', justificativa='é lenço umedecido, não fralda')}
    assert L._triagem_confirmada(e, c, regra_nao)[0] == 'excluida'
