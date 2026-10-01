"""Passo 4 do levantamento: localizar cada item do estoque nas NF-e de compra.

Cascata (da mais para a menos segura); o primeiro método que achar, vale:
  1. 'ean'            EAN do estoque == cEAN da nota (mesmo GTIN, normalizado para 14 dígitos: UPC/EAN-13/GTIN-14).
  2. 'ean_trib'       EAN do estoque == cEANTrib (a nota vende caixa; o estoque guarda a unidade). Traz fator do XML.
  3. 'ean_embalagem'  mesmo núcleo de 12 dígitos (GTIN-14 de caixa x EAN-13 da unidade). Precisa de fator.
  4. 'descricao'      comparação por atributos (scripts/casamento_descricao.py), níveis A/B/C, com desempate por preço.
  (nenhum)            'nao_localizado' — sem nota, sem crédito.

Sem inventar: produto localizado só por descrição nível C, ou ambíguo, fica marcado `revisar` e não entra no crédito
confirmado. Todo resultado traz o método, o nível e o porquê.
"""
import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional

import casamento_descricao as CD

VALIDOS = (8, 12, 13, 14)


def _d(s) -> str:
    return re.sub(r'\D', '', str(s or ''))


def gtin14(e) -> str:
    d = _d(e)
    return d.zfill(14) if len(d) in VALIDOS else ''


def nucleo12(e) -> str:
    g = gtin14(e)
    return g[1:13] if g else ''


class Localizador:
    """compras: linhas canônicas (scripts/compras.py). Constrói índices por EAN, EAN tributável, núcleo e descrição."""

    def __init__(self, compras: List[dict]):
        self.compras = compras
        self.por_ean: Dict[str, List[int]] = defaultdict(list)
        self.por_trib: Dict[str, List[int]] = defaultdict(list)
        self.por_nucleo: Dict[str, List[int]] = defaultdict(list)
        self.chave_produto: List[str] = []
        grupos_desc: Dict[str, List[str]] = defaultdict(list)
        ncms: Dict[str, List[str]] = defaultdict(list)
        precos: Dict[str, List[float]] = defaultdict(list)
        for i, c in enumerate(compras):
            g, gt = gtin14(c.get('ean')), gtin14(c.get('ean_trib'))
            if g:
                self.por_ean[g].append(i)
                self.por_nucleo[g[1:13]].append(i)
            if gt:
                self.por_trib[gt].append(i)
                self.por_nucleo[gt[1:13]].append(i)
            k = g or f"SEMEAN|{c.get('cnpj_emitente')}|{c.get('cod_produto')}"
            self.chave_produto.append(k)
            grupos_desc[k].append(c.get('descricao', ''))
            ncms[k].append(_d(c.get('ncm')))
            if (c.get('qtd') or 0) > 0 and (c.get('vl_merc') or 0) > 0:
                precos[k].append(c['vl_merc'] / c['qtd'])
        self.linhas_do_produto: Dict[str, List[int]] = defaultdict(list)
        for i, k in enumerate(self.chave_produto):
            self.linhas_do_produto[k].append(i)
        self.indice = CD.Indice()
        for k, ds in grupos_desc.items():
            self.indice.adicionar(k, [x for x, _ in Counter(ds).most_common(4)], Counter(ncms[k]).most_common(1)[0][0])
        self.preco = {k: sorted(v)[len(v) // 2] for k, v in precos.items()}

    def _fator_xml(self, linhas: List[int]) -> Optional[float]:
        """qTrib/qCom quando o XML declara quantidade tributável diferente (EAN tributável = unidade do estoque)."""
        fs = {round(self.compras[i]['qtd_trib'] / self.compras[i]['qtd'], 6) for i in linhas
              if (self.compras[i].get('qtd') or 0) > 0 and (self.compras[i].get('qtd_trib') or 0) > 0}
        return fs.pop() if len(fs) == 1 else None

    def localizar(self, item: dict) -> dict:
        """item: linha do estoque (ean, descricao, ncm, valor). Devolve dict com metodo, nivel, linhas, observacoes."""
        g = gtin14(item.get('ean'))
        if g and g in self.por_ean:
            return self._ok('ean', 'A', self.por_ean[g])
        if g and g in self.por_trib:
            linhas = self.por_trib[g]
            r = self._ok('ean_trib', 'A', linhas)
            r['fator_xml'] = self._fator_xml(linhas)
            r['observacoes'].append('EAN do estoque é o da unidade tributável da nota; conferir fator de conversão')
            return r
        if g and g[1:13] in self.por_nucleo:
            r = self._ok('ean_embalagem', 'B', self.por_nucleo[g[1:13]])
            r['observacoes'].append('mesmo núcleo de GTIN (caixa x unidade): definir fator de conversão')
            return r
        return self.por_descricao(item)

    def por_descricao(self, item: dict, excluir=()) -> dict:
        """Só o método 4 (descrição), podendo excluir produtos já usados: serve para completar a quantidade do estoque
        com outras notas equivalentes (ex.: a mesma mercadoria com outro EAN)."""
        res = self.indice.buscar(item.get('descricao', ''), item.get('ncm', ''), excluir=excluir)
        dec = CD.decidir(res)
        if dec['nivel'] is None:
            return dict(metodo='nao_localizado', nivel=None, linhas=[], chave_produto=None, observacoes=[], alternativas=[])
        chave, nivel, obs = dec['chave'], dec['nivel'], list(dec['motivos'])
        if dec['ambiguo']:
            venc = CD.desempatar_por_preco(dec['candidatos'], float(item.get('valor') or 0), self.preco)
            if venc:
                chave, nivel = venc, 'C'
                obs.append('desempate por preço de compra próximo ao custo do estoque')
            else:
                nivel = 'C'
                obs.append('ambíguo: mais de um produto com a mesma descrição (laboratório/EAN diferentes)')
        if dec['generico_sem_lab']:
            obs.append('genérico sem laboratório no estoque')
        obs += [f'atenção: {s}' for s in dec.get('suaves', [])]
        return dict(metodo='descricao', nivel=nivel, chave_produto=chave, linhas=self.linhas_do_produto[chave],
                    observacoes=obs, alternativas=dec['candidatos'], desc_nota=dec.get('desc_nota'),
                    ambiguo=dec['ambiguo'])

    @staticmethod
    def _ok(metodo, nivel, linhas):
        return dict(metodo=metodo, nivel=nivel, linhas=list(linhas), chave_produto=None, observacoes=[], alternativas=[])


def confirmado(loc: dict) -> bool:
    """Localização que pode entrar no crédito confirmado: EAN (qualquer) ou descrição A/B sem ambiguidade."""
    if loc['metodo'] in ('ean', 'ean_trib'):
        return True
    if loc['metodo'] == 'ean_embalagem':
        return True                       # confirmada, mas depende do fator
    return loc['metodo'] == 'descricao' and loc['nivel'] in ('A', 'B') and not loc.get('ambiguo')
