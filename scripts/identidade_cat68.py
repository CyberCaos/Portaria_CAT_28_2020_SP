"""Identidade da mercadoria contra a descrição legal do item da CAT 68/2019 (triagem com evidência).

O NCM é só a busca inicial (triagem.py). Para a mercadoria ser confirmada no item da CAT 68 é preciso evidência de que ELA é o
produto descrito no item da CAT 68 que saiu da ST naquela data. As evidências, registradas linha a linha:

1. descrição do produto compatível com a descrição legal do item:
   - itens de medicamentos (Anexo IX, "Medicamentos ..." / "Outros tipos de medicamentos"): NCM 3003/3004/3006 e descrição
     com dose ou forma farmacêutica (MG, ML, UI, COMP, CAPS, GTS, SOL, XPE, POM...);
   - demais itens: termo significativo da descrição legal (ou sinônimo de catálogo: SHAMPOO = xampu, DEO = desodorante,
     FD = fralda...) presente na descrição do produto, comparando raízes de 5 letras com o plural reduzido;
2. CEST da nota (pelo EAN) igual ao CEST do item: confirma; diferente: CONTRADIZ (a classificação do fornecedor aponta um
   CEST que não é item revogado para esse NCM); ausente ou ambíguo: não impede, se a descrição for compatível;
3. data de exclusão e ato revogador do item (tabela oficial consolidada).

Sem descrição compatível, ou com CEST contraditório, a mercadoria leva observação do cálculo e vai para `<cliente>/identidade_cat68.csv`,
onde a análise (ou o usuário) registra a evidência (tipo, fonte, apresentação exata) e a decisão.
"""
import csv
import os
import re
import unicodedata
from functools import lru_cache

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CAT68 = os.path.join(RAIZ, 'references', 'base-legal', 'cat68-2019-produtos-revogados.csv')

PARADAS = set('''OUTROS OUTRAS OUTRO OUTRA PREPARACOES PREPARACAO PREPARADOS PREPARADO PRODUTOS PRODUTO EXCETO PARA COM SEM DOS DAS DO DA DE
E OU A O AS OS EM NAO QUE SEUS SUAS USO TIPO TIPOS INCLUSIVE INCLUINDO INCLUIDOS INCLUIDAS DESCRITOS DESCRITO CEST NCM ITEM ITENS
ACONDICIONADOS ACONDICIONADO ACONDICIONADAS VENDA RETALHO EMBALAGEM EMBALAGENS CAPACIDADE IGUAL SUPERIOR INFERIOR ATE POSITIVA
NEGATIVA NEUTRA VETERINARIO HUMANO MESMO MESMA QUANDO DESTINADOS DESTINADAS BASE PELO PELA PELOS ESPECIE ESPECIES CUJO CUJA SEJA
SEJAM ESTES ESTAS ESSES ESSAS ONDE CONTENDO CONTENHAM PRONTOS PRONTAS CLASSIFICADOS CLASSIFICADAS POSICOES POSICAO SUBPOSICAO
SUBITEM CAPITULO ACORDO CONFORME RELACAO GERAL ESPECIAL PROPRIOS PROPRIAS FINS DIVERSOS DIVERSAS MATERIA MATERIAS'''.split())
# sinônimos de catálogo (palavra, raiz ou prefixo do produto) -> raiz de 5 letras do termo legal
SINONIMOS = {
    'SHAMP': 'XAMPU', 'DEO': 'DESOD', 'DESOD': 'ANTIP', 'ANTIT': 'ANTIP', 'ANTIP': 'DESOD', 'AEROS': 'DESOD',
    'FR': 'FRALD', 'FD': 'FRALD', 'FRALD': 'FRALD', 'GERIA': 'FRALD', 'TINT': 'TINTU', 'COLOR': 'TINTU', 'ESMAL': 'MANIC',
    'ACETO': 'MANIC', 'REMOV': 'MANIC', 'LIXA': 'MANIC', 'CHUP': 'CHUPE', 'BICO': 'BICO', 'MAMAD': 'MAMAD', 'GAZE': 'GAZE',
    'ALGOD': 'ALGOD', 'ATAD': 'ATADU', 'ESPAR': 'ESPAR', 'CURAT': 'PENSO', 'BAND': 'PENSO', 'SAB': 'SABAO', 'SABON': 'SABAO',
    'SABAO': 'SABAO', 'DENTA': 'DENTI', 'DENTI': 'DENTI', 'CR': 'CREME', 'ESCOV': 'ESCOV', 'ABSOR': 'ABSOR', 'PROTE': 'SOLAR',
    'FPS': 'SOLAR', 'CONDI': 'CONDI', 'HIDRA': 'CREME', 'LOCAO': 'LOCAO', 'PERFU': 'PERFU', 'PARFU': 'PERFU', 'COLON': 'COLON',
    'PRESE': 'PRESE', 'SERIN': 'SERIN', 'AGULH': 'AGULH', 'LUVA': 'LUVA', 'MASCA': 'MASCA', 'FIO': 'FIO', 'TOALH': 'TOALH',
    'LENCO': 'LENCO', 'SERUM': 'CREME', 'BAUME': 'CREME', 'GEL': 'CREME',
}
# termos de cosmético para os itens genéricos de cuidado da pele, solares, capilares e higiene bucal (Anexo XI)
for _p in ('HIDRA', 'HYDRA', 'SERUM', 'CREME', 'LOCAO', 'TALCO', 'DEMAQ', 'MICEL', 'TONIC', 'ESFOL', 'FACIA', 'CORPO', 'ANTIM',
           'ANTIR', 'REPAR', 'CICAT', 'CLARE', 'OLEO'):
    SINONIMOS.setdefault(_p, 'CUIDA')
for _p, _t in (('FP', 'SOLAR'), ('FPS', 'SOLAR'), ('SOLAR', 'SOLAR'), ('BRONZ', 'SOLAR'), ('LEAVE', 'CAPIL'), ('PENTE', 'CAPIL'),
               ('CABEL', 'CAPIL'), ('CAPIL', 'CAPIL'), ('FINAL', 'FINAL'), ('ENXAG', 'BUCAL'), ('BUCAL', 'BUCAL'), ('ORAL', 'BUCAL'),
               ('ANTIS', 'BUCAL')):
    SINONIMOS.setdefault(_p, _t)
# um mesmo termo do produto pode servir a mais de um item genérico: CREME vale para "cremes de beleza" e "cuidados da pele"
MULTI = {'CREME': ('CREME', 'CUIDA'), 'HIDRA': ('CREME', 'CUIDA'), 'LOCAO': ('LOCAO', 'CUIDA'), 'GEL': ('CREME', 'CUIDA'),
         'SERUM': ('CREME', 'CUIDA'), 'CONDI': ('CONDI', 'CAPIL')}
_FORMAS = ('COMP|CPR|CP|CPS|CAPS|CAP|CAPSULAS|CAPSULA|DRG|DRAGEAS|GTS|GOTAS|SOL|SUSP|XPE|XAROPE|POM|POMADA|AMP|INJ|SPRAY|FLAC|ENV|'
           'SACHE|SACHES|SUP|SUPOSITORIOS|OVULO|OVUL|ADES|COL|COLIRIO|EMULS|ELIX|INAL|AEROSSOL|GRAN|COMPRIMIDOS|LIOF|PO')
RE_MEDICAMENTO = re.compile(r'\d+(?:[.,]\d+)?\s*(?:MG|MCG|ML|G|UI|%|MEQ)(?![A-Z])|(?<![A-Z])(?:' + _FORMAS + r')(?![A-Z])')


def _norm(t) -> str:
    t = unicodedata.normalize('NFKD', str(t or '')).encode('ascii', 'ignore').decode().upper()
    return re.sub(r'[^A-Z0-9%,.+/ ]+', ' ', t)


def _dig(v) -> str:
    return re.sub(r'\D', '', str(v or ''))


def _raiz(w: str) -> str:
    """Raiz de 5 letras com o plural do português reduzido ao singular (LOCOES -> LOCAO, CREMES -> CREME, PAPEIS -> PAPEL)."""
    for fim, troca in (('OES', 'AO'), ('AES', 'AO'), ('EIS', 'EL'), ('NS', 'M'), ('ES', 'E'), ('S', '')):
        if len(w) > 4 and w.endswith(fim):
            w = w[: -len(fim)] + troca
            break
    return w[:5]


@lru_cache(maxsize=1)
def itens_cat68():
    with open(CAT68, encoding='utf-8-sig', newline='') as f:
        linhas = list(csv.DictReader(f, delimiter=';'))
    idx = {}
    for l in linhas:
        l = {k.replace('﻿', ''): v for k, v in l.items()}
        idx[(l['anexo'].strip(), l['item'].strip())] = l
    return idx


@lru_cache(maxsize=1)
def itens_vigentes():
    """Itens que continuam na ST (cat68-2019-itens-vigentes.csv), por (anexo, item)."""
    with open(CAT68.replace('produtos-revogados', 'itens-vigentes'), encoding='utf-8-sig', newline='') as f:
        linhas = list(csv.DictReader(f, delimiter=';'))
    idx = {}
    for l in linhas:
        l = {k.replace('\ufeff', ''): v for k, v in l.items()}
        idx[(l['anexo'].strip(), l['item'].strip())] = l
    return idx


def termos_legais(descricao_legal: str):
    palavras = [w for w in re.findall(r'[A-Z]+', _norm(descricao_legal)) if len(w) >= 4 and w not in PARADAS]
    return sorted({_raiz(w) for w in palavras})


def _termos_produto(descricao: str):
    out = set()
    for w in re.findall(r'[A-Z]+', _norm(descricao)):
        out.add(_raiz(w))
        out.add(w[:5])
        for chave in (w, w[:5], w[:4], w[:3], w[:2]):
            if chave in SINONIMOS:
                out.add(SINONIMOS[chave])
            out.update(MULTI.get(chave, ()))
    return out


def e_item_de_medicamento(desc_legal: str) -> bool:
    d = _norm(desc_legal)
    return d.startswith('MEDICAMENTOS') or d.startswith('OUTROS TIPOS DE MEDICAMENTOS')


def _n_itens_do_ncm(ncm: str) -> int:
    """Itens da CAT 68 (revogados e vigentes) que o NCM alcança por prefixo."""
    achados = set()
    for idx in (itens_cat68(), itens_vigentes()):
        for chave, leg in idx.items():
            if any(_dig(t) and ncm.startswith(_dig(t)) for t in str(leg.get('ncm', '')).split()):
                achados.add(chave)
    return len(achados)


def avaliar(produto: dict, anexo: str, item: str, vigente: bool = False) -> dict:
    """produto: {descricao, ncm, cest, cest_origem}. Devolve {confirmada, evidencias, motivo, descricao_legal, ato, data_revogacao,
    situacao_cest}. Com vigente=True o item é um dos que continuam na ST (serve para comparar a descrição)."""
    leg = (itens_vigentes() if vigente else itens_cat68()).get((str(anexo).strip(), str(item).strip()))
    if not leg:
        return dict(confirmada=False, evidencias=[], motivo=f'item {anexo}/{item} não encontrado na tabela da CAT 68', descricao_legal='',
                    ato='', data_revogacao='', situacao_cest='')
    desc_legal = leg.get('descricao', '')
    evid, motivo = [], ''
    d = _norm(produto.get('descricao', ''))
    ncm = _dig(produto.get('ncm'))
    if e_item_de_medicamento(desc_legal):
        compat = ncm.startswith(('3003', '3004', '3006')) and bool(RE_MEDICAMENTO.search(d))
        pontos = 2 if compat else 0
        if compat:
            evid.append('descrição com dose/forma farmacêutica e NCM de medicamento')
    else:
        comuns = sorted(set(termos_legais(desc_legal)) & _termos_produto(d))
        compat = bool(comuns)
        pontos = len(comuns)
        if compat:
            evid.append('termo da descrição legal na descrição do produto: ' + ', '.join(comuns[:4]))
    # NCM específico do item (subposição de 6+ dígitos, ex.: 2105.00 = sorvetes) identifica o produto por si; NCM de capítulo/posição
    # (4 dígitos) não: ali a descrição decide
    esp = max((len(_dig(t)) for t in str(leg.get('ncm', '')).split() if _dig(t) and ncm.startswith(_dig(t))), default=0)
    if not compat and esp >= 6 and _n_itens_do_ncm(ncm) == 1:           # só quando nenhum outro item da CAT 68 alcança o mesmo NCM
        compat = True
        evid.append(f'NCM {ncm} específico do item (subposição de {esp} dígitos)')
    cest_item, cest_prod = _dig(leg.get('cest')), _dig(produto.get('cest'))
    origem = produto.get('cest_origem', '')
    if cest_prod and origem != 'nfe_ean_ambiguo':
        situacao_cest = 'confirma' if cest_prod == cest_item else 'contradiz'
    else:
        situacao_cest = 'ambíguo' if origem == 'nfe_ean_ambiguo' else 'ausente'
    if situacao_cest == 'confirma':
        evid.append(f'CEST da nota {leg.get("cest")} igual ao do item')
    evid.append(f'exclusão: {leg.get("ato_revogador", "")} com efeito em {leg.get("data_revogacao", "")}')
    if not compat:
        motivo = (f'identidade não confirmada: a descrição do produto não corresponde à descrição legal do item {anexo}/{item} '
                  f'("{desc_legal[:90]}")')
    elif situacao_cest == 'contradiz':
        motivo = f'CEST da nota ({produto.get("cest")}) não é o do item {anexo}/{item} ({leg.get("cest")}): conferir a classificação da mercadoria'
    return dict(confirmada=compat and situacao_cest != 'contradiz', evidencias=evid, motivo=motivo, descricao_legal=desc_legal,
                ato=leg.get('ato_revogador', ''), data_revogacao=leg.get('data_revogacao', ''), situacao_cest=situacao_cest,
                pontos=pontos if situacao_cest != 'contradiz' else 0, pontos_desc=pontos if compat else 0)
