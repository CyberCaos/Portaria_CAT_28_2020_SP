"""Passo 5: fator de conversão da unidade da NOTA para a unidade do ESTOQUE (UND), usando só os XMLs de compra e a
descrição do estoque (o usuário não envia vendas).

O estoque conta em unidade de venda (UND). A nota pode vender a mesma mercadoria em fardo, caixa, display
("FD 06X34UN", "DISPLAY C/24 FLAC", "X 60 FLAC") ou em unidade solta quando o estoque guarda a caixa ("AG DESC ... AVULSO").
O fator diz quantas unidades de estoque equivalem a 1 unidade da nota (pode ser fracionário):
    qtd_estoque_equivalente = qtd_da_nota x fator
Por que isso importa: a base de ST unitária é `base da linha / (qtd da nota x fator)`. Fator MENOR que o verdadeiro
faz a base unitária sair maior e SUPERCONTA o crédito; por isso a dúvida nunca vira crédito confirmado.

Candidatos (da nota ou da descrição do estoque):
  1. XML      : qTrib/qCom quando o XML declara quantidade tributável diferente (EAN tributável = unidade do estoque).
  2. NOTA     : embalagem da descrição da nota ("C/24", "X 60", "06X34UN" -> 6 fardos, 204 total), quando o estoque não
                traz embalagem, ou múltiplo inteiro da embalagem do estoque. Número que aparece igual na descrição do
                estoque NÃO é embalagem da nota (é atributo do produto: "30X7" = calibre da agulha).
  3. ESTOQUE  : embalagem do estoque quando a nota vende a unidade solta (fator 1/n).
  4. 1        : sempre candidato; é o padrão quando as duas descrições trazem a mesma embalagem.
O preço arbitra entre candidatos: razão r = (preço da nota / fator) / custo do estoque. O custo do estoque costuma ser
um pouco MAIOR que o preço da nota (ST, frete, rateios), por isso a faixa aceita é 0,4 <= r <= 1,8 para fator != 1 e
0,4 <= r <= 2,2 para fator 1. O preço NÃO cria fator: sem candidato de origem declarada, o fator é 1.
Confiança: A = XML confirmado pelo preço, ou fator 1 com descrições concordantes e preço coerente; B = fator da
descrição confirmado pelo preço, ou fator 1 com preço apenas plausível; C = não há prova (inclui preço da nota >= 8x
o custo com descrições iguais: a unidade do estoque pode ser menor que a da nota). C fica em revisão.
"""
import math
import re
from typing import Dict, Optional

import casamento_descricao as CD

R_MIN, R_MAX_K, R_MAX_1 = 0.4, 1.8, 2.2
R_EXTREMO = 8.0            # preço da nota >= 8x o custo (ou <= 1/8) com descrições iguais: dúvida séria de unidade
MELHORA_MIN = 0.25         # fator != 1 precisa melhorar em 0,25 (log) sobre o fator 1 para ser preferido


def _candidatos_descricao(n_desc: str, e_desc: str, e: CD.Atributos, n: CD.Atributos) -> Dict[float, str]:
    cands: Dict[float, str] = {}
    texto_n, _ = CD.normalizar(n_desc)
    texto_e, _ = CD.normalizar(e_desc)
    m = re.search(r'\b(\d+)\s*X\s*(\d+)\s*(?:UN|UND|UNID|PC|PCT)?\b', texto_n)
    if m and int(m.group(1)) >= 2 and not re.search(rf'\b{m.group(1)}\s*X\s*{m.group(2)}\b', texto_e):
        cands[float(m.group(1))] = 'descrição da nota (fardo n X m)'
        cands[float(int(m.group(1)) * int(m.group(2)))] = 'descrição da nota (total n X m)'
    if n.qtd and n.qtd >= 2:
        if e.qtd is None:
            cands.setdefault(float(n.qtd), 'descrição da nota (embalagem); estoque sem embalagem')
        elif e.qtd and n.qtd != e.qtd and n.qtd % e.qtd == 0:
            cands[float(n.qtd // e.qtd)] = 'múltiplo da embalagem do estoque'
    if e.qtd and e.qtd >= 2 and n.qtd is None:
        cands[1.0 / e.qtd] = 'nota vende unidade solta; estoque guarda embalagem'
    return {k: v for k, v in cands.items() if 1 / 1000 <= k <= 1000 and abs(k - 1) > 1e-9}


def fator_linha(estoque: dict, linha: dict) -> dict:
    """estoque: {descricao, valor (custo unitário)}; linha: linha canônica da compra.
    Devolve {fator, origem, confianca, observacao, alternativas}."""
    e_desc, n_desc = estoque.get('descricao', ''), linha.get('descricao', '')
    e, n = CD.extrair(e_desc), CD.extrair(n_desc)
    qtd, qtrib = float(linha.get('qtd') or 0), float(linha.get('qtd_trib') or 0)
    preco = float(linha.get('vl_merc') or 0) / qtd if qtd > 0 else 0.0
    custo = float(estoque.get('valor') or 0)
    tem_preco = preco > 0 and custo > 0
    fx_xml = round(qtrib / qtd, 6) if qtd > 0 and qtrib > 0 else 1.0
    xml_declara = abs(fx_xml - 1) > 1e-6
    mesma_embalagem = (e.qtd is not None and e.qtd == n.qtd) or (e.qtd is None and n.qtd is None)

    cands: Dict[float, str] = {1.0: 'unidade = unidade'}
    if xml_declara:
        cands[fx_xml] = 'XML (qTrib/qCom)'
    for k, o in _candidatos_descricao(n_desc, e_desc, e, n).items():
        cands.setdefault(k, o)
    avulso: Optional[float] = float(n.qtd) if (n.qtd and n.qtd >= 2 and n.qtd == e.qtd) else None   # só como hipótese extrema

    def r_(k: float) -> float:
        return (preco / k) / custo if tem_preco else math.nan

    def dist(k: float) -> float:
        return abs(math.log(r_(k))) if tem_preco else math.inf

    ordem = sorted(cands, key=lambda k: (dist(k), abs(math.log(k))))
    alternativas = [(round(k, 4), cands[k], round(r_(k), 2) if tem_preco else None) for k in ordem[:4]]
    r1 = r_(1.0)
    extremo = tem_preco and (r1 >= R_EXTREMO or r1 <= 1 / R_EXTREMO)
    obs_preco = f'preço da nota R$ {preco:.2f} x custo R$ {custo:.2f} (razão {r1:.1f}x)' if tem_preco and not (R_MIN <= r1 <= R_MAX_1) else ''

    if len(cands) == 1:                                              # nada sugere outro fator
        if extremo and mesma_embalagem:
            if avulso and R_MIN <= r_(avulso) <= R_MAX_K:            # preço só fecha se o estoque contar unidade avulsa
                return dict(fator=avulso, origem='preço indica unidade avulsa (embalagem igual nas duas descrições)', confianca='B',
                            observacao=f'preço convertido R$ {preco / avulso:.2f} x custo R$ {custo:.2f}', alternativas=alternativas)
            return dict(fator=1.0, origem='sem prova', confianca='C',
                        observacao='descrições iguais, mas ' + obs_preco + ': a unidade do estoque pode ser menor que a da nota',
                        alternativas=alternativas)
        if extremo:
            return dict(fator=1.0, origem='sem prova', confianca='C', observacao=obs_preco, alternativas=alternativas)
        ok = tem_preco and R_MIN <= r1 <= R_MAX_1
        return dict(fator=1.0, origem='padrão: mesma unidade', confianca='A' if (mesma_embalagem and (ok or not tem_preco)) else 'B',
                    observacao=obs_preco, alternativas=alternativas)
    if not tem_preco:                                                # só o XML declarado vale sem preço
        if xml_declara:
            return dict(fator=fx_xml, origem=cands[fx_xml], confianca='B', observacao='sem preço para conferir', alternativas=alternativas)
        return dict(fator=1.0, origem='sem preço para decidir', confianca='C', observacao='há candidatos de fator e nenhum preço para arbitrar',
                    alternativas=alternativas)
    melhor = ordem[0]
    if melhor != 1.0 and R_MIN <= r_(melhor) <= R_MAX_K and (dist(1.0) - dist(melhor)) >= MELHORA_MIN:
        conf = 'A' if xml_declara and abs(melhor - fx_xml) < 1e-6 else 'B'
        return dict(fator=melhor, origem=cands[melhor], confianca=conf,
                    observacao=f'preço convertido R$ {preco / melhor:.2f} x custo R$ {custo:.2f}', alternativas=alternativas)
    if R_MIN <= r1 <= R_MAX_1:                                       # preço coerente com fator 1
        obs = f'XML declara fator {fx_xml:g}, mas o preço indica 1' if xml_declara else ''
        return dict(fator=1.0, origem='preço coerente com fator 1', confianca='B' if (xml_declara or not mesma_embalagem) else 'A',
                    observacao=obs, alternativas=alternativas)
    if mesma_embalagem and not xml_declara and not extremo:          # descrições iguais, preço atípico moderado
        return dict(fator=1.0, origem='descrições com a mesma embalagem', confianca='B', observacao=obs_preco, alternativas=alternativas)
    return dict(fator=1.0, origem='sem prova', confianca='C',
                observacao=f'candidatos {[round(k, 3) for k in ordem[:3]]} não fecham com o custo R$ {custo:.2f} (nota R$ {preco:.2f})',
                alternativas=alternativas)
