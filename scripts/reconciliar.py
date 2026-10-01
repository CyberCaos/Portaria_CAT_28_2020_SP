"""Ponte de reconciliação entre o resultado anterior (antes da revisão fiscal de 01/10/2026) e o atual, por produto e motivo.

    python scripts/reconciliar.py <pasta_do_cliente> [--anterior-total 10574.81]

Como o resultado anterior foi sobrescrito, a ponte RECALCULA as duas versões sobre os mesmos dados, em cópias temporárias da pasta
do cliente: a atual (código de produção) e a anterior (as regras revogadas reaplicadas só aqui, por substituição em memória):
  R1 enquadramento automático amplo: carga 7% + NCM de medicamento (inclusive só pela marca), redução de outra UF = não aplicável,
     arts. 34 e 39 pela carga de 12%;
  R2 Anexo V: a fórmula que reproduzia o ICMS-ST cobrado na nota (prova), em vez da fórmula do enquadramento;
  R3 Anexo IV: base de ST "já reduzida" sem reaplicar a redução;
  R4 FCP com base própria: alíquota única sobre a BC ST;
  R5 sem separação de classes: todo valor calculado entrava no total.
Se o total anterior recalculado bater com o informado (--anterior-total), a ponte está provada. Saída:
<cliente>/relatorio_parser/ponte_reconciliacao.xlsx (Resumo, Por motivo, Por produto) e o resumo no terminal.
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credito as CR  # noqa: E402
import enquadramento_auto as EA  # noqa: E402
import formulas as F  # noqa: E402
import levantamento as LV  # noqa: E402

_NCM_ART3 = '0201|0202|0203|0207|0302|0303|0304|0402|0405|09012|1001|1101|1507|1508|1511|1512|1514|1515|1517|170111|170199|190120|190211|190219|190520|190531|190590|2201'.split('|')
_NCM_ART34 = '481810|481840|560110|3303|3304|3305|3307|3401|330610|330620|481820|481830|96032|48189090'.split('|')
_NCM_ART39_AUTO, _NCM_ART39_EXC = ['03', '04', '07', '08', '20', '22029900'], ['04011010', '04012010', '04031000', '04039000', '20091']


def _dig(v):
    return re.sub(r'\D', '', str(v or ''))


def classificar_anterior(c, regime=''):
    """R1: o enquadramento automático da versão anterior (carga coincidente e marca bastavam)."""
    p_st, p_prop = float(c.get('p_red_bc_st') or 0), float(c.get('p_red_bc') or 0)
    if not (p_st > 0 or (p_prop > 0 and float(c.get('vbc_st') or 0) > 0)):
        return None
    uf_e, uf_d, ncm = str(c.get('uf_emitente') or ''), str(c.get('uf_destinatario') or ''), _dig(c.get('ncm'))
    if uf_e and uf_d and uf_e != uf_d:
        return dict(reducao=EA.NAO_APLICAVEL, dispositivo='UF de origem', carga=None, divergente=False, justificativa='regra anterior') if p_st == 0 else None
    p = p_st if p_st > 0 else p_prop
    aliq = float(c.get('p_icms') or 0) or float(c.get('p_icms_st') or 0)
    if aliq <= 0:
        return None
    carga = aliq * (1 - p / 100)
    perto = lambda alvo: abs(carga - alvo) <= EA.TOLERANCIA_CARGA
    d = EA._norm(c.get('descricao', ''))
    if perto(7) and ncm.startswith(('3003', '3004', '3006')):
        return dict(reducao=EA.APLICAVEL, dispositivo=EA.DISPOSITIVO_XXIV, carga=7.0, divergente=False, justificativa='regra anterior')
    if perto(7) and ncm.startswith(tuple(_NCM_ART3)):
        return dict(reducao=EA.APLICAVEL, dispositivo='art. 3º', carga=7.0, divergente=False, justificativa='regra anterior')
    if perto(7) and ncm.startswith(('1006', '071333')) and re.search(r'ARROZ|FEIJAO', d):
        return dict(reducao=EA.NAO_APLICAVEL, dispositivo='art. 3º XXVI/XXVII', carga=7.0, divergente=False, justificativa='regra anterior')
    if perto(12) and ncm.startswith(tuple(_NCM_ART34)):
        return dict(reducao=EA.NAO_APLICAVEL, dispositivo='art. 34', carga=12.0, divergente=False, justificativa='regra anterior')
    if perto(12) and ncm.startswith(tuple(_NCM_ART39_AUTO)) and not ncm.startswith(tuple(_NCM_ART39_EXC)):
        return dict(reducao=EA.NAO_APLICAVEL, dispositivo='art. 39', carga=12.0, divergente=False, justificativa='regra anterior')
    if ncm.startswith(EA.NCM_MEDICAMENTO) and EA.principios_xxiv(c.get('descricao', '')):
        return dict(reducao=EA.APLICAVEL, dispositivo=EA.DISPOSITIVO_XXIV, carga=7.0, divergente=False, justificativa='regra anterior')
    return None


_calc_atual = CR.calcular_linha


def calcular_anterior(regime, l, valor_mercadoria='liquido'):
    """R2 a R5 sobre o cálculo atual: troca o valor pela leitura anterior e marca a linha como definitiva (sem classes)."""
    r = _calc_atual(regime, dict(l, enq_evid_ok=True), valor_mercadoria)
    if r['credito'] is None:
        return r
    regra = ''
    if any(a.startswith('diagnóstico Anexo V: a fórmula do rótulo') for a in r['alertas']):
        outra = F.RED_NAO_APLICAVEL_CF if l.get('reducao') == F.RED_APLICAVEL_CF else F.RED_APLICAVEL_CF
        r2 = _calc_atual(regime, dict(l, reducao=outra, enq_evid_ok=True), valor_mercadoria)
        r = dict(r, credito=r2['credito'])
        regra = 'R2'
    alts = r.get('alternativas') or {}
    if 'sem reaplicar a redução (BC ST x alíquota)' in alts:
        r = dict(r, credito=alts['sem reaplicar a redução (BC ST x alíquota)'])
        regra = 'R3'
    if 'alíquota única (ICMS + FCP) sobre a BC ST' in alts:
        r = dict(r, credito=alts['alíquota única (ICMS + FCP) sobre a BC ST'])
        regra = 'R4'
    return dict(r, classe='definitivo', motivos=[], regra_anterior=regra)


def _rodar(pasta, anterior):
    tmp = tempfile.mkdtemp()
    try:
        dst = os.path.join(tmp, 'cliente')
        shutil.copytree(pasta, dst, ignore=shutil.ignore_patterns('*.pdf', 'historico'))
        orig = (LV.EA.classificar, LV.CR.calcular_linha, LV._triagem_confirmada)
        if anterior:
            LV.EA.classificar = classificar_anterior
            LV.CR.calcular_linha = calcular_anterior
            LV._triagem_confirmada = lambda e, c, regras_ident=None: ('confirmada', '', dict(evidencias=[], descricao_legal=''))
        try:
            r = LV.levantar(dst)
        finally:
            LV.EA.classificar, LV.CR.calcular_linha, LV._triagem_confirmada = orig
        import pandas as pd
        xl = pd.ExcelFile(os.path.join(dst, 'resultado_levantamento.xlsx'))
        rp, a2 = xl.parse('Resumo por produto'), xl.parse('Anexo II (notas selecionadas)')
        return r, rp, a2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def reconciliar(pasta, anterior_total=None):
    import pandas as pd
    r_at, rp_at, a2_at = _rodar(pasta, anterior=False)
    r_an, rp_an, a2_an = _rodar(pasta, anterior=True)
    chave = ['EAN', 'Data de revogação', 'Descrição']
    at = rp_at.assign(atual=rp_at['Total crédito (item 16)'].fillna(0))
    an = rp_an.assign(anterior=rp_an['Total crédito (item 16)'].fillna(0))
    m = at[chave + ['atual', 'Situação do crédito', 'Observações do cálculo']].merge(an[chave + ['anterior']], on=chave, how='outer').fillna(
        {'atual': 0, 'anterior': 0})
    m['diferenca'] = (m['atual'] - m['anterior']).round(2)
    # motivo da diferença, pelas linhas do Anexo II das duas versões
    k = ['EAN', 'Data de revogação', 'chave NFe', 'no. Item']
    la = a2_at[k + ['crédito', 'Alertas']].rename(columns={'crédito': 'cred_atual'})
    lb = a2_an[k + ['crédito']].rename(columns={'crédito': 'cred_anterior'})
    ll = la.merge(lb, on=k, how='outer')

    def motivo_linha(r):
        al = str(r.get('Alertas') or '')
        if pd.isna(r['cred_atual']) and not pd.isna(r['cred_anterior']):
            return 'R1 enquadramento automático restrito: linha sem enquadramento (antes: carga/marca/UF/art. 39)'
        if 'diagnóstico Anexo V: a fórmula do rótulo' in al:
            return 'R2 Anexo V pela fórmula do enquadramento (antes: a que reproduzia o ICMS-ST)'
        if 'parece já reduzida' in al:
            return 'R3 Anexo IV com a fórmula do anexo (antes: sem reaplicar a redução)'
        if 'FCP com base própria' in al:
            return 'R4 FCP calculado na sua base (antes: alíquota única)'
        return 'sem mudança na linha'
    ll['motivo'] = ll.apply(motivo_linha, axis=1)
    ll['dif_linha'] = (ll['cred_atual'].fillna(0) - ll['cred_anterior'].fillna(0)).round(2)
    por_prod_motivo = ll[ll['motivo'] != 'sem mudança na linha'].groupby(['EAN', 'Data de revogação'])['motivo'].agg(
        lambda s: '; '.join(sorted(set(s))))
    m = m.merge(por_prod_motivo.rename('motivos_da_diferenca').reset_index(), on=['EAN', 'Data de revogação'], how='left')
    m['motivos_da_diferenca'] = m['motivos_da_diferenca'].fillna(
        m['diferenca'].apply(lambda d: 'piso zero da mercadoria / arredondamento' if abs(d) >= 0.005 else ''))
    mud = m[m['diferenca'].abs() >= 0.005]
    # ponte por motivo (atribuída pela diferença de cada produto ao seu motivo principal)
    mud = mud.assign(motivo_principal=mud['motivos_da_diferenca'].str.split('; ').str[0])
    ponte = mud.groupby('motivo_principal').agg(produtos=('EAN', 'count'), diferenca=('diferenca', 'sum')).reset_index().sort_values('diferenca')
    tot_an, tot_at = round(m['anterior'].sum(), 2), round(m['atual'].sum(), 2)
    resumo = dict(anterior_recalculado=tot_an, anterior_informado=anterior_total,
                  anterior_confere=(abs(tot_an - anterior_total) < 0.01) if anterior_total is not None else None,
                  atual_total=tot_at, atual_com_observacao=r_at['credito_interpretativo'],
                  diferenca=round(tot_at - tot_an, 2), soma_da_ponte=round(ponte['diferenca'].sum(), 2))
    destino = os.path.join(pasta, 'relatorio_parser', 'ponte_reconciliacao.xlsx')
    with pd.ExcelWriter(destino) as w:
        pd.DataFrame([resumo]).T.reset_index().rename(columns={'index': 'item', 0: 'valor'}).to_excel(w, sheet_name='Resumo', index=False)
        ponte.to_excel(w, sheet_name='Por motivo', index=False)
        mud.sort_values('diferenca').to_excel(w, sheet_name='Por produto', index=False)
        ll[ll['motivo'] != 'sem mudança na linha'].to_excel(w, sheet_name='Por linha de nota', index=False)
    return resumo, ponte, destino


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pasta')
    ap.add_argument('--anterior-total', type=float)
    a = ap.parse_args()
    resumo, ponte, destino = reconciliar(a.pasta, a.anterior_total)
    print(json.dumps(resumo, ensure_ascii=False, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(ponte.to_string(index=False))
    print(destino)
