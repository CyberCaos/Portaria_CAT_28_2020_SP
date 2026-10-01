"""Passo 2: triagem do estoque pela REGRA DE OURO (definida pelo usuário).

Na CAT 68/2019 houve anexos que saíram POR INTEIRO e anexos que saíram PARCIALMENTE. Para o item do estoque entrar no
levantamento:
    anexo de saída completa  -> só o NCM (prefixo: o NCM do produto começa com o NCM do anexo)
    anexo de saída parcial   -> NCM + CEST
O estoque não traz CEST: ele é resolvido pelo EAN nas NF-e de compra (`resolver_cest`). Só os anexos parciais o exigem;
o CEST também desempata item que casa em mais de um anexo (ex.: mamadeiras em XI/XIII/XX, datas diferentes).

Cada posição de estoque vale só para as revogações do DIA SEGUINTE (CAT 28/20, art. 2º): a posição de 31/12/2025 serve
aos itens revogados em 01/01/2026 etc. `particionar` faz essa divisão; revogação sem posição vira pendência.

Dados: references/base-legal/cat68-2019-produtos-revogados.csv e cat68-2019-itens-vigentes.csv (gerados por
scripts/base/build_cat68_revogados.py).
"""
import csv
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'references', 'base-legal')


def _d(s) -> str:
    return re.sub(r'\D', '', str(s or ''))


def _csv(nome):
    with open(os.path.join(BASE, nome), encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f, delimiter=';'))


class Triagem:
    def __init__(self):
        rev, vig = _csv('cat68-2019-produtos-revogados.csv'), _csv('cat68-2019-itens-vigentes.csv')
        self.completos = {r['anexo'] for r in rev if r['tipo_revogacao'] == 'Anexo inteiro revogado'}
        self.tok_rev: List[dict] = []
        for r in rev:
            dt = datetime.strptime(r['data_revogacao'], '%d/%m/%Y').date()
            for t in r['ncm'].split():
                if _d(t):
                    self.tok_rev.append(dict(tok=_d(t), anexo=r['anexo'], item=r['item'], data=dt, cest=_d(r['cest']),
                                             completo=r['anexo'] in self.completos, ato=r['ato_revogador'],
                                             segmento=r['segmento'], descricao=r['descricao']))
        self.tok_vig = [dict(tok=_d(t), anexo=r['anexo'], item=r['item'], cest=_d(r['cest']))
                        for r in vig for t in r['ncm'].split() if _d(t)]

    def classificar(self, ncm: str, cest: str = '', descricao: str = '', cest_origem: str = '') -> dict:
        """Devolve {status, criterio, anexo, item, data_revogacao, ato, flags, alternativas}.
        status: 'triado' | 'ambiguo' (mais de um anexo e o CEST não desempata) | 'revisar_parcial_sem_cest' | 'fora'."""
        ncm, cest = _d(ncm), _d(cest)
        r = self._classificar(ncm, cest)
        if descricao and not r.get('cest_confirma') and (r['status'] in ('ambiguo', 'revisar_parcial_sem_cest') or
                                                         (r['status'] == 'triado' and self._n_candidatos(ncm) > 1)):
            r = self._por_descricao(ncm, cest, descricao, cest_origem, r)
        return r

    def _n_candidatos(self, ncm):
        """Grupos distintos que o NCM alcança: (anexo, data de saída) dos itens revogados e anexos dos itens que continuam na ST.
        Mais de um grupo e sem CEST que confirme = decide a descrição. Um só grupo (ex.: medicamentos, Anexo IX) não tem o que decidir."""
        return len({('rev', t['anexo'], t['data']) for t in self.tok_rev if ncm.startswith(t['tok'])} |
                   {('vig', t['anexo']) for t in self.tok_vig if ncm.startswith(t['tok'])})

    def _por_descricao(self, ncm, cest, descricao, cest_origem, r):
        """Item em mais de um anexo ou anexo parcial sem CEST: o melhor anexo/item é o da descrição legal que mais corresponde
        à descrição do produto (identidade_cat68). Sem nenhuma correspondência o item continua fora, com o motivo."""
        import identidade_cat68 as ID
        casam = [t for t in self.tok_rev if ncm.startswith(t['tok'])]
        base = casam
        prod = dict(descricao=descricao, ncm=ncm, cest=cest, cest_origem=cest_origem)
        pont = []
        for t in base:
            av = ID.avaliar(prod, t['anexo'], t['item'])
            if av['confirmada'] and av['pontos'] > 0:
                pont.append((av['pontos'], t, av))
        contradiz = False
        if not pont:                                    # só a descrição decide: o CEST da nota fica como observação
            for t in base:
                av = ID.avaliar(prod, t['anexo'], t['item'])
                if av['pontos_desc'] > 0:
                    pont.append((av['pontos_desc'], t, av))
            contradiz = bool(pont)
        # itens do mesmo NCM que CONTINUAM na ST competem pela descrição: se um deles descreve melhor o produto, ele segue na ST
        vig = []
        for t in self.tok_vig:
            if ncm.startswith(t['tok']):
                av = ID.avaliar(prod, t['anexo'], t['item'], vigente=True)
                if av['pontos_desc'] > 0:
                    vig.append((av['pontos_desc'], t, av))
        if vig:
            mv = max(p[0] for p in vig)
            if not pont or mv >= max(p[0] for p in pont):
                esc = max(vig, key=lambda p: p[0])
                return dict(status='vigente', criterio='', anexo=esc[1]['anexo'], item=esc[1]['item'], alternativas=[],
                            flags=[f"pela descrição, o produto é do item {esc[1]['anexo']}/{esc[1]['item']} ({esc[2]['descricao_legal'][:70]}), "
                                   'que continua na ST'])
        if not pont:
            if r['status'] != 'triado':
                r['flags'] = r['flags'] + ['a descrição do produto não corresponde à descrição legal de nenhum dos itens candidatos']
            return r                                    # sem correspondência de descrição: fica a triagem pelo NCM
        melhor = max(p[0] for p in pont)
        topo = [p for p in pont if p[0] == melhor]
        escolha = self._melhor([p[1] for p in topo])
        av = next(p[2] for p in topo if p[1] is escolha)
        empate = (' ; empate entre ' + ', '.join(sorted({f"{p[1]['anexo']}/{p[1]['item']}" for p in topo})) +
                  ' desfeito pelo NCM mais específico e pela data') if len(topo) > 1 else ''
        nota = (f"anexo {escolha['anexo']} item {escolha['item']} escolhido pela descrição do produto "
                f"({av['evidencias'][0]}; {len(pont)} item(ns) candidato(s){empate})" +
                ('; o CEST da nota não confere com o item escolhido: classificação da nota divergente' if contradiz else ''))
        return dict(status='triado', criterio='NCM' if escolha['completo'] else 'NCM+descrição', anexo=escolha['anexo'],
                    item=escolha['item'], data_revogacao=escolha['data'], ato=escolha['ato'], segmento=escolha['segmento'],
                    ncm_anexo=escolha['tok'], cest_confirma=False, flags=[nota], alternativas=[])

    def _classificar(self, ncm: str, cest: str) -> dict:
        casam = [t for t in self.tok_rev if ncm and ncm.startswith(t['tok'])]
        completos = [t for t in casam if t['completo']]
        parciais = [t for t in casam if not t['completo']]
        confirmados = [t for t in casam if cest and t['cest'] == cest]      # NCM + CEST valem em qualquer anexo
        flags: List[str] = []
        if confirmados:
            escolha = self._melhor(confirmados)
            criterio = 'NCM' if escolha['completo'] else 'NCM+CEST'
        elif completos:
            anexos = {t['anexo'] for t in completos}
            if len(anexos) > 1:
                alt = sorted({(t['anexo'], t['data']) for t in completos}, key=lambda x: (x[1], x[0]))
                return dict(status='ambiguo', criterio='NCM', alternativas=alt, flags=['NCM em mais de um anexo'] +
                            (['CEST do produto não casa com nenhum'] if cest else ['sem CEST para desempatar']))
            escolha = self._melhor(completos)
            criterio = 'NCM'
            if parciais:
                flags.append('NCM também consta em anexo de saída parcial (' + ', '.join(sorted({t['anexo'] for t in parciais})) +
                             '); sem CEST que confirme, foi usado o anexo completo: conferir o CEST do produto')
        elif parciais:
            alt = sorted({(t['anexo'], t['data']) for t in parciais}, key=lambda x: (x[1], x[0]))
            motivo = 'anexo parcial exige NCM+CEST; ' + ('CEST do produto não casa' if cest else 'produto sem CEST')
            return dict(status='revisar_parcial_sem_cest', criterio='NCM+CEST', alternativas=alt, flags=[motivo])
        else:
            return dict(status='fora', flags=[])
        cest_confirma = bool(cest and escolha['cest'] == cest)
        if criterio == 'NCM' and len(escolha['tok']) <= 4 and not cest_confirma:
            flags.append('NCM amplo (<= 4 dígitos) sem confirmação de CEST: pode pegar produto que nunca teve ST; '
                         'o crédito fica zero se a nota não trouxer base de ST')
        if cest and any(ncm.startswith(v['tok']) and v['cest'] == cest for v in self.tok_vig):
            flags.append('NCM+CEST também consta em item vigente da ST')
        return dict(status='triado', criterio=criterio, anexo=escolha['anexo'], item=escolha['item'], data_revogacao=escolha['data'],
                    ato=escolha['ato'], segmento=escolha['segmento'], ncm_anexo=escolha['tok'], cest_confirma=cest_confirma, flags=flags,
                    alternativas=[])

    @staticmethod
    def _melhor(cands: List[dict]) -> dict:
        return sorted(cands, key=lambda t: (-len(t['tok']), t['data'], t['anexo']))[0]


def particionar(itens_classificados: Iterable[dict], datas_posicoes: Iterable[date]) -> dict:
    """Divide os itens 'triado' pela data da posição: posição D serve à revogação de D+1.
    Devolve {'por_posicao': {D: [itens]}, 'sem_posicao': {data_revogacao: [itens]}}."""
    posicoes = set(datas_posicoes)
    por_pos: Dict[date, list] = {d: [] for d in sorted(posicoes)}
    sem: Dict[date, list] = {}
    for it in itens_classificados:
        if it['status'] != 'triado':
            continue
        pos = it['data_revogacao'] - timedelta(days=1)
        if pos in posicoes:
            por_pos[pos].append(it)
        else:
            sem.setdefault(it['data_revogacao'], []).append(it)
    return dict(por_posicao=por_pos, sem_posicao=dict(sorted(sem.items())))


# ---------------------------------------------------------------- CEST do estoque via notas (por EAN)
def indice_cest_por_ean(compras: Iterable[dict]) -> Dict[str, Counter]:
    """EAN (14 dígitos) -> Counter de CEST observados nas NF-e de compra."""
    idx: Dict[str, Counter] = {}
    for c in compras:
        ean, cest = _d(c.get('ean')), _d(c.get('cest'))
        if len(ean) in (8, 12, 13, 14) and len(cest) == 7:
            idx.setdefault(ean.zfill(14), Counter())[cest] += 1
    return idx


def resolver_cest(linhas_estoque: Iterable[dict], indice: Dict[str, Counter]) -> dict:
    """Preenche `cest` e `cest_origem` no estoque (o relatório da drogaria não traz CEST).
    cest_origem: 'estoque' | 'nfe_ean' (um único CEST nas notas) | 'nfe_ean_ambiguo' (vários; usado o mais frequente,
    produto em revisão) | 'nao_encontrado'. Devolve estatísticas de cobertura."""
    est = dict(total=0, estoque=0, nfe_ean=0, nfe_ean_ambiguo=0, nao_encontrado=0)
    for l in linhas_estoque:
        est['total'] += 1
        if _d(l.get('cest')):
            l['cest_origem'] = 'estoque'
        else:
            e = _d(l.get('ean'))
            cont = indice.get(e.zfill(14)) if len(e) in (8, 12, 13, 14) else None
            if not cont:
                l['cest'], l['cest_origem'] = '', 'nao_encontrado'
            else:
                l['cest'] = cont.most_common(1)[0][0]
                l['cest_origem'] = 'nfe_ean' if len(cont) == 1 else 'nfe_ean_ambiguo'
        est[l['cest_origem']] += 1
    return est
