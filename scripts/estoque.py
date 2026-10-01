"""Descoberta, leitura e validação das posições de estoque (arquivos tipo "estoque 31.12.2025.xls").

Layout de referência (relatório "Posição de Estoque (Inventário)" do sistema da drogaria; cabeçalho na 4ª linha, colunas
de mesclagem vazias entre elas):
    Código de Barras | Produto ID | Descrição do Produto | Grupo pai | Grupo filho | Qtde. | Preço Custo Médio |
    Total Preço Custo Médio | Preço Venda | Total Preço Venda | Unidade | CST | NCM | CST PIS | CST COFINS | Totalizador
    + linha de totais no rodapé. NÃO há coluna de CEST (resolvido pelas NF-e de compra: ver triagem.py).

CAMPOS OBRIGATÓRIOS para os cruzamentos: EAN, DESCRICAO, NCM e VALOR (custo unitário médio), além de quantidade e
código do produto. Linha com qualquer obrigatório ausente/inválido NÃO é descartada em silêncio: vai para `rejeitadas`
com o motivo e aparece no relatório. Coluna obrigatória ausente no arquivo é erro bloqueante.

A data da posição vem do NOME do arquivo (dd.mm.aaaa).
"""
import csv
import os
import re
import unicodedata
from datetime import date
from typing import Dict, List, Optional, Tuple

EXT = ('.xlsx', '.xlsm', '.xls', '.csv')
_DATA_NOME = re.compile(r'(?<!\d)(\d{2})[.\-_/ ](\d{2})[.\-_/ ](\d{4})(?!\d)')

# Campos que o usuário exige na planilha (nomes canônicos). 'valor' = custo unitário médio.
OBRIGATORIOS = ('ean', 'descricao', 'ncm', 'valor')
ESSENCIAIS = ('qtd', 'cod_produto')       # sem eles a linha não serve para o cálculo
ROTULO = {'ean': 'EAN (Código de Barras)', 'descricao': 'Descrição', 'ncm': 'NCM', 'valor': 'Valor (Preço Custo Médio)',
          'qtd': 'Quantidade', 'cod_produto': 'Código do produto (Produto ID)'}

APELIDOS: Dict[str, List[str]] = {
    'ean': ['codigo de barras', 'cod barras', 'codigo barras', 'ean', 'gtin', 'cean'],
    'cod_produto': ['produto id', 'id produto', 'codigo', 'cod', 'cod produto', 'codigo produto', 'codigo do produto',
                    'cod item', 'sku', 'item', 'referencia', 'cod interno'],
    'descricao': ['descricao do produto', 'descricao', 'descricao produto', 'nome', 'nome produto', 'produto', 'descr',
                  'descricao item'],
    'ncm': ['ncm', 'ncm sh', 'classificacao fiscal', 'cod ncm'],
    'cest': ['cest', 'cod cest'],
    'qtd': ['qtde', 'quantidade', 'qtd', 'saldo', 'estoque', 'qtd estoque', 'quantidade em estoque', 'saldo estoque',
            'qtde estoque', 'saldo atual', 'quantidade estoque'],
    'unidade': ['unidade', 'un', 'und', 'unid', 'um', 'u m', 'unidade medida'],
    'valor': ['preco custo medio', 'custo medio', 'custo unitario', 'custo', 'preco custo', 'valor unitario',
              'vl unitario', 'valor'],
    'valor_total': ['total preco custo medio', 'valor total', 'custo total', 'total custo', 'vl total', 'valor estoque'],
    'preco_venda': ['preco venda', 'preco de venda', 'venda'],
    'total_venda': ['total preco venda', 'total venda', 'valor venda total'],
    'grupo_pai': ['grupo pai', 'grupo', 'categoria'],
    'grupo_filho': ['grupo filho', 'subgrupo'],
    'cst_icms': ['cst', 'cst icms'],
    'cst_pis': ['cst pis'],
    'cst_cofins': ['cst cofins'],
    'totalizador': ['totalizador', 'totalizador parcial'],
}


# ---------------------------------------------------------------- utilidades
def data_do_nome(nome: str) -> Optional[date]:
    m = _DATA_NOME.search(nome)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _norm(s) -> str:
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', s)).strip()


def descobrir(raizes: List[str]) -> List[Tuple[str, Optional[date]]]:
    """Arquivos de estoque (nome contém 'estoque') em qualquer subpasta. Devolve (caminho, data do nome)."""
    achados = []
    for raiz in raizes:
        for dp, _, fs in os.walk(raiz):
            for f in fs:
                if f.lower().endswith(EXT) and 'estoque' in _norm(f) and not f.startswith('~$'):
                    achados.append((os.path.join(dp, f), data_do_nome(f)))
    return sorted(achados, key=lambda t: (t[1] or date.min, t[0]))


def num_br(v) -> Optional[float]:
    """'1.234,56' | '1234.56' | 12 | None -> float."""
    if v is None or v == '' or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if v != v else float(v)  # NaN -> None
    s = str(v).strip().replace('\xa0', '').replace(' ', '')
    if not s:
        return None
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.') if s.rfind(',') > s.rfind('.') else s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def digitos(v) -> str:
    """Só dígitos, tratando números do Excel (int/float) sem acrescentar '.0' nem perder dígitos."""
    if v is None:
        return ''
    if isinstance(v, bool):
        return ''
    if isinstance(v, float):
        if v != v:
            return ''
        if v.is_integer():
            v = int(v)
    return re.sub(r'\D', '', str(v))


def normalizar_ncm(v) -> Tuple[str, Optional[str]]:
    """(ncm_8_digitos, aviso). O Excel guarda NCM como número e perde o zero à esquerda (ex.: 04090000 -> 4090000)."""
    d = digitos(v)
    if len(d) == 7:
        return d.zfill(8), 'NCM com 7 dígitos: zero à esquerda restaurado'
    if len(d) == 8:
        return d, None
    return d, f'NCM inválido ({d or "vazio"}): esperado 8 dígitos'


def gtin_valido(ean: str) -> bool:
    """Dígito verificador GTIN-8/12/13/14 (módulo 10)."""
    if not ean.isdigit() or len(ean) not in (8, 12, 13, 14):
        return False
    corpo, dv = ean[:-1], int(ean[-1])
    soma = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(corpo)))
    return (10 - soma % 10) % 10 == dv


def aliquota_totalizador(t: str) -> Optional[float]:
    """'TC (18.00)' -> 18.0 (alíquota do totalizador fiscal do PDV; informativo, não é a alíquota legal)."""
    m = re.search(r'\((\d+(?:[.,]\d+)?)\)', t or '')
    return float(m.group(1).replace(',', '.')) if m else None


# ---------------------------------------------------------------- leitura
def _mapear_cabecalho(linha) -> Dict[str, int]:
    usados, mapa = set(), {}
    normas = [_norm(c) for c in linha]
    for campo, aps in APELIDOS.items():  # 1ª passada: igualdade exata, na ordem de prioridade dos apelidos
        for ap in aps:
            if campo in mapa:
                break
            for j, n in enumerate(normas):
                if n == ap and j not in usados:
                    mapa[campo] = j
                    usados.add(j)
                    break
    for campo in ('qtd', 'descricao', 'cod_produto'):  # 2ª passada: "contém" só para os essenciais
        if campo in mapa:
            continue
        for ap in APELIDOS[campo]:
            if len(ap) < 5:
                continue
            for j, n in enumerate(normas):
                if j not in usados and ap in n and 'barra' not in n and 'ean' not in n and 'total' not in n:
                    mapa[campo] = j
                    usados.add(j)
                    break
            if campo in mapa:
                break
    return mapa


def _linhas(caminho: str):
    ext = os.path.splitext(caminho)[1].lower()
    if ext == '.csv':
        for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
            try:
                with open(caminho, encoding=enc, newline='') as f:
                    amostra = f.read(4096)
                    f.seek(0)
                    try:
                        dialeto = csv.Sniffer().sniff(amostra, delimiters=';,\t|')
                    except csv.Error:
                        dialeto = csv.excel_tab if '\t' in amostra else csv.excel
                        dialeto.delimiter = ';' if amostra.count(';') >= amostra.count(',') else ','
                    return list(csv.reader(f, dialeto))
            except UnicodeDecodeError:
                continue
        raise ValueError('encoding do CSV não reconhecido')
    if ext in ('.xlsx', '.xlsm'):
        from openpyxl import load_workbook
        wb = load_workbook(caminho, read_only=True, data_only=True)
        try:
            ws = wb[wb.sheetnames[0]] if len(wb.sheetnames) == 1 else max(wb.worksheets, key=lambda w: w.max_row or 0)
            return [list(r) for r in ws.iter_rows(values_only=True)]
        finally:
            wb.close()  # libera o arquivo (Windows mantém lock em modo read_only)
    import pandas as pd  # .xls (requer xlrd)
    df = pd.read_excel(caminho, header=None, dtype=object)
    return df.astype(object).where(df.notna(), None).values.tolist()


def _vazio(v) -> bool:
    return v is None or (isinstance(v, float) and v != v) or str(v).strip() == ''


def ler(caminho: str, data_posicao: Optional[date]) -> dict:
    """Lê e valida uma posição de estoque.

    Devolve dict com: linhas (válidas, campos canônicos), rejeitadas (com motivo), colunas (mapeamento detectado),
    nao_reconhecidas, avisos, bloqueantes (colunas obrigatórias ausentes/cabeçalho), total_rodape, arquivo, data_posicao.
    """
    base = dict(linhas=[], rejeitadas=[], colunas={}, nao_reconhecidas=[], avisos=[], bloqueantes=[],
                total_rodape=None, arquivo=os.path.basename(caminho), data_posicao=data_posicao)
    try:
        linhas = _linhas(caminho)
    except Exception as ex:
        base['bloqueantes'].append(f'Falha ao abrir: {type(ex).__name__}: {ex}')
        return base
    cab_idx, mapa = None, {}
    for idx, lin in enumerate(linhas[:40]):
        m = _mapear_cabecalho(lin)
        if 'qtd' in m and ('cod_produto' in m or 'descricao' in m) and len(m) >= 3:
            cab_idx, mapa = idx, m
            break
    if cab_idx is None:
        base['bloqueantes'].append('Cabeçalho não reconhecido (precisa de quantidade + código/descrição). '
                                   'Conferir o layout do arquivo.')
        return base
    cab = linhas[cab_idx]
    base['colunas'] = {k: str(cab[v]) for k, v in mapa.items()}
    base['nao_reconhecidas'] = [str(c) for j, c in enumerate(cab) if j not in mapa.values() and not _vazio(c)]

    # 'valor' pode ser derivado de valor_total/qtd quando só o total existir
    falta = [c for c in OBRIGATORIOS + ESSENCIAIS
             if c not in mapa and not (c == 'valor' and 'valor_total' in mapa)]
    for c in falta:
        base['bloqueantes'].append(f'Coluna obrigatória ausente: {ROTULO[c]}.')
    if data_posicao is None:
        base['avisos'].append('Data da posição não encontrada no nome do arquivo (esperado "estoque dd.mm.aaaa").')
    if 'cest' not in mapa:
        base['avisos'].append('Arquivo sem CEST (esperado neste layout): o CEST será resolvido pelo EAN nas NF-e de '
                              'compra; produto sem correspondência vai para revisão.')
    if falta:
        return base

    g = lambda lin, k: (lin[mapa[k]] if k in mapa and mapa[k] < len(lin) else None)
    ncm_corrigidos = 0
    vistos: Dict[str, int] = {}
    for n, lin in enumerate(linhas[cab_idx + 1:], start=cab_idx + 2):
        if not lin or all(_vazio(c) for c in lin):
            continue
        ean_raw, desc, cod = g(lin, 'ean'), str(g(lin, 'descricao') or '').strip(), str(digitos(g(lin, 'cod_produto')) or
                                                                                          g(lin, 'cod_produto') or '').strip()
        # rodapé de totais: sem identificação do produto, com valor total preenchido
        if _vazio(ean_raw) and not desc and not cod:
            vt = num_br(g(lin, 'valor_total'))
            if vt is not None:
                base['total_rodape'] = vt
            continue
        if _norm(cod).startswith('total') or _norm(desc).startswith('total'):
            continue
        qtd, valor, vtot = num_br(g(lin, 'qtd')), num_br(g(lin, 'valor')), num_br(g(lin, 'valor_total'))
        if valor is None and vtot is not None and qtd:
            valor = vtot / qtd
        ean = digitos(ean_raw)
        ncm, av_ncm = normalizar_ncm(g(lin, 'ncm'))
        motivos = []
        if _vazio(ean_raw):
            motivos.append('EAN ausente')
        elif not ean:
            motivos.append(f'EAN sem dígitos ({str(ean_raw).strip()})')
        elif len(ean) not in (8, 12, 13, 14):
            motivos.append(f'EAN com tamanho inválido ({len(ean)} dígitos)')
        if not desc:
            motivos.append('Descrição ausente')
        if len(ncm) != 8:
            motivos.append(av_ncm or 'NCM ausente')
        if valor is None:
            motivos.append('Valor ausente')
        elif valor <= 0:
            motivos.append('Valor zero/negativo')
        if qtd is None:
            motivos.append('Quantidade ausente/ilegível')
        elif qtd <= 0:
            motivos.append('Quantidade zero/negativa')
        if not cod:
            motivos.append('Código do produto ausente')
        if motivos:
            base['rejeitadas'].append(dict(linha=n, arquivo=base['arquivo'], ean=str(ean_raw or ''), descricao=desc,
                                           motivo='; '.join(motivos)))
            continue
        if av_ncm:
            ncm_corrigidos += 1
        vistos[ean] = vistos.get(ean, 0) + 1
        tot = g(lin, 'totalizador')
        base['linhas'].append(dict(
            data_posicao=data_posicao, arquivo=base['arquivo'], cod_produto=cod, ean=ean, descricao=desc, ncm=ncm,
            cest=digitos(g(lin, 'cest')), qtd=qtd, unidade=str(g(lin, 'unidade') or '').strip(), valor=round(valor, 6),
            valor_total=round(vtot if vtot is not None else valor * qtd, 2),
            grupo_pai=str(g(lin, 'grupo_pai') or '').strip(), cst_icms=str(g(lin, 'cst_icms') or '').strip(),
            totalizador=str(tot or '').strip(), aliq_totalizador=aliquota_totalizador(str(tot or '')),
            ean_dv_ok=gtin_valido(ean)))
    if ncm_corrigidos:
        base['avisos'].append(f'{ncm_corrigidos} NCM com 7 dígitos tiveram o zero à esquerda restaurado '
                              '(Excel grava NCM como número).')
    dup = [e for e, c in vistos.items() if c > 1]
    if dup:
        base['avisos'].append(f'{len(dup)} EAN repetidos no mesmo arquivo (a quantidade será somada no cruzamento).')
    dv = sum(1 for l in base['linhas'] if not l['ean_dv_ok'])
    if dv:
        base['avisos'].append(f'{dv} EAN com dígito verificador GTIN inválido (código interno/etiqueta própria?): '
                              'cruzamento por EAN pode não achar a nota; usar descrição/NCM como apoio.')
    if base['total_rodape'] is not None and base['linhas']:
        soma = round(sum(l['valor_total'] for l in base['linhas']) + 0.0, 2)
        rej = base['rejeitadas']
        if abs(soma - base['total_rodape']) > 0.05 and not rej:
            base['avisos'].append(f'Soma do valor total das linhas ({soma:,.2f}) difere do total do rodapé '
                                  f"({base['total_rodape']:,.2f}).")
    if base['rejeitadas']:
        base['avisos'].append(f"{len(base['rejeitadas'])} linha(s) rejeitada(s) por campo obrigatório ausente/inválido "
                              '(ver aba "Estoque rejeitadas").')
    return base


def assinatura(linhas: List[dict]) -> frozenset:
    """Impressão digital do conteúdo (EAN, qtd, valor) para detectar posições idênticas entre datas diferentes."""
    return frozenset((l['ean'], l['qtd'], l['valor']) for l in linhas)
