"""Fórmulas do crédito de ICMS sobre estoque na exclusão da ST (Portaria CAT 28/2020, Anexos IV e V).

Transcrição das tabelas oficiais (references/base-legal/portaria-cat-28-2020.html). Cada ramo indica a linha da
tabela que implementa. As combinações que o Anexo IV não lista são resolvidas por ANALOGIA explícita (marcada no rótulo
da linha e em `Resultado.analogia`), sempre com a regra da própria portaria para o mesmo tipo de carga:
- retenção por substituto anterior ao fornecedor RPA: o fornecedor substituído não destaca ICMS próprio e toda a carga
  foi retida antes (art. 4º trata exatamente da NF-e com CST 60), como na linha "fornecedor SN / substituto anterior";
- substituto anterior ou antecipação com redução de BC, e antecipação em operação interna: a regra da linha RPA/RPA
  (sem redução ou redução não aplicável ao consumidor final = BC ST x alíquota; aplicável = BC ST x (1 - pRedBc) x alíquota).
`NaoPrevistoNaPortaria` fica só para responsável ou regime do fornecedor desconhecido.

Notação da portaria: C = crédito do item; BC ST = base de cálculo da ST do item (vBCST da própria nota + vBCSTRet da ST
retida antes, ou a base da antecipação informada); VlMerc = valor da
mercadoria na entrada; pRedBc = % de redução de BC; alíquotas em fração (0.18 = 18%).
"""
from dataclasses import dataclass
from typing import Optional

# Regime de apuração (do detentor do estoque e do fornecedor)
RPA = 'RPA'  # Regime Periódico de Apuração
SN = 'SN'    # Simples Nacional

# Responsável pela retenção/antecipação
RET_FORNECEDOR = 'retencao_fornecedor'
ANTEC_ADQUIRENTE = 'antecipacao_adquirente'
RET_SUBST_ANTERIOR = 'retencao_substituto_anterior'

# Operação
INTERNA = 'interna'
INTERESTADUAL = 'interestadual'

# Redução de base de cálculo da ST (texto da portaria)
SEM_REDUCAO = 'sem_reducao'
RED_APLICAVEL_CF = 'reducao_aplicavel_consumidor_final'
RED_NAO_APLICAVEL_CF = 'reducao_nao_aplicavel_consumidor_final'


class NaoPrevistoNaPortaria(ValueError):
    """Combinação de parâmetros sem fórmula nos Anexos IV/V."""


@dataclass
class Resultado:
    credito: float
    anexo: str          # 'IV' ou 'V'
    linha: str          # descrição da linha da tabela aplicada
    formula: str        # fórmula aplicada, como na portaria
    alertas: tuple = ()
    analogia: bool = False   # combinação que o Anexo IV não lista, resolvida pela regra da mesma carga (ver docstring)


def p_red_bc(aliq_interna: float, aliq_efetiva: float) -> float:
    """pRedBc quando a legislação fixa a carga efetiva: (alíquota interna - alíquota efetiva) / alíquota interna."""
    return (aliq_interna - aliq_efetiva) / aliq_interna if aliq_interna > 0 else 0.0


def credito_item(*, regime_detentor: str, regime_fornecedor: str, responsavel: str, operacao: str,
                 reducao: str = SEM_REDUCAO, bc_st: float, vl_merc: float, aliq_interna: float,
                 aliq_interestadual: Optional[float] = None, p_red: float = 0.0) -> Resultado:
    """Crédito (C) de um item de documento fiscal, na quantidade total do item. Escalar por qtd_utilizada/qtd_item."""
    if reducao != SEM_REDUCAO and not p_red:
        raise ValueError('reducao informada mas p_red == 0')
    if regime_detentor == SN:
        return _anexo_v(regime_fornecedor, responsavel, operacao, reducao, bc_st, vl_merc, aliq_interna, p_red)
    if regime_detentor == RPA:
        return _anexo_iv(regime_fornecedor, responsavel, operacao, reducao, bc_st, vl_merc, aliq_interna,
                         aliq_interestadual, p_red)
    raise ValueError(f'regime_detentor inválido: {regime_detentor}')


def _carga_integral(prefixo, red, bc, ai, p, analogia):
    """Regra da linha RPA/RPA do Anexo IV: toda a carga (própria + ST) está na BC ST."""
    if red == RED_APLICAVEL_CF:
        return Resultado(round(bc * (1 - p) * ai, 2), 'IV', f'{prefixo}, redução aplicável ao cons. final',
                         'C = BC ST x (1 - pRedBc) x Alíquota interna', (), analogia)
    rot = 'sem redução' if red == SEM_REDUCAO else 'redução não aplicável ao cons. final'
    return Resultado(round(bc * ai, 2), 'IV', f'{prefixo}, {rot}', 'C = BC ST x Alíquota interna', (), analogia)


def _anexo_iv(forn, resp, oper, red, bc, v, ai, aie, p) -> Resultado:
    R = lambda c, linha, f, alertas=(): Resultado(round(c, 2), 'IV', linha, f, alertas)
    if resp not in (RET_FORNECEDOR, ANTEC_ADQUIRENTE, RET_SUBST_ANTERIOR):
        raise NaoPrevistoNaPortaria(f'Anexo IV: responsável desconhecido {resp}')
    if forn not in (RPA, SN):
        raise NaoPrevistoNaPortaria(f'Anexo IV: regime do fornecedor desconhecido {forn}')
    if forn == RPA:
        if resp in (RET_FORNECEDOR, ANTEC_ADQUIRENTE):  # interna ou interestadual
            # A célula "BC ST x alíquota" abrange sem redução e redução não aplicável ao consumidor final (rowspan 2).
            return _carga_integral('RPA/RPA, retenção forn. ou antecip. adq.', red, bc, ai, p, False)
        return _carga_integral('RPA/RPA, retenção por substituto anterior ao fornecedor (analogia: art. 4º e linha SN/substituto anterior)',
                               red, bc, ai, p, True)
    elif forn == SN:
        if resp == RET_FORNECEDOR and oper == INTERNA:
            if red == SEM_REDUCAO:
                return R((bc - v) * ai, 'RPA/SN, retenção forn., interna, sem redução', 'C = (BC ST - VlMerc) x Alíquota interna')
            if red == RED_NAO_APLICAVEL_CF:
                return R((bc - v) * (1 - p) * ai, 'RPA/SN, retenção forn., interna, redução não aplicável ao cons. final',
                         'C = (BC ST - VlMerc) x (1 - pRedBc) x Alíquota interna')
            return R((bc - v * (1 - p)) * ai, 'RPA/SN, retenção forn., interna, redução aplicável ao cons. final',
                     'C = (BC ST - VlMerc x (1 - pRedBc)) x Alíquota interna')
        if resp == RET_FORNECEDOR and oper == INTERESTADUAL:
            if aie is None:
                raise ValueError('aliq_interestadual obrigatória para operação interestadual com fornecedor SN')
            if red == SEM_REDUCAO:
                return R(bc * ai - v * aie, 'RPA/SN, retenção forn., interestadual, sem redução',
                         'C = BC ST x Alíquota interna - VlMerc x Alíquota interestadual')
            if red == RED_NAO_APLICAVEL_CF:
                return R((bc * ai - v * aie) * (1 - p), 'RPA/SN, retenção forn., interestadual, redução não aplicável ao cons. final',
                         'C = (BC ST x Alíquota interna - VlMerc x Alíquota interestadual) x (1 - pRedBc)')
            return R(bc * ai - v * (1 - p) * aie, 'RPA/SN, retenção forn., interestadual, redução aplicável ao cons. final',
                     'C = BC ST x Alíquota interna - VlMerc x (1 - pRedBc) x Alíquota interestadual')
        if resp == RET_SUBST_ANTERIOR:  # interna ou interestadual
            if red == SEM_REDUCAO:
                return R(bc * ai, 'RPA/SN, retenção por substituto anterior ao fornecedor, sem redução', 'C = BC ST x Alíquota interna')
            return _carga_integral('RPA/SN, retenção por substituto anterior ao fornecedor (analogia: regra RPA/RPA para a redução)',
                                   red, bc, ai, p, True)
        # antecipação pelo adquirente
        if oper == INTERESTADUAL and red in (SEM_REDUCAO, RED_APLICAVEL_CF):
            return _carga_integral('RPA/SN, antecipação pelo adquirente, interestadual', red, bc, ai, p, False)
        if oper == INTERESTADUAL:
            return _carga_integral('RPA/SN, antecipação pelo adquirente, interestadual (analogia: regra RPA/RPA)', red, bc, ai, p, True)
        # interna: leitura conservadora, igual à retenção pelo fornecedor SN na operação interna (a guia abate a operação própria)
        pre = 'RPA/SN, antecipação pelo adquirente, interna (analogia: linha SN/retenção interna)'
        if red == SEM_REDUCAO:
            return Resultado(round((bc - v) * ai, 2), 'IV', f'{pre}, sem redução', 'C = (BC ST - VlMerc) x Alíquota interna', (), True)
        if red == RED_NAO_APLICAVEL_CF:
            return Resultado(round((bc - v) * (1 - p) * ai, 2), 'IV', f'{pre}, redução não aplicável ao cons. final',
                             'C = (BC ST - VlMerc) x (1 - pRedBc) x Alíquota interna', (), True)
        return Resultado(round((bc - v * (1 - p)) * ai, 2), 'IV', f'{pre}, redução aplicável ao cons. final',
                         'C = (BC ST - VlMerc x (1 - pRedBc)) x Alíquota interna', (), True)


def _anexo_v(forn, resp, oper, red, bc, v, ai, p) -> Resultado:
    """Anexo V (detentor SN). Vale para fornecedor RPA ou SN, qualquer responsável, interna ou interestadual.

    ATENÇÃO: no Anexo V os rótulos 'aplicável' / 'não aplicável' ao consumidor final aparecem INVERTIDOS em relação
    ao Anexo IV (mesmas fórmulas, rótulos trocados). Aqui fica a transcrição literal do Anexo V; a escolha da fórmula em cada
    linha (a que reproduz o ICMS-ST da nota) é feita em credito.leitura_anexo_v_por_prova.
    """
    if resp not in (RET_FORNECEDOR, ANTEC_ADQUIRENTE, RET_SUBST_ANTERIOR):
        raise NaoPrevistoNaPortaria(f'Anexo V: responsável desconhecido {resp}')
    alerta = ('Anexo V: rótulos aplicável/não aplicável ao consumidor final divergem do Anexo IV; '
              'conferir qual fórmula vale para a mercadoria.',)
    R = lambda c, linha, f, al=(): Resultado(round(c, 2), 'V', linha, f, al)
    if red == SEM_REDUCAO:
        return R((bc - v) * ai, 'SN, sem redução', 'C = (BC ST - VlMerc) x Alíquota interna')
    if red == RED_APLICAVEL_CF:
        return R((bc - v) * (1 - p) * ai, 'SN, redução aplicável ao cons. final (rótulo literal do Anexo V)',
                 'C = (BC ST - VlMerc) x (1 - pRedBc) x Alíquota interna', alerta)
    return R((bc - v * (1 - p)) * ai, 'SN, redução não aplicável ao cons. final (rótulo literal do Anexo V)',
             'C = (BC ST - VlMerc x (1 - pRedBc)) x Alíquota interna', alerta)


def ratear(valor_item: float, qtd_item: float, qtd_utilizada: float) -> float:
    """Proporção do item do documento fiscal usada para compor o estoque (item 9 do Anexo I)."""
    if qtd_item <= 0:
        raise ValueError('qtd_item deve ser > 0')
    return valor_item * (qtd_utilizada / qtd_item)
