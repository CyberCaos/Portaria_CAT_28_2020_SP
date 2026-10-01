"""ItemFiscal (XML) -> linha canônica de compras (nomes em references/entradas-esperadas.md)."""
from decimal import Decimal

CAMPOS_COMPRAS = [
    'chave_nfe', 'numero', 'serie', 'data_emissao', 'n_item', 'cnpj_emitente', 'nome_emitente', 'uf_emitente',
    'crt_emitente', 'cnpj_destinatario', 'nome_destinatario', 'uf_destinatario', 'cod_produto', 'ean', 'ean_trib', 'descricao',
    'ncm', 'cest', 'cfop', 'unid_comercial', 'qtd', 'unid_trib', 'qtd_trib', 'vl_merc', 'frete', 'seguro',
    'outras_despesas', 'desconto', 'vl_contabil', 'cst', 'orig', 'vbc_st_ret', 'p_st', 'vicms_st_ret', 'vbc_fcp_st_ret',
    'vicms_substituto', 'vbc_st', 'vicms_st', 'p_icms_st', 'p_fcp_st', 'p_fcp_st_ret', 'vbc', 'vicms', 'vfcp_st', 'vfcp_st_ret', 'vbc_fcp_st', 'ref_nfe', 'data_saida_entrada', 'p_icms', 'p_red_bc', 'p_red_bc_st', 'tp_nf', 'fin_nfe', 'nat_op',
    'c_stat', 'protocolo', 'situacao', 'arquivo_xml',
]


def _f(v):
    return float(v) if isinstance(v, Decimal) else v


def linha_compra(i) -> dict:
    return {
        'chave_nfe': i.chave, 'numero': i.numero, 'serie': i.serie,
        'data_emissao': i.data_emissao.date() if i.data_emissao else None, 'n_item': i.sequencia,
        'cnpj_emitente': i.emitente_documento, 'nome_emitente': i.emitente_nome, 'uf_emitente': i.emitente_uf,
        'crt_emitente': i.crt_emitente, 'cnpj_destinatario': i.destinatario_documento,
        'nome_destinatario': i.destinatario_nome, 'uf_destinatario': i.destinatario_uf,
        'cod_produto': i.codigo_produto, 'ean': i.ean, 'ean_trib': i.ean_trib, 'descricao': i.descricao, 'ncm': i.ncm, 'cest': i.cest,
        'cfop': i.cfop, 'unid_comercial': i.unidade, 'qtd': _f(i.quantidade), 'unid_trib': i.unidade_trib,
        'qtd_trib': _f(i.quantidade_trib), 'vl_merc': _f(i.valor_item), 'frete': _f(i.frete), 'seguro': _f(i.seguro),
        'outras_despesas': _f(i.outras_despesas), 'desconto': _f(i.desconto), 'vl_contabil': _f(i.valor_contabil),
        'cst': i.cst_icms, 'orig': i.orig_icms, 'vbc_st_ret': _f(i.icms_st_retido_ant.base), 'p_st': _f(i.icms_st_retido_ant.aliquota),
        'vicms_st_ret': _f(i.icms_st_retido_ant.valor), 'vbc_fcp_st_ret': _f(i.fcp_st_retido_ant.base),
        'vicms_substituto': _f(i.v_icms_substituto), 'vbc_st': _f(i.icms_st.base), 'vicms_st': _f(i.icms_st.valor),
        'p_icms_st': _f(i.icms_st.aliquota), 'p_fcp_st': _f(i.p_fcp_st), 'p_fcp_st_ret': _f(i.fcp_st_retido_ant.aliquota),
        'vbc': _f(i.icms.base), 'vicms': _f(i.icms.valor), 'vfcp_st': _f(i.v_fcp_st), 'vfcp_st_ret': _f(i.fcp_st_retido_ant.valor),
        'vbc_fcp_st': _f(i.v_bc_fcp_st), 'ref_nfe': i.ref_nfe, 'data_saida_entrada': i.data_saida_entrada,
        'p_icms': _f(i.icms.aliquota), 'p_red_bc': _f(i.p_red_bc), 'p_red_bc_st': _f(i.p_red_bc_st),
        'tp_nf': i.tp_nf, 'fin_nfe': i.fin_nfe, 'nat_op': i.nat_op, 'c_stat': i.c_stat, 'protocolo': i.protocolo,
        'situacao': i.situacao, 'arquivo_xml': i.arquivo,
    }
