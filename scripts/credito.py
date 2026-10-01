"""Aplicação da fórmula da CAT 28/2020 (Anexos IV e V) sobre as linhas de alocação de notas.

Entrada por linha (vinda de `alocacao.alocar`): base de ST unitária x quantidade usada (`bc_st_usada`), valor da mercadoria
usado (`vl_liq_usado`), alíquota interna, redução de base, CST, CRT, UF e os totais da linha inteira da nota.
O regime do detentor do estoque escolhe o anexo: Simples Nacional -> Anexo V; RPA -> Anexo IV.

Todo crédito calculado entra no total unificado (decisão do usuário, 01/10/2026). Cada linha sai com uma marca interna
(`classe`), que só indica se há ressalva a registrar como observação do cálculo:
- 'definitivo' = sem ressalva: fórmula do anexo pelo enquadramento jurídico, parâmetros da nota ou da lei, documento autorizado;
- 'interpretativo' = com ressalva: valor calculado com uma premissa a documentar (analogia, alíquota presumida, percentual da
  operação própria, base que parece já reduzida, enquadramento por análise, divergência de carga, documento a conferir),
  somado ao total, com o motivo e os valores alternativos;
- pendente: sem valor (falta enquadramento, alíquota, UF, regime ou VlMerc válido).
Comparações com o ICMS-ST destacado são DIAGNÓSTICO: nunca trocam a fórmula nem o valor.
"""
from typing import Dict, List, Optional

import formulas as F


def _brl(v):
    return 'R$ ' + f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


REGIME_CRT = {'1': F.SN, '2': F.RPA, '3': F.RPA, '4': F.SN}
TOL_PROVA_ABS, TOL_PROVA_REL = 0.05, 0.03     # R$ 0,05 ou 3% do imposto da linha inteira da nota (só diagnóstico)
ROTULO_RED = {F.RED_APLICAVEL_CF: 'aplicável', F.RED_NAO_APLICAVEL_CF: 'não aplicável', F.SEM_REDUCAO: 'sem redução'}


def _tol(valor):
    return max(TOL_PROVA_ABS, TOL_PROVA_REL * abs(valor))


def _regime_fornecedor(cst, crt):
    """Regime do fornecedor pelo código de tributação do ICMS do item (CSOSN 3 dígitos = SN; CST 2 dígitos = RPA, inclui CRT 2)
    e pelo CRT. Devolve (regime ou None, conflito). Conflito entre os dois NÃO é resolvido em silêncio: a linha usa o CST e
    fica interpretativa."""
    c = str(cst or '').strip()
    pelo_crt = REGIME_CRT.get(str(crt or '').strip())
    pelo_cst = F.SN if (len(c) == 3 and c.isdigit()) else F.RPA if (len(c) == 2 and c.isdigit()) else None
    if pelo_cst is None:
        return pelo_crt, ''
    conflito = f'CST/CSOSN {c} indica fornecedor {pelo_cst} e o CRT {crt} indica {pelo_crt}' if pelo_crt and pelo_crt != pelo_cst else ''
    return pelo_cst, conflito


def aliquota_interestadual(l: dict):
    """Alíquota interestadual do item (%): a informada ou o pICMS da nota (fundamentados); sem eles, a da Resolução do Senado
    pela origem informada no XML (4% importado, Res. SF 13/2012; 12% demais, Res. SF 22/1989, destino SP). Sem origem, 12% é
    só presunção. Devolve (alíquota ou None, presumida: bool, alerta)."""
    for campo in ('aliquota_interestadual', 'p_icms'):
        if float(l.get(campo) or 0) > 0:
            return float(l[campo]), False, ''
    if l.get('uf_emitente') and l.get('uf_emitente') == l.get('uf_destinatario'):
        return None, False, ''
    orig = str(l.get('orig') or '').strip()
    if orig in ('1', '2', '3', '8'):
        return 4.0, False, f'alíquota interestadual 4% pela origem {orig} (importado; Res. SF 13/2012)'
    if orig:
        return 12.0, False, f'alíquota interestadual 12% pela origem {orig} (Res. SF 22/1989, destino SP)'
    return 12.0, True, 'alíquota interestadual presumida em 12%: a nota não informa a origem da mercadoria (se importada, seria 4%)'


def diagnostico_anexo_v(regime, red, r_literal, args, linha):
    """Só diagnóstico (não troca a fórmula): diz se a fórmula literal do Anexo V ou a do rótulo trocado reproduz o ICMS-ST
    cobrado na linha inteira da nota. Devolve o texto do alerta ou ''."""
    if regime != F.SN or red == F.SEM_REDUCAO or not linha or linha.get('bc', 0) <= 0 or linha.get('st', 0) <= 0:
        return ''
    outra = F.RED_NAO_APLICAVEL_CF if red == F.RED_APLICAVEL_CF else F.RED_APLICAVEL_CF
    a_l = dict(args, bc_st=linha['bc'])
    lit_v = F.credito_item(reducao=red, vl_merc=linha['vl'], **a_l).credito
    out_v = F.credito_item(reducao=outra, vl_merc=linha['vl'], **a_l).credito
    ref, tol = linha['st'], _tol(linha['st'])
    lit_ok, out_ok = abs(lit_v - ref) <= tol, abs(out_v - ref) <= tol
    if lit_ok:
        return f'diagnóstico Anexo V: a fórmula aplicada reproduz o ICMS-ST cobrado na linha da nota ({_brl(ref)})'
    if out_ok:
        return (f'diagnóstico Anexo V: a fórmula do rótulo "{ROTULO_RED[outra]}" reproduziria o ICMS-ST cobrado na linha ({_brl(ref)}); '
                'mantida a fórmula do enquadramento jurídico (art. 3º e Anexo V)')
    return f'diagnóstico Anexo V: nenhuma das duas fórmulas reproduz o ICMS-ST cobrado na linha ({_brl(ref)})'


def diagnostico_base_reduzida(r, args, linha):
    """Anexo IV, fórmula BC ST x (1 - pRedBc) x alíquota: se a BC ST da nota reproduz o imposto suportado na linha
    (BC ST x alíquota = ICMS-ST + FCP + ICMS próprio), a redução PODE já estar na base. A igualdade numérica não demonstra
    qual base a portaria exige: o crédito fica o literal e a linha vai para interpretativo com o valor alternativo.
    Devolve (valor alternativo, alerta) ou None."""
    if r.anexo != 'IV' or r.formula != 'C = BC ST x (1 - pRedBc) x Alíquota interna' or not linha:
        return None
    suportado = linha.get('st', 0) + linha.get('proprio', 0)
    if linha.get('bc', 0) <= 0 or suportado <= 0 or linha.get('proprio', 0) <= 0:
        return None
    if abs(linha['bc'] * args['aliq_interna'] - suportado) > _tol(suportado):
        return None
    alt = round(args['bc_st'] * args['aliq_interna'], 2)
    return alt, (f'BC ST da nota parece já reduzida (BC ST x alíquota = {_brl(linha["bc"] * args["aliq_interna"])} = ICMS-ST + ICMS próprio '
                 f'{_brl(suportado)}): sem reaplicar a redução o crédito seria {_brl(alt)}; mantida a fórmula do Anexo IV ({_brl(r.credito)}) até '
                 'fundamentar a natureza da base')


def _responsavel(l: dict) -> str:
    """Base de ST na própria nota (vBCST: CST 10/30/70/90, CSOSN 201/202/203/900) = retenção pelo fornecedor;
    só vBCSTRet (CST 60, CSOSN 500) = retenção por substituto anterior. Sem as bases unitárias, decide pelo CST."""
    if l.get('antecipacao'):
        return F.ANTEC_ADQUIRENTE
    st, ret = l.get('bc_st_unit'), l.get('bc_st_ret_unit')
    if st is not None or ret is not None:
        if float(st or 0) > 0:
            return F.RET_FORNECEDOR
        if float(ret or 0) > 0:
            return F.RET_SUBST_ANTERIOR
    return F.RET_FORNECEDOR if str(l.get('cst')) in ('10', '30', '70', '90', '201', '202', '203', '900') else F.RET_SUBST_ANTERIOR


def _pendente(base, alerta, **extra):
    return dict(base, alertas=[alerta], status='dados_fiscais_pendentes', classe='pendente', motivos=[alerta], **extra)


def calcular_linha(regime: str, l: dict, valor_mercadoria: str = 'liquido') -> dict:
    """regime: 'SN' ou 'RPA'. Devolve {credito, classe, motivos, alternativas, formula, linha_tabela, alertas, status,
    p_red_usado, p_red_origem_usado, aliquota_usada, enquadramento, alt_vprod, analogia}.
    status: 'calculado' | 'sem_base_st' | 'sem_aliquota' | 'nao_previsto' | 'dados_fiscais_pendentes'."""
    bc = float(l.get('bc_st_usada') or 0)
    vl_bruto = float(l.get('vl_merc_usado') or 0)
    vl = float(l.get('vl_liq_usado', vl_bruto)) if valor_mercadoria == 'liquido' else vl_bruto
    base_vazia = dict(credito=None, alternativa=None, alt_vprod=None, formula='', linha_tabela='', alternativas={},
                      p_red_usado=None, p_red_origem_usado='', aliquota_usada=l.get('aliquota_st'), enquadramento='')
    if l.get('sem_base_st') or bc <= 0:
        return dict(base_vazia, credito=0.0, alertas=['sem base de ST: crédito zero (art. 4º, I)'], status='sem_base_st',
                    classe='definitivo', motivos=[])
    aliq = l.get('aliquota_st')
    if aliq is None:
        return dict(base_vazia, alertas=['alíquota interna ausente'], status='sem_aliquota', classe='pendente', motivos=['alíquota interna ausente'])
    motivos, alternativas = [], {}
    p_st, p_prop = float(l.get('p_red_bc_st') or 0) / 100.0, float(l.get('p_red_bc') or 0) / 100.0
    p_nota = float(l.get('p_red_efetivo', l.get('p_red_bc_st')) or 0) / 100.0
    red = l.get('reducao') or (F.SEM_REDUCAO if p_nota == 0 else None)
    if red not in (F.SEM_REDUCAO, F.RED_APLICAVEL_CF, F.RED_NAO_APLICAVEL_CF) or ((red == F.SEM_REDUCAO) != (p_nota == 0)):
        origem = l.get('p_red_origem') or 'pRedBCST'
        return _pendente(base_vazia, f'Redução de BC de {p_nota * 100:g}% ({origem}): informar o enquadramento (aplicável ou não ao consumidor '
                                     'final) conforme a legislação do produto')
    enquadramento = '' if red == F.SEM_REDUCAO else f"{ROTULO_RED[red]} ({l.get('enq_dispositivo') or 'sem dispositivo'}; {l.get('enq_fonte') or '?'})"
    # percentual de redução que entra na fórmula: o LEGAL quando o dispositivo fixa a carga; senão o da redução da ST na nota;
    # o pRedBC da operação própria não é transportado para a ST sem fundamento
    p_red, origem_p = 0.0, ''
    carga_legal = l.get('carga_legal')
    if red != F.SEM_REDUCAO:
        if carga_legal is not None and float(aliq) > float(carga_legal):
            p_red = (float(aliq) - float(carga_legal)) / float(aliq)
            origem_p = f"legal: carga {float(carga_legal):g}% de {l.get('enq_dispositivo') or 'dispositivo'}"
            if abs(p_red - p_nota) > 0.0005:
                motivos.append(f'percentual de redução da nota ({p_nota * 100:.2f}%) diferente do legal ({p_red * 100:.2f}%)')
        elif p_st > 0:
            p_red, origem_p = p_st, 'pRedBCST da nota (redução da base da ST)'
        else:
            p_red, origem_p = p_prop, 'pRedBC da operação própria do fornecedor'
            motivos.append('percentual da operação própria (pRedBC) usado na fórmula da ST sem fundamento de que se aplique à ST')
        if 'enq_evid_ok' in l and not l.get('enq_evid_ok'):
            motivos.append('evidência do enquadramento incompleta' + (f": falta {l['enq_evid_falta']}" if l.get('enq_evid_falta') else ''))
        if l.get('enq_divergente'):
            motivos.append('carga destacada na nota diferente da carga do dispositivo enquadrado')
    regime_forn, conflito = _regime_fornecedor(l.get('cst'), l.get('crt_emitente'))
    if regime not in (F.SN, F.RPA) or regime_forn is None:
        return _pendente(base_vazia, 'Regime do detentor ou CST/CRT do fornecedor ausente/inválido')
    if conflito:
        motivos.append(f'{conflito}: conflito não resolvido (usado o CST)')
    if not l.get('uf_emitente') or not l.get('uf_destinatario'):
        return _pendente(base_vazia, 'UF de origem/destino ausente')
    aie, aie_presumida, alerta_aie = aliquota_interestadual(l)
    args = dict(
        regime_detentor=F.SN if regime == 'SN' else F.RPA, regime_fornecedor=regime_forn, responsavel=_responsavel(l),
        operacao=F.INTERNA if l.get('uf_emitente') == l.get('uf_destinatario') else F.INTERESTADUAL,
        bc_st=bc, aliq_interna=float(aliq) / 100.0, aliq_interestadual=(aie / 100.0 if aie else None), p_red=p_red)
    try:
        r = F.credito_item(reducao=red, vl_merc=vl, **args)
        alt_vprod = F.credito_item(reducao=red, vl_merc=vl_bruto, **args).credito if abs(vl - vl_bruto) > 0.005 else None
    except F.NaoPrevistoNaPortaria as ex:
        return dict(base_vazia, alertas=[f'combinação não prevista: {ex}'], status='nao_previsto', classe='pendente', motivos=[str(ex)])
    except ValueError as ex:
        return _pendente(base_vazia, str(ex))
    if 'VlMerc' not in r.formula:
        alt_vprod = None
    if 'VlMerc' in r.formula and vl <= 0:
        return _pendente(base_vazia, f'valor da mercadoria {_brl(vl)} (zero ou negativo: bonificação ou dado inconsistente) numa fórmula que usa '
                                     'VlMerc: crédito não calculado')
    linha = (dict(bc=float(l.get('bc_linha') or 0), vl=float(l.get('vl_liq_linha') or 0), st=float(l.get('st_linha') or 0),
                  proprio=float(l.get('proprio_linha') or 0)) if l.get('bc_linha') is not None else None)
    alertas = list(r.alertas)
    diag_v = diagnostico_anexo_v(args['regime_detentor'], red, r, args, linha)
    if diag_v:
        alertas.append(diag_v)
    diag_b = diagnostico_base_reduzida(r, args, linha)
    if diag_b:
        alternativas['sem reaplicar a redução (BC ST x alíquota)'] = diag_b[0]
        alertas.append(diag_b[1])
        motivos.append('BC ST da nota parece já reduzida: natureza da base a fundamentar (Anexo IV)')
    if alerta_aie and 'Alíquota interestadual' in r.formula:
        alertas.append(alerta_aie)
        if aie_presumida:
            motivos.append('alíquota interestadual presumida (a nota não informa a origem)')
    if r.analogia:
        motivos.append('combinação não listada no Anexo IV: valor por analogia, sem fundamento oficial específico')
    credito = r.credito
    if l.get('fcp_base_diverge') and float(l.get('p_fcp') or 0) > 0 and 'Alíquota interestadual' not in r.formula:
        f_ = float(l['p_fcp']) / 100.0
        a_icms = dict(args, aliq_interna=args['aliq_interna'] - f_)
        a_fcp = dict(args, aliq_interna=f_, bc_st=float(l.get('bc_fcp_usada') or 0))
        credito = round(F.credito_item(reducao=red, vl_merc=vl, **a_icms).credito + F.credito_item(reducao=red, vl_merc=vl, **a_fcp).credito, 2)
        alternativas['alíquota única (ICMS + FCP) sobre a BC ST'] = r.credito
        alertas.append(f'FCP com base própria: ICMS sobre a BC ST e FCP ({f_ * 100:g}%) sobre a BC do FCP = {_brl(credito)}; a fórmula com '
                       f'alíquota única daria {_brl(r.credito)}')
    if str(l.get('aliquota_origem') or '').startswith('padrão'):
        motivos.append('alíquota interna presumida (não encontrada na nota nem no cadastro do estoque)')
    for flag, texto in (('sem_protocolo', 'nota sem protocolo de autorização (cStat) no XML'),
                        ('bases_somadas', 'a linha traz base de ST própria e retida anteriormente: conferir antes de somar'),
                        ('fcp_base_diverge', 'base do FCP diferente da base da ST: a alíquota com FCP sobre a base da ST não reproduz o FCP'),
                        ('complementar', 'há nota complementar para esta nota (refNFe) que não foi ligada a nenhum item: conferir a base')):
        if l.get(flag):
            motivos.append(texto)
    if l.get('antecipacao'):
        alertas.append('BC ST da antecipação pelo adquirente informada (bc_st_antecipacao), fora da nota')
    if valor_mercadoria == 'liquido' and alt_vprod is not None:
        alertas.append(f'VlMerc líquido {_brl(vl)} (vProd {_brl(vl_bruto)}); com vProd o crédito seria {_brl(alt_vprod)}')
    if l.get('complementada'):
        alertas.append(f"base complementada pela NF complementar {l['complementada']} (art. 4º, II)")
    if r.credito < 0:
        alertas.append('BC de ST menor que o valor da mercadoria: valor negativo nesta linha (compensa dentro da mercadoria; total com piso zero)')
    if motivos:
        alertas.append('Observação do cálculo (já somada ao total): ' + '; '.join(motivos))
    return dict(credito=credito, alternativa=None, alt_vprod=alt_vprod, formula=r.formula, linha_tabela=f'Anexo {r.anexo}: {r.linha}',
                alertas=alertas, status='calculado', analogia=r.analogia, classe='interpretativo' if motivos else 'definitivo',
                motivos=motivos, alternativas=alternativas, p_red_usado=round(p_red * 100, 4), p_red_origem_usado=origem_p,
                aliquota_usada=float(aliq), enquadramento=enquadramento)


def consolidar_item(linhas: List[dict], resultados: List[dict]) -> dict:
    """Totais da mercadoria (itens 14 a 16 do Anexo I): soma das linhas calculadas, com piso zero (a exclusão nunca gera débito).
    `definitivo` = nenhuma linha com ressalva nem pendente (sem observação do cálculo); o crédito calculado é somado ao total
    de qualquer forma, e `motivos` traz as ressalvas."""
    total_bruto = sum(r['credito'] for r in resultados if r['credito'] is not None)
    total = max(0.0, total_bruto)
    motivos = []
    for r in resultados:
        for m in r.get('motivos') or []:
            if m not in motivos:
                motivos.append(m)
    pendente = any(r['status'] in ('sem_aliquota', 'nao_previsto', 'dados_fiscais_pendentes') for r in resultados)
    definitivo = not pendente and all(r.get('classe') == 'definitivo' for r in resultados)
    return dict(
        total_vl=sum(l.get('vl_liq_usado', l['vl_merc_usado']) for l in linhas), total_bc=sum(l['bc_st_usada'] for l in linhas),
        total_literal=round(total_bruto, 2), credito=round(total, 2), ajuste_piso=round(total - total_bruto, 2),
        pendente=pendente, definitivo=definitivo, motivos=motivos,
        nlinhas=len(linhas), sem_base=sum(1 for r in resultados if r['status'] == 'sem_base_st'))
