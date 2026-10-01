"""Identificação do estoque pela DESCRIÇÃO, quando o relatório do cliente não traz EAN ou NCM.

Cada ERP exporta o estoque de um jeito. A skill só exige descrição e quantidade; o que faltar (EAN, NCM, CEST, código) é buscado
nas NF-e de compra, que são a fonte fiscal de toda a apuração: a descrição do estoque é comparada com a das notas
(`Localizador.por_descricao`, níveis A/B/C) e, quando há correspondência segura (A ou B, sem ambiguidade), o produto herda da
nota o EAN, o NCM e o CEST. Correspondência fraca ou ambígua não identifica: o item fica fora, com o motivo (sem inventar).

Campos que a função grava em cada linha do estoque:
    ident_por   '' (veio completo) | 'descrição A|B (nota: ...)' | 'nao_identificado'
    ident_nivel nível do casamento ('A'/'B') quando identificado pela descrição
    ident_obs   motivo quando não identificado
"""
import csv
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

VALIDOS = (8, 12, 13, 14)


def _d(s) -> str:
    return re.sub(r'\D', '', str(s or ''))


def _moda(valores) -> str:
    c = Counter(v for v in valores if v)
    return c.most_common(1)[0][0] if c else ''


# ---------------------------------------------------------------- identificação flexível (relatórios com nomes abreviados)
GENERICAS = {'DE', 'DA', 'DO', 'DAS', 'DOS', 'E', 'COM', 'C', 'EM', 'PARA', 'CX', 'CAIXA', 'UN', 'UND', 'UNID', 'UNIDADE', 'UNIDADES',
             'PCT', 'PC', 'PECA', 'ML', 'G', 'GR', 'KG', 'L', 'LT', 'X', 'POTE', 'POTES', 'SORVETE', 'SORV', 'SORVETES', 'PRODUTO'}


def _tokens(texto: str) -> List[str]:
    t = unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode().upper()
    t = re.sub(r'[^A-Z0-9]+', ' ', t)
    t = re.sub(r'(?<=[A-Z])(?=[0-9])|(?<=[0-9])(?=[A-Z])', ' ', t)          # CX14UN -> CX 14 UN; P150 -> P 150
    out = []
    for w in t.split():
        if w in GENERICAS or w.isdigit() or len(w) == 1 or re.fullmatch(r'\d+(ML|G|GR|KG|L|LT|UN|UND|U|X\d*)?', w) or                 re.fullmatch(r'X?\d+X?\d*(ML|G|GR|KG|L)?', w):
            continue
        out.append(w)
    return out


def _embalagem(texto: str) -> Optional[int]:
    """Quantidade por embalagem na descrição: '24X72ML' -> 24; 'CX C/ 18 UN' -> 18."""
    t = str(texto or '').upper()
    m = re.search(r'(\d{1,3})\s*X\s*\d', t) or re.search(r'C/\s*(\d{1,3})', t) or re.search(r'CX\s*(\d{1,3})', t)         or re.search(r'(\d{1,3})\s*(?:UN|UND|U)', t)
    return int(m.group(1)) if m else None


def _casa(a: str, b: str) -> float:
    """Peso do casamento de dois tokens: igual = 1; um é prefixo do outro (abreviação, >= 3 letras) = 0,85."""
    if a == b:
        return 1.0
    if len(a) >= 3 and len(b) >= 3 and (b.startswith(a) or a.startswith(b)):
        return 0.85
    return 0.0


class Catalogo:
    """Produtos das notas de compra (chave -> descrições) com peso IDF dos termos, para a identificação flexível."""

    def __init__(self, loc, compras):
        self.prod: Dict[str, dict] = {}
        df = Counter()
        for k, idxs in loc.linhas_do_produto.items():
            descs = [d for d, _ in Counter(compras[i].get('descricao', '') for i in idxs).most_common(4)]
            toks = [set(_tokens(d)) for d in descs]
            for t in set().union(*toks) if toks else ():
                df[t] += 1
            emit = set()
            for i in idxs:
                emit.update(_tokens(compras[i].get('nome_emitente', '')))          # marca = fornecedor ("ROCHINHA" no nome do emitente)
            self.prod[k] = dict(descs=descs, toks=toks, emb=[_embalagem(d) for d in descs], idxs=idxs, emit=emit)
        self.vocab = set(df)
        self.prefixos = [u for u in df if len(u) >= 3]
        n = max(1, len(self.prod))
        self.idf = defaultdict(lambda: math.log(1 + n), {t: math.log(1 + n / c) for t, c in df.items()})

    def pontuar(self, desc: str, chave: str) -> float:
        p = self.prod[chave]
        te = [t for t in dict.fromkeys(_tokens(desc)) if t in self.vocab or any(_casa(t, u) for u in self.prefixos)]
        if not te:
            return 0.0
        emb_e = _embalagem(desc)
        melhor = 0.0
        for tn, emb_n in zip(p['toks'], p['emb']):
            if not tn:
                continue
            w_total = sum(self.idf[t] for t in te)
            w_ok = sum(self.idf[t] * (1.0 if t in p['emit'] else max((_casa(t, u) for u in tn), default=0.0)) for t in te)
            cobertura = w_ok / w_total
            usados = sum(self.idf[u] * max((_casa(t, u) for t in te), default=0.0) for u in tn)
            precisao = usados / max(1e-9, sum(self.idf[u] for u in tn))
            sc = 0.7 * cobertura + 0.3 * precisao
            if emb_e and emb_n and emb_e != emb_n:
                sc *= 0.6                                   # embalagem diferente: outro produto, na dúvida
            melhor = max(melhor, sc)
        return melhor

    def melhor(self, desc: str) -> Tuple[Optional[str], float, float]:
        ranking = sorted(((self.pontuar(desc, k), k) for k in self.prod), reverse=True)[:2]
        if not ranking:
            return None, 0.0, 0.0
        (s1, k1), (s2, _) = ranking[0], (ranking[1] if len(ranking) > 1 else (0.0, None))
        return k1, s1, s2


LIM_SCORE, LIM_MARGEM = 0.80, 0.10          # com score >= 0,95 basta margem de 0,05


ARQUIVO = 'identificacao_estoque.csv'
CAMPOS = ['descricao', 'melhor_candidato', 'similaridade', 'ean', 'ncm', 'cest', 'observacao']


def _chave(desc: str) -> str:
    return ' '.join(_tokens(desc)) + '|' + str(_embalagem(desc))


def carregar_de_para(pasta: str) -> Dict[str, dict]:
    """<cliente>/identificacao_estoque.csv: EAN/NCM informados para descrições do estoque que a skill não identificou sozinha."""
    caminho = os.path.join(pasta, ARQUIVO)
    if not os.path.exists(caminho):
        return {}
    with open(caminho, encoding='utf-8-sig', newline='') as f:
        return {_chave(r['descricao']): r for r in csv.DictReader(f, delimiter=';') if _d(r.get('ean')) or _d(r.get('ncm'))}


def gravar_pendentes(pasta: str, estoque: List[dict], de_para: Dict[str, dict]) -> Optional[str]:
    """Lista as descrições não identificadas, com o melhor candidato das notas, para informar EAN/NCM (preserva o que já foi informado)."""
    ja = {}
    caminho = os.path.join(pasta, ARQUIVO)
    if os.path.exists(caminho):
        with open(caminho, encoding='utf-8-sig', newline='') as f:
            ja = {_chave(r['descricao']): r for r in csv.DictReader(f, delimiter=';')}
    linhas = list(ja.values())
    vistos = set(ja)
    for e in estoque:
        if e.get('ident_por') != 'nao_identificado':
            continue
        k = _chave(e['descricao'])
        if k in vistos:
            continue
        vistos.add(k)
        linhas.append(dict(descricao=e['descricao'], melhor_candidato=e.get('ident_cand', ''), similaridade=e.get('ident_sim', ''),
                           ean='', ncm='', cest='', observacao=e.get('ident_obs', '')))
    if not linhas:
        return None
    with open(caminho, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, delimiter=';', extrasaction='ignore')
        w.writeheader()
        w.writerows(linhas)
    return caminho


def enriquecer(estoque: List[dict], loc, compras: List[dict], de_para: Optional[Dict[str, dict]] = None) -> Dict[str, int]:
    """Completa EAN/NCM/CEST de cada linha do estoque que não os traz. Devolve contagens."""
    st = Counter()
    catalogo = None
    de_para = de_para or {}
    for e in estoque:
        e.setdefault('ident_por', '')
        if e.get('ean') and e.get('ncm'):
            st['completo'] += 1
            continue
        info = de_para.get(_chave(e.get('descricao', '')))
        if info:                                              # EAN/NCM informados pelo usuário para esta descrição
            e['ean'] = e.get('ean') or _d(info.get('ean'))
            e['ncm'] = e.get('ncm') or _d(info.get('ncm'))
            e['cest'] = e.get('cest') or _d(info.get('cest'))
            e['ident_por'] = f'descrição A (de-para informado em {ARQUIVO})'
            e['ident_nivel'] = 'A'
            st['de_para'] += 1
            continue
        r = loc.por_descricao(dict(descricao=e.get('descricao', ''), ncm=e.get('ncm', ''), valor=e.get('valor') or 0.0))
        seguro = r['metodo'] == 'descricao' and r['nivel'] in ('A', 'B') and not r.get('ambiguo') and r['linhas']
        if not seguro:
            if catalogo is None:
                catalogo = Catalogo(loc, compras)
            chave, s1, s2 = catalogo.melhor(e.get('descricao', ''))
            if chave and s1 >= LIM_SCORE and (s1 - s2) >= (0.05 if s1 >= 0.95 else LIM_MARGEM):
                r = dict(metodo='descricao', nivel='B', chave_produto=chave, linhas=catalogo.prod[chave]['idxs'], ambiguo=False,
                         desc_nota=catalogo.prod[chave]['descs'][0], flexivel=round(s1, 2))
                seguro = True
        if not seguro:
            if catalogo is not None and chave:
                e['ident_cand'], e['ident_sim'] = catalogo.prod[chave]['descs'][0], round(s1, 2)
            e['ident_por'] = 'nao_identificado'
            e['ident_obs'] = ('; '.join(r.get('observacoes') or [])) or 'nenhuma nota de compra com descrição equivalente'
            st['nao_identificado'] += 1
            continue
        linhas = [compras[i] for i in r['linhas']]
        ncm = _moda([_d(c.get('ncm')) for c in linhas if len(_d(c.get('ncm'))) == 8])
        ean = _d(r.get('chave_produto')) if len(_d(r.get('chave_produto'))) in VALIDOS and not str(r.get('chave_produto')).startswith('SEMEAN') \
            else _moda([_d(c.get('ean')) for c in linhas if len(_d(c.get('ean'))) in VALIDOS])
        if not e.get('ean') and ean:
            e['ean'] = ean
        if not e.get('ncm') and ncm:
            e['ncm'] = ncm
        if not e.get('cest'):
            e['cest'] = _moda([_d(c.get('cest')) for c in linhas if len(_d(c.get('cest'))) == 7])
            e['cest_origem'] = 'nfe_descricao' if e['cest'] else e.get('cest_origem', '')
        flex = f", similaridade {r['flexivel']}" if r.get('flexivel') else ''
        e['ident_por'] = f"descrição {r['nivel']}{' flexível' if r.get('flexivel') else ''} (nota: {r.get('desc_nota') or linhas[0].get('descricao', '')[:60]}{flex})"
        e['ident_nivel'] = r['nivel']
        st['por_descricao'] += 1
    return dict(st)
