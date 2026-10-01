"""Parser de NF-e (mod. 55) e NFC-e (mod. 65). Porte de NfeNfceParser.cs + extractors de imposto."""
import os
import xml.etree.ElementTree as ET
from typing import List, Optional

from . import xmlhelpers as X
from .modelos import NFE, NFCE, ItemFiscal, TributoValor

ZERO = X.Decimal(0)


def suporta(root: Optional[str], modelo: Optional[str]) -> bool:
    return root in ('nfeProc', 'NFe') and modelo in ('55', '65')


def _icms(icms: Optional[ET.Element]) -> dict:
    """Primeiro filho de <ICMS> (ICMS00, ICMS60, ICMSSN500, ICMSST...) -> campos normalizados."""
    node = next(iter(icms), None) if icms is not None else None
    if node is None:
        return dict(cst='', orig='', v_bc=ZERO, p_icms=ZERO, v_icms=ZERO, v_bc_st=ZERO, p_icms_st=ZERO, v_icms_st=ZERO,
                    st_ret=TributoValor(), fcp_ret=TributoValor(), p_red_bc=ZERO, p_red_bc_st=ZERO, v_subst=ZERO, p_fcp_st=ZERO, v_fcp_st=ZERO,
                    v_bc_fcp_st=ZERO)
    d = X.parse_dec
    return dict(
        cst=X.el(node, 'CST') or X.el(node, 'CSOSN') or '', orig=(X.el(node, 'orig') or '').strip(),
        v_bc=d(X.el(node, 'vBC')), p_icms=d(X.el(node, 'pICMS')), v_icms=d(X.el(node, 'vICMS')),
        v_bc_st=d(X.el(node, 'vBCST')), p_icms_st=d(X.el(node, 'pICMSST')), v_icms_st=d(X.el(node, 'vICMSST')),
        st_ret=TributoValor(d(X.el(node, 'vBCSTRet')), d(X.el(node, 'pST')), d(X.el(node, 'vICMSSTRet'))),
        fcp_ret=TributoValor(d(X.el(node, 'vBCFCPSTRet')), d(X.el(node, 'pFCPSTRet')), d(X.el(node, 'vFCPSTRet'))),
        p_red_bc=d(X.el(node, 'pRedBC')), p_red_bc_st=d(X.el(node, 'pRedBCST')), v_subst=d(X.el(node, 'vICMSSubstituto')),
        p_fcp_st=d(X.el(node, 'pFCPST')), v_fcp_st=d(X.el(node, 'vFCPST')), v_bc_fcp_st=d(X.el(node, 'vBCFCPST')))


def _ipi(imposto: Optional[ET.Element]) -> TributoValor:
    trib = X.child(X.child(imposto, 'IPI'), 'IPITrib')
    if trib is None:
        return TributoValor()
    d = X.parse_dec
    return TributoValor(d(X.el(trib, 'vBC')), d(X.el(trib, 'pIPI')), d(X.el(trib, 'vIPI')))


def _pis_cofins(grupo: Optional[ET.Element], tag_aliq: str, tag_valor: str) -> TributoValor:
    node = next(iter(grupo), None) if grupo is not None else None
    if node is None:
        return TributoValor()
    d = X.parse_dec
    return TributoValor(d(X.el(node, 'vBC')), d(X.el(node, tag_aliq)), d(X.el(node, tag_valor)))


def parse(root: ET.Element, nome_arquivo: str) -> List[ItemFiscal]:
    inf = X.descendant(root, 'infNFe')
    if inf is None:
        raise ValueError(f'infNFe não encontrado em {nome_arquivo}')
    d = X.parse_dec

    ide = X.child(inf, 'ide')
    modelo = X.el(ide, 'mod') or ''
    numero, serie = X.el(ide, 'nNF') or '', X.el(ide, 'serie') or ''
    data = X.parse_data(X.el(ide, 'dhEmi') or X.el(ide, 'dEmi'))

    id_attr = inf.get('Id', '')
    chave = id_attr[3:] if id_attr.startswith('NFe') else id_attr

    emit, dest = X.child(inf, 'emit'), X.child(inf, 'dest')
    emit_doc = X.el(emit, 'CNPJ') or X.el(emit, 'CPF') or ''
    dest_doc = X.el(dest, 'CNPJ') or X.el(dest, 'CPF') or ''

    # protocolo de autorização (só existe em nfeProc)
    prot = X.descendant(X.descendant(root, 'protNFe'), 'infProt')

    itens = []
    for det in X.children(inf, 'det'):
        prod, imposto = X.child(det, 'prod'), X.child(det, 'imposto')
        try:
            seq = int(det.get('nItem', ''))
        except ValueError:
            seq = 0
        ic = _icms(X.child(imposto, 'ICMS'))
        ipi = _ipi(imposto)
        v_prod, v_frete, v_seg = d(X.el(prod, 'vProd')), d(X.el(prod, 'vFrete')), d(X.el(prod, 'vSeg'))
        v_outro, v_desc = d(X.el(prod, 'vOutro')), d(X.el(prod, 'vDesc'))
        v_contabil = v_prod + v_frete + v_seg + v_outro + ic['v_icms_st'] + ipi.valor - v_desc
        itens.append(ItemFiscal(
            arquivo=nome_arquivo, chave=chave, modelo=NFCE if modelo == '65' else NFE, numero=numero, serie=serie,
            data_emissao=data, sequencia=seq,
            emitente_documento=emit_doc, emitente_nome=X.el(emit, 'xNome') or '',
            destinatario_documento=dest_doc, destinatario_nome=X.el(dest, 'xNome') or '',
            codigo_produto=X.el(prod, 'cProd') or '', ean=X.el(prod, 'cEAN') or '', ncm=X.el(prod, 'NCM') or '',
            cest=X.el(prod, 'CEST') or '', descricao=X.el(prod, 'xProd') or '', cfop=X.el(prod, 'CFOP') or '',
            unidade=X.el(prod, 'uCom') or '', quantidade=d(X.el(prod, 'qCom')), valor_item=v_prod, frete=v_frete,
            seguro=v_seg, outras_despesas=v_outro, desconto=v_desc, valor_contabil=v_contabil,
            icms=TributoValor(ic['v_bc'], ic['p_icms'], ic['v_icms']),
            icms_st=TributoValor(ic['v_bc_st'], ic['p_icms_st'], ic['v_icms_st']),
            ipi=ipi, pis=_pis_cofins(X.child(imposto, 'PIS'), 'pPIS', 'vPIS'),
            cofins=_pis_cofins(X.child(imposto, 'COFINS'), 'pCOFINS', 'vCOFINS'),
            icms_st_retido_ant=ic['st_ret'], fcp_st_retido_ant=ic['fcp_ret'], cst_icms=ic['cst'], orig_icms=ic['orig'],
            p_red_bc=ic['p_red_bc'], p_red_bc_st=ic['p_red_bc_st'],
            emitente_uf=X.uf(emit) or '', destinatario_uf=X.uf(dest) or '',
            crt_emitente=(X.el(emit, 'CRT') or '').strip(),
            unidade_trib=X.el(prod, 'uTrib') or '', quantidade_trib=d(X.el(prod, 'qTrib')),
            v_icms_substituto=ic['v_subst'],
            tp_nf=(X.el(ide, 'tpNF') or '').strip(), fin_nfe=(X.el(ide, 'finNFe') or '').strip(),
            data_saida_entrada=((X.el(ide, 'dhSaiEnt') or X.el(ide, 'dSaiEnt') or '').strip()[:10]),
            nat_op=X.el(ide, 'natOp') or '',
            c_stat=(X.el(prot, 'cStat') or '').strip(), protocolo=(X.el(prot, 'nProt') or '').strip(),
            tp_amb=(X.el(ide, 'tpAmb') or '').strip(),
            indicador_ie_dest=(X.el(dest, 'indIEDest') or '').strip(),
            ean_trib=(X.el(prod, 'cEANTrib') or '').strip(), p_fcp_st=ic['p_fcp_st'], v_fcp_st=ic['v_fcp_st'], v_bc_fcp_st=ic['v_bc_fcp_st'],
            ref_nfe='|'.join(sorted({(e.text or '').strip() for e in (ide.iter() if ide is not None else [])
                                     if e.tag.split('}')[-1] == 'refNFe' and (e.text or '').strip()}))))
    return itens


def extrair_evento_cancelamento(root: ET.Element, nome_arquivo: str):
    """procEventoNFe com tpEvento 110111 -> EventoCancelamento; outro tipo -> None; infEvento/chNFe ausente -> erro."""
    from .modelos import EventoCancelamento
    inf = X.descendant(root, 'infEvento')
    if inf is None:
        raise ValueError(f'infEvento não encontrado em {nome_arquivo}')
    if (X.el(inf, 'tpEvento') or '') != '110111':
        return None
    ch = (X.el(inf, 'chNFe') or '').strip()
    if not ch:
        raise ValueError(f'chNFe ausente no evento de cancelamento em {nome_arquivo}')
    return EventoCancelamento(ch, X.parse_data(X.el(inf, 'dhEvento')), nome_arquivo)
