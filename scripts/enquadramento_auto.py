"""Enquadramento automático da redução de base de cálculo: a redução alcança ou não a venda ao consumidor final?

A CAT 28/2020 tem duas fórmulas para a linha de nota com redução de BC, conforme a redução seja "aplicável" ou "não aplicável
ao consumidor final". O XML não diz isso; quem diz é o dispositivo do RICMS/SP que concede a redução
(`references/base-legal/ricms-sp-reducoes.csv`). O automático só decide com IDENTIFICAÇÃO POSITIVA dos atributos que o
dispositivo exige; carga destacada na nota e NCM são indícios, nunca confirmação:

- RICMS/SP Anexo II, art. 3º, XXIV (medicamentos, carga 7%, toda a cadeia: RC 4231/2014): o princípio ativo listado precisa
  estar ESCRITO na descrição (marca não basta). Associações são condições conjuntas: "amoxicilina + clavulanato" exige os dois;
  descrição com "+" só passa se houver mais de um princípio do inciso identificado (ex.: tramadol + paracetamol); "+" com um só
  princípio identificado (ex.: paracetamol + cafeína, levonorgestrel + etinilestradiol) vai para análise. Também exige NCM de
  medicamento (3003, 3004, 3006), operação interna em SP e emissão dentro da vigência do inciso. Carga da nota diferente de 7%
  não impede o enquadramento, mas marca a linha como divergente (a linha leva observação do cálculo).

- RICMS/SP Anexo II, art. 39, XIV (sorvetes, NCM 2105.00.10 e 2105.00.90, carga 12%, saída de fabricante ou atacadista; o § 1º exclui
  a saída a consumidor final e a empresa do Simples Nacional: RC 23159/2021 e RC 29390/2024). O NCM 2105.00 identifica o produto
  por si (sorvete de qualquer espécie); exige operação interna SP e emissão na vigência. A condição "fabricante ou atacadista" não
  consta do XML e fica registrada na justificativa. Redução NÃO aplicável ao consumidor final.

Todo o resto (art. 34, demais itens do art. 39, demais incisos do art. 3º, redução de fornecedor de outra UF) fica para análise: a
descrição do produto precisa ser conferida com o dispositivo. A marca conhecida vira só sugestão no arquivo de enquadramento.
"""
import csv
import os
import re
import unicodedata
from datetime import date, datetime
from functools import lru_cache
from typing import Optional

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TABELA = os.path.join(RAIZ, 'references', 'base-legal', 'ricms-sp-reducoes.csv')
APLICAVEL = 'reducao_aplicavel_consumidor_final'
NAO_APLICAVEL = 'reducao_nao_aplicavel_consumidor_final'
TOLERANCIA_CARGA = 0.06          # pontos percentuais (61,11% de 18% = 7,0002%)

DISPOSITIVO_XXIV = 'RICMS/SP Anexo II art. 3º XXIV'
CARGA_XXIV = 7.0
VIGENCIA_XXIV = (date(2014, 7, 4), date(2026, 12, 31))      # Decreto 60.630/2014 (DOE 04/07/2014) até Decreto 69.207/2024
NCM_MEDICAMENTO = ('3003', '3004', '3006')
DISPOSITIVO_39_XIV = 'RICMS/SP Anexo II art. 39 XIV'
CARGA_39 = 12.0
VIGENCIA_39 = (date(2014, 1, 1), date(2026, 12, 31))          # Decretos 69.207/2024 e 70.293/2025 (tabela de dispositivos)
NCM_SORVETE = ('21050010', '21050090')
# princípio ativo do inciso -> padrões que TODOS precisam aparecer na descrição (condição conjunta para associações)
PRINCIPIOS_XXIV = [
    ('paracetamol', [r'PARACETAMOL|ACETAMINOFEN']),
    ('tramadol', [r'TRAMADOL']),
    ('montelucaste de sódio', [r'MONTELUCAST|MONTELUKAST']),
    ('amoxicilina + clavulanato', [r'AMOXICILINA|\bAMOX\b|\bAMOXI\b', r'CLAVULAN|\bCLAV\b|\bCLAVUL\b']),
    ('levonorgestrel', [r'LEVONORGESTREL']),
    ('carbamazepina', [r'CARBAMAZEPINA']),
    ('ibuprofeno', [r'IBUPROFENO']),
    ('sulfato de glicosamina/condroitina', [r'GLICOSAMINA']),
]
# marcas: SÓ sugestão para a análise (não é identificação positiva)
MARCAS_XXIV = {
    'TYLENOL': 'paracetamol', 'VICK PYRENA': 'paracetamol', 'DORIL': 'paracetamol', 'PARATRAM': 'tramadol + paracetamol',
    'REVANGE': 'tramadol + paracetamol', 'ATRACE': 'tramadol + paracetamol', 'ULTRACET': 'tramadol + paracetamol',
    'TRAMAL': 'tramadol', 'TRAMADON': 'tramadol', 'TRAUM': 'tramadol', 'CLAVULIN': 'amoxicilina + clavulanato',
    'SIGMA CLAV': 'amoxicilina + clavulanato', 'ATAK CLAV': 'amoxicilina + clavulanato', 'NORDETTE': 'levonorgestrel',
    'LEVEL': 'levonorgestrel', 'GESTRELAN': 'levonorgestrel', 'MICROVLAR': 'levonorgestrel', 'POSTINOR': 'levonorgestrel',
    'ALIVIUM': 'ibuprofeno', 'BUSCOFEM': 'ibuprofeno', 'ADVIL': 'ibuprofeno', 'MONTELAIR': 'montelucaste',
    'PIEMONTE': 'montelucaste', 'SINGULAIR': 'montelucaste', 'TEGRETOL': 'carbamazepina', 'CONDROFLEX': 'glicosamina + condroitina',
}


def _norm(t) -> str:
    t = unicodedata.normalize('NFKD', str(t or '')).encode('ascii', 'ignore').decode().upper()
    return re.sub(r'\s+', ' ', t)


def _dig(v) -> str:
    return re.sub(r'\D', '', str(v or ''))


def _data(v) -> Optional[date]:
    try:
        return datetime.strptime(str(v)[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


@lru_cache(maxsize=1)
def tabela():
    """Tabela de referência dos dispositivos (usada pela análise e para achar a carga legal do dispositivo citado)."""
    with open(TABELA, encoding='utf-8-sig', newline='') as f:
        linhas = list(csv.DictReader(f, delimiter=';'))
    for l in linhas:
        l['_carga'] = float(l['carga']) if (l.get('carga') or '').strip() else None
    return linhas


def principios_xxiv(descricao: str):
    """Princípios ativos do inciso XXIV identificados POSITIVAMENTE na descrição (todas as condições de cada um)."""
    d = _norm(descricao)
    return [nome for nome, padroes in PRINCIPIOS_XXIV if all(re.search(p, d) for p in padroes)]


def sugestao_marca(descricao: str) -> str:
    d = _norm(descricao)
    for marca, ativo in MARCAS_XXIV.items():
        if re.search(rf'\b{marca}\b', d):
            return f'sugestão para análise: a marca {marca.title()} costuma ser {ativo}; conferir a composição do produto'
    return ''


def _classificar_sorvete(c: dict, p: float) -> Optional[dict]:
    """Art. 39, XIV: sorvetes (NCM 2105.00.10/.90), identificados pelo próprio NCM; carga 12%; não alcança o consumidor final."""
    if _dig(c.get('ncm')) not in NCM_SORVETE:
        return None
    if str(c.get('uf_emitente') or '') != 'SP' or str(c.get('uf_destinatario') or '') != 'SP':
        return None
    emissao = _data(c.get('data_emissao'))
    if not emissao or not (VIGENCIA_39[0] <= emissao <= VIGENCIA_39[1]):
        return None
    aliq = float(c.get('p_icms') or 0) or float(c.get('p_icms_st') or 0)
    carga = aliq * (1 - p / 100) if aliq > 0 else None
    divergente = carga is None or abs(carga - CARGA_39) > TOLERANCIA_CARGA
    nota = (f'carga da nota {carga:.2f}% confere com os 12% do dispositivo' if not divergente else
            f'carga da nota {"desconhecida" if carga is None else f"{carga:.2f}%"} diferente dos 12% do dispositivo (indício contrário: conferir)')
    return dict(reducao=NAO_APLICAVEL, dispositivo=DISPOSITIVO_39_XIV, carga=CARGA_39, divergente=divergente, evidencia_tipo='descricao_e_classificacao',
                justificativa=f'automático: {DISPOSITIVO_39_XIV}, sorvete identificado pelo NCM {c.get("ncm")}; operação interna SP, emissão '
                              f'{emissao.strftime("%d/%m/%Y")} na vigência; {nota}; alcance: o § 1º exclui a saída a consumidor final (redução não aplicável); '
                              'o benefício é de fabricante ou atacadista (condição não verificável no XML)')


def classificar(c: dict, regime: str = '') -> Optional[dict]:
    """c: linha de compra (compras.csv). Devolve {reducao, dispositivo, carga, divergente, justificativa} ou None (análise)."""
    p_st, p_prop = float(c.get('p_red_bc_st') or 0), float(c.get('p_red_bc') or 0)
    tem_st = float(c.get('vbc_st') or 0) > 0
    if not (p_st > 0 or (p_prop > 0 and tem_st)):
        return None
    if _dig(c.get('ncm')) in NCM_SORVETE:
        return _classificar_sorvete(c, p_st if p_st > 0 else p_prop)
    if not _dig(c.get('ncm')).startswith(NCM_MEDICAMENTO):
        return None
    if str(c.get('uf_emitente') or '') != 'SP' or str(c.get('uf_destinatario') or '') != 'SP':
        return None                                                  # o inciso vale para operações internas de SP
    emissao = _data(c.get('data_emissao'))
    if not emissao or not (VIGENCIA_XXIV[0] <= emissao <= VIGENCIA_XXIV[1]):
        return None
    achados = principios_xxiv(c.get('descricao', ''))
    if not achados:
        return None
    desc = _norm(c.get('descricao', ''))
    if '+' in desc and len(achados) < 2 and 'amoxicilina + clavulanato' not in achados:
        return None                                                  # associação com princípio fora do inciso: análise
    p = p_st if p_st > 0 else p_prop
    aliq = float(c.get('p_icms') or 0) or float(c.get('p_icms_st') or 0)
    carga = aliq * (1 - p / 100) if aliq > 0 else None
    divergente = carga is None or abs(carga - CARGA_XXIV) > TOLERANCIA_CARGA
    regra = next((r for r in tabela() if r['dispositivo'] == DISPOSITIVO_XXIV), {})
    nota = (f'carga da nota {carga:.2f}% confere com os 7% do inciso' if not divergente else
            f'carga da nota {"desconhecida" if carga is None else f"{carga:.2f}%"} diferente dos 7% do inciso (indício contrário: conferir)')
    return dict(reducao=APLICAVEL, dispositivo=DISPOSITIVO_XXIV, carga=CARGA_XXIV, divergente=divergente,
                justificativa=f'automático: {DISPOSITIVO_XXIV}, princípio ativo identificado na descrição ({" + ".join(achados)}); '
                              f'NCM {c.get("ncm")}, operação interna SP, emissão {emissao.strftime("%d/%m/%Y")} na vigência; {nota}; '
                              f'alcance: {regra.get("alcance_consumidor_final", "toda a cadeia")}')
