"""Seleção das notas de compra que SUPREM a quantidade do estoque (regras de ouro 1 a 4 do usuário).

1. A quantidade em estoque deve ser suprida por UMA OU MAIS notas de compra; localizar o máximo possível para cobri-la.
   Ordem: produto localizado por EAN (melhor prova) e, se faltar quantidade, outros produtos equivalentes por descrição
   (A/B e depois C na simulação). Entre todos os grupos, da nota mais recente para a mais antiga; a última pode entrar em parte.
2. De cada item de nota extrai-se a BASE DE ST e a BASE DE ST RETIDO ANTERIORMENTE **unitárias** (base da linha dividida
   pela quantidade da nota já convertida para unidades de estoque) e multiplica-se pela quantidade do estoque que aquela
   nota supre. É esse valor que entra na fórmula da CAT 28/2020.
3. Alíquota: a da ST do parser quando houver (pICMSST nas CST 10/70; pST nas 60/500; mais o FCP da ST); quando não
   houver, a alíquota interna do item no estoque (totalizador do PDV); sem nenhuma das duas (ou cadastro com 0%), 18%,
   a alíquota interna geral de SP (decisão do usuário), com alerta. pST já inclui o FCP (NT 2016.002).
4. Só notas ANTERIORES à vigência da exclusão da CAT 68/2019 (emissão < data de revogação).

5. PROVA OBRIGATÓRIA (sem validação manual): só supre o estoque, e portanto só gera crédito, a nota cuja localização e cujo
   fator de conversão estão provados (EAN, ou descrição A/B sem ambiguidade; fator A/B). O que não tem prova é descartado
   automaticamente, com o motivo, e nunca consome quantidade de nota. `exigir_prova=False` existe só para a simulação
   "fora do crédito" (quanto se poderia aproveitar com mais documentos), rodada depois, sobre o que sobrou.
6. USO ÚNICO DA NOTA: o livro-razão `consumo` ({índice da linha da nota: quantidade já usada}) é global, compartilhado por
   TODOS os itens e TODAS as posições de estoque. Um item de nota nunca supre mais do que a quantidade que comprou;
   `verificar_consumo` confere isso ao final e interrompe o levantamento se houver excesso.

Nenhum crédito é calculado aqui: o resultado alimenta o passo da fórmula (Anexos IV/V).
"""
import re
from datetime import date, datetime
from typing import Callable, Dict, List, Optional, Tuple

EPS = 1e-9
NAO_CONFIRMADO = ('C',)
DIAS_REVISAO_ENTRADA = 7           # só PRIORIZA a revisão da entrada; não é critério de conformidade
ALIQ_PADRAO = 18.0                 # alíquota interna geral de SP: usada quando nem a nota nem o estoque trazem a alíquota (decisão do usuário)
ORIGEM_ALIQ_PADRAO = 'padrão 18% (alíquota interna não encontrada na nota nem no estoque)'
MOTIVO_LOCALIZACAO = 'localização sem prova (descrição nível C ou ambígua)'
MOTIVO_FATOR = 'fator de conversão sem prova'


class ConsumoExcedido(RuntimeError):
    """Um item de nota foi usado além da quantidade comprada (uso duplicado entre itens do estoque)."""


def verificar_consumo(consumo: Dict[int, float], compras: List[dict]) -> None:
    """Trava final do uso único: nenhum item de nota pode ter sido usado além da sua quantidade."""
    ruins = [(i, u, float(compras[i]['qtd'])) for i, u in consumo.items() if u > float(compras[i]['qtd']) * (1 + 1e-9) + EPS]
    if ruins:
        det = '; '.join(f"{compras[i]['chave_nfe']} item {compras[i]['n_item']}: usado {u:g} de {q:g}" for i, u, q in ruins[:5])
        raise ConsumoExcedido(f'{len(ruins)} item(ns) de nota usado(s) além da quantidade comprada: {det}')


def _dt(v) -> Optional[date]:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _evidencia_entrada(l: dict) -> str:
    """Evidência disponível da ENTRADA da mercadoria (art. 2º: estoque na data). Registro de entrada (EFD, livro, manifestação)
    informado em entradas.csv é a evidência; dhSaiEnt é a data de saída informada pelo emitente e não comprova o recebimento."""
    if l.get('_data_entrada'):
        return f"registro de entrada em {str(l['_data_entrada'])[:10]} ({l.get('_origem_entrada') or 'informado'})"
    if l.get('data_saida_entrada'):
        return f"dhSaiEnt do emitente {str(l['data_saida_entrada'])[:10]} (não comprova o recebimento); sem registro de entrada"
    return 'só a data de emissão; sem registro de entrada'


def _fcp_diverge(l: dict) -> bool:
    """Base do FCP informada e diferente da base da ST da mesma linha (com FCP de fato cobrado)."""
    for bc_fcp, bc, v_fcp in (('vbc_fcp_st', 'vbc_st', 'vfcp_st'), ('vbc_fcp_st_ret', 'vbc_st_ret', 'vfcp_st_ret')):
        b_f, b, v = float(l.get(bc_fcp) or 0), float(l.get(bc) or 0), float(l.get(v_fcp) or 0)
        if v > 0 and b_f > 0 and abs(b_f - b) > 0.01:
            return True
    return False


def elegivel(linha: dict, data_revogacao: date) -> Tuple[bool, str]:
    """Regra 4 + filtros de documento: emitida antes da vigência, nota normal e autorizada, não devolução."""
    d = _dt(linha.get('data_emissao'))
    if d is None:
        return False, 'sem data de emissão'
    if d >= data_revogacao:
        return False, 'emitida na vigência da exclusão ou depois'
    if linha.get('situacao', 'Normal') != 'Normal':
        return False, 'nota cancelada'
    if linha.get('c_stat') and linha['c_stat'] not in ('100', '150'):
        return False, 'nota não autorizada'
    if str(linha.get('fin_nfe') or '') == '4':
        return False, 'devolução'
    if str(linha.get('fin_nfe') or '') == '2':
        return False, 'nota complementar (incorporada à nota original)'
    de = _dt(linha.get('_data_entrada'))
    if de and de >= data_revogacao:
        return False, 'entrada registrada na vigência da exclusão ou depois'
    cfop = str(linha.get('cfop') or '')
    if len(cfop) == 4 and cfop[0] in '56' and cfop[1] == '2':
        return False, 'CFOP de devolução'
    if (linha.get('qtd') or 0) <= 0:
        return False, 'quantidade zero'
    return True, ''


def aliquota_st(linha: dict, aliq_estoque: Optional[float]) -> Tuple[Optional[float], str]:
    """Regra 3. A alíquota interna inclui o FCP (Anexo I, item 5). pICMSST não inclui o FCP (soma-se pFCPST);
    pST ("alíquota suportada pelo consumidor final", NT 2016.002) já traz o FCP embutido e é usado sozinho."""
    p_st = float(linha.get('p_icms_st') or 0)
    if p_st > 0:
        return round(p_st + float(linha.get('p_fcp_st') or 0), 4), 'ST da nota (pICMSST + pFCPST)'
    p_ret = float(linha.get('p_st') or 0)
    if p_ret > 0:
        return round(p_ret, 4), 'ST retido anteriormente (pST, já inclui FCP)'
    if aliq_estoque is not None and float(aliq_estoque) > 0:      # 0% no cadastro do PDV não é alíquota de produto com ST
        return float(aliq_estoque), 'alíquota interna do item no estoque (totalizador)'
    return ALIQ_PADRAO, ORIGEM_ALIQ_PADRAO


def alocar(item: dict, grupos: List[dict], compras: List[dict], data_revogacao: date, consumo: Dict[int, float],
           fator_fn: Callable[[dict, dict], dict], exigir_prova: bool = True) -> dict:
    """item: {descricao, ean, qtd, valor, aliq_totalizador}; grupos: [{chaves, linhas, origem, confirmado}] em ordem de
    prioridade; consumo: livro-razão global {índice da linha: qtd da nota já usada por qualquer outro item do levantamento}.
    Devolve {'linhas': [...], 'qtd_estoque', 'qtd_coberta', 'qtd_descoberta', 'descartadas': {motivo: n}}."""
    restante, saida = float(item['qtd']), []
    descartadas: Dict[str, int] = {}
    # Identidade/prova são preservadas; a cronologia é global entre os grupos.
    por_linha = {}
    for grupo in grupos:
        for indice in grupo['linhas']:
            anterior = por_linha.get(indice)
            if anterior is None or (grupo['confirmado'] and not anterior['confirmado']):
                por_linha[indice] = dict(grupo, linhas=[indice])
    grupos = [por_linha[i] for i in sorted(por_linha, key=lambda i: (
        _dt(compras[i].get('data_emissao')) or date.min,
        compras[i]['chave_nfe'], int(compras[i]['n_item'] or 0)), reverse=True)]
    for g in grupos:
        if exigir_prova and not g['confirmado']:
            descartadas[MOTIVO_LOCALIZACAO] = descartadas.get(MOTIVO_LOCALIZACAO, 0) + len(g['linhas'])
            continue
        elegiveis = []
        for i in g['linhas']:
            ok, motivo = elegivel(compras[i], data_revogacao)
            if ok:
                elegiveis.append(i)
            else:
                descartadas[motivo] = descartadas.get(motivo, 0) + 1
        elegiveis.sort(key=lambda i: (_dt(compras[i]['data_emissao']), compras[i]['chave_nfe'], int(compras[i]['n_item'] or 0)), reverse=True)
        for i in elegiveis:
            if restante <= EPS:
                break
            l = compras[i]
            f = fator_fn(item, l)
            fator = float(f['fator'])
            if exigir_prova and f['confianca'] == 'C':
                descartadas[MOTIVO_FATOR] = descartadas.get(MOTIVO_FATOR, 0) + 1
                continue
            disponivel_nf = float(l['qtd']) - consumo.get(i, 0.0)
            if disponivel_nf <= EPS:
                continue
            equiv_linha = float(l['qtd']) * fator                  # unidades de estoque que a linha inteira representa
            usar_equiv = min(restante, disponivel_nf * fator)
            consumo[i] = consumo.get(i, 0.0) + usar_equiv / fator
            restante -= usar_equiv
            vbc_st, vbc_ret = float(l.get('vbc_st') or 0), float(l.get('vbc_st_ret') or 0)
            # antecipação pelo adquirente: a BC ST não está na nota; vem do recolhimento (guia) informado em bc_st_antecipacao
            vbc_ant = float(l.get('bc_st_antecipacao') or 0) if (vbc_st + vbc_ret) <= 0 else 0.0
            vbc_st += vbc_ant
            u_st, u_ret = vbc_st / equiv_linha, vbc_ret / equiv_linha            # regra 2: base unitária por unidade de estoque
            u_fcp = float(l.get('vbc_fcp_st_ret') or 0) / equiv_linha
            u_vl = float(l.get('vl_merc') or 0) / equiv_linha
            # valor da operação líquido de desconto = base do ICMS próprio do fornecedor (vProd + frete + seguro + outras - vDesc)
            liq = (float(l.get('vl_merc') or 0) + float(l.get('frete') or 0) + float(l.get('seguro') or 0)
                   + float(l.get('outras_despesas') or 0) - float(l.get('desconto') or 0))
            u_liq = liq / equiv_linha
            u_desc = float(l.get('desconto') or 0) / equiv_linha
            st_linha = (float(l.get('vicms_st') or 0) + float(l.get('vicms_st_ret') or 0)
                        + float(l.get('vfcp_st') or 0) + float(l.get('vfcp_st_ret') or 0))       # ICMS-ST cobrado na linha, com FCP
            u_st_cobrado = st_linha / equiv_linha
            aliq, aliq_origem = aliquota_st(l, item.get('aliq_totalizador'))
            p_red_st, p_red_proprio = float(l.get('p_red_bc_st') or 0), float(l.get('p_red_bc') or 0)
            if p_red_st > 0:
                p_red_efetivo, p_red_origem = p_red_st, 'pRedBCST'
            elif vbc_st > 0 and p_red_proprio > 0:            # nota com ST e redução só em pRedBC: não calcular como "sem redução"
                p_red_efetivo, p_red_origem = p_red_proprio, 'pRedBC, redução da operação própria'
            else:
                p_red_efetivo, p_red_origem = 0.0, ''
            saida.append(dict(
                origem=g['origem'], confirmado=bool(g['confirmado']) and f['confianca'] != 'C', linha_idx=i,
                chave_nfe=l['chave_nfe'], n_item=l['n_item'], data_emissao=str(_dt(l['data_emissao'])), cod_produto_nf=l.get('cod_produto'),
                descricao_nf=l.get('descricao'), ean_nf=l.get('ean'), unid_nf=l.get('unid_comercial'), qtd_nf=float(l['qtd']),
                fator=fator, fator_origem=f['origem'], fator_confianca=f['confianca'], fator_obs=f.get('observacao', ''),
                qtd_usada_estoque=usar_equiv, qtd_equivalente_linha=equiv_linha,
                vl_merc_unit=u_vl, bc_st_unit=u_st, bc_st_ret_unit=u_ret, bc_st_total_unit=u_st + u_ret, bc_fcp_st_ret_unit=u_fcp,
                vl_liq_unit=u_liq, vl_liq_usado=u_liq * usar_equiv, desconto_usado=u_desc * usar_equiv,
                st_cobrado_usado=u_st_cobrado * usar_equiv, vl_merc_usado=u_vl * usar_equiv, bc_st_usada=(u_st + u_ret) * usar_equiv, bc_st_ret_usada=u_ret * usar_equiv,
                aliquota_st=aliq, aliquota_origem=aliq_origem, cst=l.get('cst'), crt_emitente=l.get('crt_emitente'),
                uf_emitente=l.get('uf_emitente'), uf_destinatario=l.get('uf_destinatario'), cfop=l.get('cfop'),
                reducao=l.get('reducao'), aliquota_interestadual=l.get('aliquota_interestadual'), orig=l.get('orig'),
                antecipacao=vbc_ant > 0,
                p_red_bc_st=p_red_st, p_red_bc=p_red_proprio, p_red_efetivo=p_red_efetivo, p_red_origem=p_red_origem,
                carga_legal=l.get('_carga_legal'), enq_fonte=l.get('_enq_fonte', ''), enq_dispositivo=l.get('_enq_dispositivo', ''),
                enq_divergente=bool(l.get('_enq_divergente')),
                # marcas documentais (art. 2º estoque na data; art. 4º identificação e complementação): geram observação do cálculo na linha
                sem_protocolo=not str(l.get('c_stat') or '').strip(),
                evidencia_entrada=_evidencia_entrada(l),
                revisar_entrada=bool(not l.get('_data_entrada') and _dt(l.get('data_emissao'))
                                     and (data_revogacao - _dt(l.get('data_emissao'))).days <= DIAS_REVISAO_ENTRADA),
                complementada='; '.join(l.get('_complementada') or []),
                enq_evid_ok=bool(l.get('_enq_evid_ok')), enq_evid_falta=l.get('_enq_evid_falta', ''),
                bc_fcp_usada=(float(l.get('vbc_fcp_st') or 0) + float(l.get('vbc_fcp_st_ret') or 0)) / equiv_linha * usar_equiv,
                p_fcp=float(l.get('p_fcp_st') or 0) or float(l.get('p_fcp_st_ret') or 0),
                bases_somadas=vbc_st > 0 and vbc_ret > 0 and not vbc_ant,
                fcp_base_diverge=_fcp_diverge(l),
                complementar=bool(l.get('_tem_complementar')),
                # linha inteira da nota (sem ratear): provas das fórmulas com redução (Anexo V) e da base já reduzida (Anexo IV)
                bc_linha=vbc_st + vbc_ret, vl_liq_linha=liq, st_linha=st_linha,
                proprio_linha=float(l.get('vicms') or 0) + float(l.get('vicms_substituto') or 0),
                p_icms=float(l.get('p_icms') or 0),
                sem_base_st=(vbc_st + vbc_ret) <= 0))
        if restante <= EPS:
            break
    coberta = float(item['qtd']) - max(restante, 0.0)
    return dict(linhas=saida, qtd_estoque=float(item['qtd']), qtd_coberta=coberta, qtd_descoberta=max(restante, 0.0),
                descartadas=descartadas)
