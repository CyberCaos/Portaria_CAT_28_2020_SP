"""Estruturas de estoque diferentes: identificação pela descrição, notas só de entrada, enquadramento do sorvete."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import compras as C  # noqa: E402
import enquadramento_auto as EA  # noqa: E402
import identificacao_estoque as IE  # noqa: E402
import localizar as L  # noqa: E402


def _nota(i, ean, desc, ncm='21050010', emitente='SORVETES ROCHINHA LTDA', **k):
    r = {c: '' for c in C.CAMPOS_COMPRAS}
    r.update(chave_nfe=str(i) * 44, n_item='1', cnpj_emitente='11111111000111', nome_emitente=emitente, cod_produto=f'P{i}', ean=ean,
             ean_trib=ean, descricao=desc, ncm=ncm, cest='2300100', unid_comercial='CX', qtd=10.0, qtd_trib=10.0, vl_merc=1500.0)
    r.update(k)
    return r


def _compras():
    return [
        _nota(1, '17891075060211', 'Sorvete KIBON Palito Tablito 24X72ML/59G', emitente='UNILEVER BRASIL LTDA'),
        _nota(2, '17891075060228', 'Sorvete KIBON Palito Brigadeiro 22X77ML/52G', emitente='UNILEVER BRASIL LTDA'),
        _nota(3, '17891075060235', 'PICOLE LIMAO CX14UN'),
        _nota(4, '17891075060242', 'PICOLE UVA CX14UN'),
    ]


def _estoque(desc):
    return dict(ean='', ncm='', cest='', cest_origem='', descricao=desc, valor=190.0, qtd=10.0)


def test_estoque_sem_ean_e_ncm_herda_da_nota_pela_descricao():
    compras = _compras()
    est = [_estoque('KIBON  PALITO  TABLITO 24X72ML'), _estoque('ROCHINHA PICOLE LIMÃO CX COM 14UN')]
    st = IE.enriquecer(est, L.Localizador(compras), compras)
    assert st['por_descricao'] == 2
    assert (est[0]['ean'], est[0]['ncm'], est[0]['cest']) == ('17891075060211', '21050010', '2300100')
    assert est[0]['ident_por'].startswith('descrição')
    assert est[1]['ean'] == '17891075060235'          # marca = fornecedor ("ROCHINHA" no nome do emitente) não atrapalha


def test_descricao_ambigua_ou_sem_nota_nao_identifica():
    compras = _compras()
    est = [_estoque('KIBON CORNETTO CHOCOMIX'), _estoque('PRODUTO QUE NAO EXISTE NAS NOTAS 10X10ML'),
           _estoque('KIBON PALITO 24X72ML')]            # só "palito" + embalagem: casa com Tablito e Brigadeiro (margem pequena)
    IE.enriquecer(est, L.Localizador(compras), compras)
    assert all(e['ident_por'] == 'nao_identificado' and not e['ncm'] for e in est)


def test_linha_do_estoque_completa_nao_e_alterada():
    compras = _compras()
    e = dict(_estoque('QUALQUER'), ean='7890000000015', ncm='21050010')
    IE.enriquecer([e], L.Localizador(compras), compras)
    assert e['ident_por'] == '' and e['ean'] == '7890000000015'


def test_so_notas_de_entrada_entram_como_compra(tmp_path):
    import csv
    import json
    import levantamento as LV
    rel = tmp_path / 'relatorio_parser'
    rel.mkdir()
    campos = C.CAMPOS_COMPRAS + ['papel_empresa']
    linhas = []
    for papel in ('entrada', 'saida', 'terceiros'):
        r = _nota({'entrada': 1, 'saida': 2, 'terceiros': 3}[papel], '17891075060211', 'X')
        r.update(papel_empresa=papel, qtd=1, qtd_trib=1, vl_merc=1)
        linhas.append(r)
    with open(rel / 'compras.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=';')
        w.writeheader()
        w.writerows(linhas)
    with open(rel / 'estoque.csv', 'w', newline='', encoding='utf-8-sig') as f:
        f.write('qtd;valor;valor_total;aliq_totalizador\n')
    (rel / 'intake_resumo.json').write_text('{}', encoding='utf-8')
    (tmp_path / 'cliente.json').write_text(json.dumps(dict(regime='RPA')), encoding='utf-8')
    compras, _, _, _, resumo = LV.carregar(str(tmp_path))
    assert [c['papel_empresa'] for c in compras] == ['entrada'] and resumo['itens_fora_das_compras'] == 2


def test_enquadramento_automatico_do_sorvete_art_39_xiv():
    c = dict(ncm='21050010', p_red_bc='33.33', p_red_bc_st='0', vbc_st='5035.20', uf_emitente='SP', uf_destinatario='SP',
             data_emissao='2026-05-10', p_icms='18', p_icms_st='0')
    r = EA.classificar(c, 'RPA')
    assert r['reducao'] == EA.NAO_APLICAVEL and r['dispositivo'] == 'RICMS/SP Anexo II art. 39 XIV' and not r['divergente']
    assert EA.classificar(dict(c, ncm='19019020'), 'RPA') is None                 # só o NCM do sorvete é identificação positiva
    assert EA.classificar(dict(c, uf_emitente='MG'), 'RPA') is None               # operação interestadual: análise
    assert EA.classificar(dict(c, p_red_bc='20'), 'RPA')['divergente']            # carga da nota != 12%: indício contrário


def test_de_para_informado_resolve_o_que_a_skill_nao_identificou(tmp_path):
    compras = _compras()
    est = [_estoque('KIBON CORNETTO CHOCOMIX')]
    IE.enriquecer(est, L.Localizador(compras), compras)
    assert est[0]['ident_por'] == 'nao_identificado'
    arq = IE.gravar_pendentes(str(tmp_path), est, {})
    assert arq and 'CORNETTO CHOCOMIX' in open(arq, encoding='utf-8-sig').read()
    with open(arq, 'w', encoding='utf-8-sig') as f:                        # o usuário (ou a análise) informa EAN e NCM
        f.write('descricao;melhor_candidato;similaridade;ean;ncm;cest;observacao\nKIBON CORNETTO CHOCOMIX;;;17891150065926;21050010;2300100;\n')
    est2 = [_estoque('KIBON CORNETTO CHOCOMIX')]
    IE.enriquecer(est2, L.Localizador(compras), compras, IE.carregar_de_para(str(tmp_path)))
    assert est2[0]['ean'] == '17891150065926' and est2[0]['ncm'] == '21050010' and 'de-para' in est2[0]['ident_por']
    assert IE.gravar_pendentes(str(tmp_path), est2, {}) is not None        # arquivo preservado
