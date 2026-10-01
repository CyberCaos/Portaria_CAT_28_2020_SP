"""Relatório final em PDF do levantamento de crédito de ICMS sobre estoque (CAT 28/2020).

    python scripts/gerar_relatorio.py <pasta_do_cliente>            ->  <cliente>/relatorio_levantamento.pdf

Lê `resultado_levantamento.xlsx` (gerado por levantamento.py) e `cliente.json`; o PDF e a planilha nunca divergem.
Seções: 1) resumo executivo (indicadores, gráficos, avisos); 2) como o crédito foi apurado (funil e passos);
3) memória de cálculo (fórmula, regras, exemplo real passo a passo); 4) crédito por competência e pendências;
5) detalhamento item a item: item do estoque -> chave de acesso e item rastreado da NF-e -> crédito da linha e do item;
6) apêndice: itens sem crédito, premissas e glossário.
Usa só reportlab (gráficos desenhados à mão). Fonte Calibri/Consolas quando existirem (Windows); senão Helvetica/Courier.
"""
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String, Wedge
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

# ----------------------------------------------------------------------------------------------- estilo
AZUL, AZUL2, TEAL, AMBAR, VERM, VERDE = (colors.HexColor(c) for c in ('#1F3864', '#2F5597', '#0E9F8E', '#F59E0B', '#DC2626', '#16A34A'))
CINZA, CINZA_CL, FUNDO, BORDA = (colors.HexColor(c) for c in ('#64748B', '#94A3B8', '#F3F5F8', '#D9DFE8'))
TEXTO = colors.HexColor('#1E293B')
PAGINA = landscape(A4)
LARG = PAGINA[0]
ML, MR = 1.0 * cm, 1.0 * cm
UTIL = LARG - ML - MR


def _fontes():
    """Calibri/Consolas do Windows quando existirem; senão as fontes Vera que acompanham o reportlab (têm acentos e o sinal de menos)."""
    f = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
    try:
        for nome, arq in (('Txt', 'calibri.ttf'), ('Txt-B', 'calibrib.ttf'), ('Txt-I', 'calibrii.ttf'), ('Txt-BI', 'calibriz.ttf'), ('Mono', 'consola.ttf')):
            pdfmetrics.registerFont(TTFont(nome, os.path.join(f, arq)))
        pdfmetrics.registerFontFamily('Txt', normal='Txt', bold='Txt-B', italic='Txt-I', boldItalic='Txt-BI')
        return 'Txt', 'Txt-B', 'Mono'
    except Exception:
        pass
    try:
        import reportlab
        v = os.path.join(os.path.dirname(reportlab.__file__), 'fonts')
        for nome, arq in (('Txt', 'Vera.ttf'), ('Txt-B', 'VeraBd.ttf'), ('Txt-I', 'VeraIt.ttf'), ('Txt-BI', 'VeraBI.ttf')):
            pdfmetrics.registerFont(TTFont(nome, os.path.join(v, arq)))
        pdfmetrics.registerFontFamily('Txt', normal='Txt', bold='Txt-B', italic='Txt-I', boldItalic='Txt-BI')
        print('Aviso: fontes Calibri/Consolas não encontradas; usando Vera (reportlab).', file=sys.stderr)
        return 'Txt', 'Txt-B', 'Courier'
    except Exception:
        print('Aviso: nenhuma fonte TrueType disponível; usando Helvetica (alguns símbolos podem faltar).', file=sys.stderr)
        return 'Helvetica', 'Helvetica-Bold', 'Courier'


FT, FB, FM = _fontes()


def st(nome, **k):
    base = dict(fontName=FT, fontSize=9, leading=12, textColor=TEXTO)
    base.update(k)
    return ParagraphStyle(nome, **base)


S = dict(
    h1=st('h1', fontName=FB, fontSize=17, leading=21, textColor=AZUL, spaceAfter=4),
    h2=st('h2', fontName=FB, fontSize=12, leading=15, textColor=AZUL2, spaceBefore=8, spaceAfter=3),
    p=st('p'), pp=st('pp', fontSize=8, leading=10.5), peq=st('peq', fontSize=7, leading=8.6, textColor=CINZA),
    ci=st('ci', fontSize=6.6, leading=8, textColor=CINZA),
    kpi_t=st('kpi_t', fontSize=8, leading=10, textColor=CINZA), kpi_v=st('kpi_v', fontName=FB, fontSize=19, leading=23, textColor=AZUL),
    kpi_s=st('kpi_s', fontSize=7.6, leading=9.4, textColor=CINZA),
    cel=st('cel', fontSize=7.2, leading=8.6), cel_b=st('cel_b', fontName=FB, fontSize=7.4, leading=8.8),
    cel_d=st('cel_d', fontSize=7.2, leading=8.6, alignment=TA_RIGHT), cel_c=st('cel_c', fontSize=7.2, leading=8.6, alignment=TA_CENTER),
    mono=st('mono', fontName=FM, fontSize=6.0, leading=7.6),
    th_s=st('th_s', fontName=FB, fontSize=6.6, leading=8, textColor=colors.white), th_sd=st('th_sd', fontName=FB, fontSize=6.6, leading=8, textColor=colors.white, alignment=TA_RIGHT), th=st('th', fontName=FB, fontSize=7.4, leading=9, textColor=colors.white),
    th_d=st('th_d', fontName=FB, fontSize=7.4, leading=9, textColor=colors.white, alignment=TA_RIGHT),
    form=st('form', fontName=FB, fontSize=15, leading=20, textColor=AZUL, alignment=TA_CENTER),
)


def brl(v, casas=2):
    if v is None or (isinstance(v, float) and v != v):
        return '—'
    v = round(v, casas) + 0.0
    s = f'{abs(v):,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return ('−' if v < 0 else '') + 'R$ ' + s


def num(v, casas=0):
    s = f'{v:,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return s


def data_br(v):
    t = str(v)[:10]
    return f'{t[8:10]}/{t[5:7]}/{t[:4]}' if len(t) == 10 and t[4] == '-' else t


def esc(t):
    return str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ----------------------------------------------------------------------------------------------- dados
def _lerxl(xl, aba, num_cols=()):
    d = pd.read_excel(xl, sheet_name=aba, dtype=str).fillna('')
    for c in num_cols:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c].str.replace(',', '.'), errors='coerce')
    return d


def _data(s):
    try:
        return datetime.strptime(str(s)[:10], '%d/%m/%Y').date()
    except ValueError:
        return None


def carregar(pasta):
    import json
    xl = os.path.join(pasta, 'resultado_levantamento.xlsx')
    tr = os.path.join(pasta, 'relatorio_parser', 'trilha_levantamento.xlsx')
    with open(os.path.join(pasta, 'cliente.json'), encoding='utf-8') as f:
        cli = json.load(f)
    D = dict(cli=cli)
    D['a2'] = _lerxl(xl, 'Anexo II (notas selecionadas)', ('qtde em estoque', 'alíquota interna (inclui FCP)', 'qtde do item (unidade comercial)',
                                                           'fator de conversão para unid. de estoque', 'qtde utilizada do item para informar o estoque',
                                                           'vl Mercd', 'BC ST', 'crédito', 'Vl mercadoria bruto (vProd)', 'Desconto (vDesc)',
                                                           'Crédito com VlMerc = vProd (alternativa)', 'pRedBc'))
    D['rp'] = _lerxl(xl, 'Resumo por produto', ('Qtd estoque', 'Total vl Mercd (item 14)', 'Total BC ST (item 15)', 'Total crédito (item 16)',
                                                'Unit. crédito (item 19)', 'Qtd sem nota (descoberto)'))
    D['al'] = _lerxl(tr, 'Alocação de notas', ('Fator', 'Qtd usada do estoque'))
    D['tri'] = _lerxl(tr, 'Triagem estoque', ('Qtd em estoque', 'Valor total', 'Valor unitário (custo médio)'))
    D['loc'] = _lerxl(tr, 'Localização', ('Qtd em estoque', 'Cobertura', 'Valor do estoque coberto'))
    D['pend'] = _lerxl(xl, 'Pendências', ('Valor em estoque',))
    D['prem'] = _lerxl(tr, 'Premissas')
    D['fora'] = _lerxl(tr, 'Fora do crédito', ('Crédito potencial da linha', 'Crédito potencial do item', 'Qtd do estoque (hipótese)'))
    D['comp'] = _lerxl(xl, 'Resumo por competência', ('Crédito a lançar',))
    est = os.path.join(pasta, 'relatorio_parser', 'estoque.csv')
    e = pd.read_csv(est, sep=';', dtype=str, encoding='utf-8-sig').fillna('')
    D['estoque_posicoes'] = e['arquivo'].nunique() if len(e) else 0
    D['estoque_itens'] = len(e)                                      # linhas de todas as posições recebidas
    D['estoque_valor'] = pd.to_numeric(e['valor_total'], errors='coerce').sum()
    D['n_xml'] = cli.get('resumo_parser', {}).get('notas_unicas')
    return D


def preparar(D):
    """Junta Anexo II + Alocação por (EAN, chave, item) e calcula totais por item (piso zero, como a planilha) e por data."""
    a2, al = D['a2'].copy(), D['al'].copy()
    a2['k'] = a2['EAN'].astype(str) + '|' + a2['chave NFe'].astype(str) + '|' + a2['no. Item'].astype(str)
    al['k'] = al['EAN (estoque)'].astype(str) + '|' + al['Chave NF-e'].astype(str) + '|' + al['Item'].astype(str)
    al = al.drop_duplicates('k')[['k', 'Emissão', 'Descrição na nota', 'Origem da localização', 'Origem do fator', 'Confiança do fator', 'CST/CSOSN']]
    L = a2.merge(al, on='k', how='left')
    tri = D['tri'].drop_duplicates('EAN').set_index('EAN')
    itens, interp = {}, []
    rp_mot = {}
    sit_rp = {}
    for _, r in D['rp'].iterrows():
        rp_mot[(str(r['EAN']), str(r['Data de revogação']))] = str(r.get('Observações do cálculo') or '')
        sit_rp[(str(r['EAN']), str(r['Data de revogação']))] = str(r['Situação do crédito'])
    fora = ('Pendente', 'Sem crédito: a mercadoria não corresponde')
    L = L[[not sit_rp.get((str(a), str(b)), 'Crédito').startswith(fora) for a, b in zip(L['EAN'], L['Data de revogação'])]].copy()
    for (ean, cod, _rev), g in L.groupby(['EAN', 'cod Mercd', 'Data de revogação'], sort=False):
        total = max(0.0, g['crédito'].fillna(0).sum())          # piso zero por mercadoria, igual à planilha
        mot = rp_mot.get((str(ean), str(_rev))) or ''
        if mot and total > 0:
            interp.append(dict(ean=ean, desc=g['Descrição (estoque)'].iloc[0], valor=round(total, 2), motivos=mot))
        t = tri.loc[ean] if ean in tri.index else None
        if isinstance(t, pd.DataFrame):
            t = t.iloc[0]
        itens[(ean, cod, _rev)] = dict(ean=ean, desc=g['Descrição (estoque)'].iloc[0], ncm=g['cod NCM'].iloc[0], qtd=g['qtde em estoque'].iloc[0],
                          rev=_data(g['Data de revogação'].iloc[0]), linhas=g, total=round(total, 2), anexo=(t['Anexo CAT 68'] if t is not None else ''),
                          segmento=(t['Segmento'] if t is not None else ''))
    D['itens'] = itens
    D['interp'] = sorted(interp, key=lambda x: -x['valor'])
    D['L'] = L

    rp = D['rp']
    D['tot'] = dict(total=sum(i['total'] for i in itens.values()), itens=sum(1 for i in itens.values() if i['total'] > 0),
                    notas=L.drop_duplicates(['chave NFe', 'no. Item']).shape[0],
                    com_obs=sum(x['valor'] for x in D['interp']), n_com_obs=len(D['interp']),
                    soma_linhas=round(L['crédito'].fillna(0).sum(), 2))
    por_data = defaultdict(lambda: dict(total=0.0, n=0))
    for i in itens.values():
        if i['total'] > 0:
            d = por_data[i['rev']]
            d['total'] += i['total']; d['n'] += 1
    D['por_data'] = dict(sorted(por_data.items()))
    sit = rp['Situação do crédito']
    D['situacao'] = [
        ('Crédito', int((sit == 'Crédito').sum()), VERDE),
        ('Crédito com observações', int((sit == 'Crédito com observações').sum()), colors.HexColor('#8B5CF6')),
        ('Pendência fiscal (sem valor)', int(sit.str.startswith('Pendente').sum()), VERM),
        ('Sem crédito: BC ST ≤ valor da mercadoria', int((sit == 'Sem crédito: BC ST não supera o valor da mercadoria').sum()), AZUL2),
        ('Sem crédito: sem base de ST na nota', int((sit == 'Sem crédito: sem base de ST').sum()), CINZA_CL),
        ('Sem prova documental', int((sit == 'Sem crédito: sem prova documental').sum()), colors.HexColor('#CBD5E1')),
        ('Sem nota anterior à vigência', int((sit == 'Sem crédito: sem nota anterior à vigência').sum()), AMBAR),
    ]
    return D


# ----------------------------------------------------------------------------------------------- componentes
def kpi(titulo, valor, sub, cor, largura):
    t = Table([[Paragraph(titulo.upper(), S['kpi_t'])], [Paragraph(valor, S['kpi_v'])], [Paragraph(sub, S['kpi_s'])]], colWidths=[largura])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.white), ('LINEBEFORE', (0, 0), (0, -1), 4, cor),
                           ('BOX', (0, 0), (-1, -1), 0.6, BORDA), ('LEFTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 2),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 2), ('TOPPADDING', (0, 0), (-1, 0), 8), ('BOTTOMPADDING', (0, -1), (-1, -1), 8)]))
    return t


def caixa(conteudo, fundo=FUNDO, borda=BORDA, cor_borda_esq=None, largura=UTIL, pad=8):
    t = Table([[conteudo]], colWidths=[largura])
    est = [('BACKGROUND', (0, 0), (-1, -1), fundo), ('BOX', (0, 0), (-1, -1), 0.6, borda), ('LEFTPADDING', (0, 0), (-1, -1), pad + 2),
           ('RIGHTPADDING', (0, 0), (-1, -1), pad), ('TOPPADDING', (0, 0), (-1, -1), pad), ('BOTTOMPADDING', (0, 0), (-1, -1), pad)]
    if cor_borda_esq:
        est.append(('LINEBEFORE', (0, 0), (0, -1), 4, cor_borda_esq))
    t.setStyle(TableStyle(est))
    return t


def grafico_barras(por_data, w, h):
    d = Drawing(w, h)
    d.add(String(0, h - 10, 'Crédito por data de revogação', fontName=FB, fontSize=9, fillColor=AZUL))
    itens = list(por_data.items())
    if not itens:
        return d
    mx = max(v['total'] for _, v in itens) or 1
    base_y, topo = 34, h - 40
    alt = topo - base_y
    n = len(itens)
    larg_b = min(70, (w - 40) / n * 0.55)
    passo = (w - 40) / n
    d.add(Line(20, base_y, w - 10, base_y, strokeColor=BORDA, strokeWidth=0.8))
    for k, (dt, v) in enumerate(itens):
        x = 30 + k * passo + (passo - larg_b) / 2
        hc = alt * v['total'] / mx
        d.add(Rect(x, base_y, larg_b, hc, fillColor=TEAL, strokeColor=None))
        d.add(String(x + larg_b / 2, base_y + hc + 5, brl(v['total'], 0), fontName=FB, fontSize=9, fillColor=AZUL, textAnchor='middle'))
        d.add(String(x + larg_b / 2, base_y - 12, dt.strftime('%d/%m/%Y') if dt else '—', fontName=FB, fontSize=8, fillColor=TEXTO, textAnchor='middle'))
        d.add(String(x + larg_b / 2, base_y - 23, f"{v['n']} itens", fontName=FT, fontSize=7.4, fillColor=CINZA, textAnchor='middle'))
    return d


def grafico_rosca(fatias, w, h):
    d = Drawing(w, h)
    d.add(String(0, h - 10, 'Situação dos itens triados', fontName=FB, fontSize=9, fillColor=AZUL))
    total = sum(f[1] for f in fatias) or 1
    cx, cy, r = 62, (h - 14) / 2 + 2, 52
    ang = 90.0
    for nome, n, cor in fatias:
        if n <= 0:
            continue
        ext = 360.0 * n / total
        d.add(Wedge(cx, cy, r, ang - ext, ang, radius1=r * 0.58, fillColor=cor, strokeColor=colors.white, strokeWidth=1.2))
        ang -= ext
    d.add(String(cx, cy + 2, num(total), fontName=FB, fontSize=14, fillColor=AZUL, textAnchor='middle'))
    d.add(String(cx, cy - 9, 'itens triados', fontName=FT, fontSize=7.4, fillColor=CINZA, textAnchor='middle'))
    y = h - 34
    for nome, n, cor in fatias:
        d.add(Rect(135, y - 1, 8, 8, fillColor=cor, strokeColor=None))
        d.add(String(148, y, f'{nome}', fontName=FT, fontSize=7.8, fillColor=TEXTO))
        d.add(String(w - 4, y, f'{num(n)}  ({n / total:.0%})', fontName=FB, fontSize=7.8, fillColor=TEXTO, textAnchor='end'))
        y -= 15
    return d


def funil(etapas, w):
    """etapas: [(rótulo, contagem, valor_texto, cor)] -> barras horizontais proporcionais."""
    h = 34 * len(etapas)
    d = Drawing(w, h)
    mx = max(e[1] for e in etapas) or 1
    y = h - 28
    for rot, n, val, cor in etapas:
        larg = max(6, (w - 250) * n / mx)
        d.add(String(0, y + 11, rot, fontName=FB, fontSize=8.6, fillColor=TEXTO))
        d.add(String(0, y + 1, val, fontName=FT, fontSize=7.4, fillColor=CINZA))
        d.add(Rect(235, y, larg, 20, fillColor=cor, strokeColor=None, rx=3, ry=3))
        d.add(String(235 + larg + 6, y + 6, num(n), fontName=FB, fontSize=10, fillColor=AZUL))
        y -= 34
    return d


def tabela(dados, larguras, cab=True, zebra=True, extra=(), fs=7.6):
    t = Table(dados, colWidths=larguras, repeatRows=1 if cab else 0)
    est = [('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('FONTNAME', (0, 0), (-1, -1), FT), ('FONTSIZE', (0, 0), (-1, -1), fs),
           ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('LEFTPADDING', (0, 0), (-1, -1), 5),
           ('RIGHTPADDING', (0, 0), (-1, -1), 5), ('LINEBELOW', (0, 0), (-1, -1), 0.3, BORDA)]
    if cab:
        est += [('BACKGROUND', (0, 0), (-1, 0), AZUL), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('FONTNAME', (0, 0), (-1, 0), FB)]
    if zebra:
        for r in range(1 if cab else 0, len(dados)):
            if (r % 2) == 0:
                est.append(('BACKGROUND', (0, r), (-1, r), FUNDO))
    t.setStyle(TableStyle(est + list(extra)))
    return t


# ----------------------------------------------------------------------------------------------- páginas
class Numerada(canvas.Canvas):
    rodape = ''

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._salvas = []

    def showPage(self):
        self._salvas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._salvas)
        for estado in self._salvas:
            self.__dict__.update(estado)
            if self._pageNumber > 1:
                self.setStrokeColor(BORDA); self.setLineWidth(0.5)
                self.line(ML, 1.05 * cm, LARG - MR, 1.05 * cm)
                self.setFont(FT, 7.2); self.setFillColor(CINZA)
                self.drawString(ML, 0.65 * cm, self.rodape)
                self.drawRightString(LARG - MR, 0.65 * cm, f'Página {self._pageNumber} de {n}')
            super().showPage()
        super().save()


def _faixa_topo(c, doc, titulo):
    c.saveState()
    c.setFillColor(AZUL)
    c.rect(0, PAGINA[1] - 1.25 * cm, LARG, 1.25 * cm, stroke=0, fill=1)
    c.setFillColor(TEAL)
    c.rect(0, PAGINA[1] - 1.25 * cm, 0.55 * cm, 1.25 * cm, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont(FB, 11)
    c.drawString(1.3 * cm, PAGINA[1] - 0.8 * cm, titulo)
    c.setFont(FT, 8)
    c.drawRightString(LARG - MR, PAGINA[1] - 0.8 * cm, doc.cliente_linha)
    c.restoreState()


COLS = [6.5 * cm, 5.7 * cm, 1.0 * cm, 1.8 * cm, 3.7 * cm, 1.3 * cm, 1.6 * cm, 1.6 * cm, 0.9 * cm, 1.6 * cm, 2.0 * cm]
COLS[-1] = UTIL - sum(COLS[:-1])
ROTULOS = ['ITEM DO ESTOQUE', 'CHAVE DE ACESSO DA NF-E', 'ITEM', 'EMISSÃO', 'ITEM RASTREADO NA NOTA', 'QTD USADA', 'VL MERC.', 'BC ST', 'ALÍQ.', 'CRÉDITO LINHA', 'CRÉDITO DO ITEM']


def _cabecalho_colunas(c, doc):
    c.saveState()
    y = PAGINA[1] - 1.25 * cm - 0.62 * cm
    c.setFillColor(AZUL2)
    c.rect(ML, y, UTIL, 0.55 * cm, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont(FB, 6.6)
    x = ML
    for i, (rot, w) in enumerate(zip(ROTULOS, COLS)):
        if i >= 5:
            c.drawRightString(x + w - 4, y + 0.19 * cm, rot)
        else:
            c.drawString(x + 5, y + 0.19 * cm, rot)
        x += w
    c.restoreState()


class Doc(BaseDocTemplate):
    cliente_linha = ''


def montar_doc(caminho, cli):
    doc = Doc(caminho, pagesize=PAGINA, leftMargin=ML, rightMargin=MR, topMargin=1.25 * cm, bottomMargin=1.3 * cm,
              title=f"Levantamento de crédito de ICMS sobre estoque — {cli['cliente']}", author='skill credito-icms-estoque-st')
    doc.cliente_linha = f"{cli['cliente']}  ·  CNPJ {_fmt_cnpj(cli['cnpj'])}"
    Numerada.rodape = f"{cli['cliente']}  ·  Levantamento de crédito de ICMS sobre estoque  ·  Portaria CAT 28/2020"
    f_capa = Frame(ML, 1.3 * cm, UTIL, PAGINA[1] - 1.3 * cm - 3.6 * cm, id='capa', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    f_corpo = Frame(ML, 1.3 * cm, UTIL, PAGINA[1] - 1.3 * cm - 1.25 * cm - 0.45 * cm, id='corpo', leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=0)
    f_det = Frame(ML, 1.3 * cm, UTIL, PAGINA[1] - 1.3 * cm - 1.95 * cm, id='det', leftPadding=0, rightPadding=0,
                  topPadding=2, bottomPadding=0)

    def capa(c, d):
        c.saveState()
        c.setFillColor(AZUL); c.rect(0, PAGINA[1] - 3.6 * cm, LARG, 3.6 * cm, stroke=0, fill=1)
        c.setFillColor(TEAL); c.rect(0, PAGINA[1] - 3.6 * cm, 0.7 * cm, 3.6 * cm, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont(FB, 22)
        c.drawString(1.6 * cm, PAGINA[1] - 1.55 * cm, 'Levantamento de crédito de ICMS sobre estoque')
        c.setFont(FT, 11.5)
        c.drawString(1.6 * cm, PAGINA[1] - 2.25 * cm, 'Exclusão de produtos do regime de ICMS-ST  ·  Portaria CAT 28/2020 (SP)  ·  Portaria CAT 68/2019')
        c.setFont(FB, 11); c.drawString(1.6 * cm, PAGINA[1] - 3.05 * cm, d.cliente_linha)
        c.restoreState()

    doc.addPageTemplates([PageTemplate(id='capa', frames=[f_capa], onPage=capa),
                          PageTemplate(id='corpo', frames=[f_corpo], onPage=lambda c, d: _faixa_topo(c, d, 'Levantamento de crédito de ICMS sobre estoque')),
                          PageTemplate(id='detalhe', frames=[f_det], onPage=lambda c, d: (_faixa_topo(c, d, 'Detalhamento item a item'), _cabecalho_colunas(c, d)))])
    return doc


def _fmt_cnpj(c):
    c = re.sub(r'\D', '', str(c))
    return f'{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}' if len(c) == 14 else c


# ----------------------------------------------------------------------------------------------- conteúdo
def secao_resumo(D):
    cli, tot = D['cli'], D['tot']
    w4 = (UTIL - 3 * 0.35 * cm) / 4
    anexo = 'Anexo V · Simples Nacional' if cli['regime'] == 'SN' else 'Anexo IV · RPA'
    w3 = (UTIL - 2 * 0.35 * cm) / 3
    cards = Table([[kpi('Crédito total', brl(tot['total']), anexo, AZUL, w3),
                    kpi('Mercadorias com crédito', num(tot['itens']), f"{num(tot['notas'])} itens de nota, cada um usado uma única vez", TEAL, w3),
                    kpi('Estoque que saiu da ST', brl(D['tri']['Valor total'].sum()), f"{num(len(D['tri']))} itens triados, a custo", CINZA, w3)]],
                  colWidths=[w3 + 0.35 * cm] * 3)
    cards.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0.35 * cm), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    linhas = ['<b>Como o crédito foi apurado.</b> O <b>crédito total</b> soma todas as mercadorias com nota provada (EAN ou descrição de alta confiança, fator '
              'comprovado) e valor calculado pela fórmula do anexo; cada linha é reproduzível pelos parâmetros exportados no Anexo II. '
              'As premissas adotadas em parte das mercadorias aparecem como observações do cálculo, já incluídas no total.',
              '• <b>Anexo da CAT 68:</b> anexo parcial sem CEST e NCM em mais de um anexo são resolvidos pela descrição do produto (a que mais corresponde à descrição legal do item).',
              '• <b>Uso único das notas:</b> cada item de nota supre o estoque no máximo pela quantidade comprada, em todas as datas; '
              'itens casados pelo EAN escolhem as notas primeiro.',
              '• <b>Valor da mercadoria</b> líquido de desconto (base do ICMS próprio do fornecedor), sem limitar o crédito ao ICMS-ST destacado; redução exige enquadramento fiscal explícito.']
    alerta = caixa(Paragraph('<br/>'.join(linhas), S['pp']), fundo=colors.HexColor('#EAF6F4'), borda=colors.HexColor('#B7E0D8'), cor_borda_esq=TEAL, pad=7)
    gw = (UTIL - 0.6 * cm) / 2
    graficos = Table([[grafico_barras(D['por_data'], gw, 175), grafico_rosca(D['situacao'], gw, 175)]], colWidths=[gw + 0.6 * cm, gw])
    graficos.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    meta = Paragraph(f"<b>Regime:</b> {esc(cli['regime'])} ({esc(cli.get('origem_regime', ''))})  ·  <b>Notas de compra lidas:</b> {num(D['n_xml'] or 0)} XML  ·  "
                     f"<b>Estoque:</b> {num(D['estoque_itens'])} linhas em {num(D['estoque_posicoes'])} posição(ões), {brl(D['estoque_valor'])} a custo  ·  <b>Gerado em</b> {date.today().strftime('%d/%m/%Y')}", S['pp'])
    top = sorted(D['itens'].values(), key=lambda i: -i['total'])[:6]
    dados = [[Paragraph(c, S['th_d'] if k >= 2 else S['th']) for k, c in enumerate(('Maiores créditos', 'Anexo', 'Estoque (un.)', 'Notas usadas', 'Crédito'))]]
    for i in top:
        dados.append([Paragraph(f"<b>{esc(i['desc'])}</b>", S['cel']), Paragraph(esc(i['anexo']), S['cel']), Paragraph(num(i['qtd'], 0), S['cel_d']),
                      Paragraph(num(len(i['linhas'])), S['cel_d']), Paragraph(f"<b>{brl(i['total'])}</b>", S['cel_d'])])
    maiores = tabela(dados, [UTIL - 15.4 * cm, 2.4 * cm, 3.0 * cm, 3.0 * cm, 7.0 * cm])
    return [Spacer(1, 0.25 * cm), cards, Spacer(1, 0.3 * cm), alerta, Spacer(1, 0.3 * cm), graficos, Spacer(1, 0.1 * cm), maiores, Spacer(1, 0.15 * cm), meta]


def secao_como(D):
    tri, loc, rp = D['tri'], D['loc'], D['rp']
    tri_n = len(tri)
    tri_v = tri['Valor total'].sum()
    sit = loc['Situação']
    achados = int(sit.str.startswith('Confirmado').sum())
    com_cred = int((rp['Total crédito (item 16)'] > 0).sum())
    f = funil([('Estoque recebido', D['estoque_itens'], f"{num(D['estoque_posicoes'])} posição(ões) · {brl(D['estoque_valor'])} a custo", CINZA_CL),
               ('Saíram da ST (triagem)', tri_n, f'{brl(tri_v)} a custo · regra de ouro por NCM / NCM+CEST', AZUL2),
               ('Localizados em notas provadas', achados, 'antes da vigência da exclusão, por EAN ou descrição A/B', TEAL),
               ('Com crédito apurado', com_cred, f"{brl(D['tot']['total'])} pelas fórmulas do Anexo {_anexo(D)}", VERDE)], UTIL - 1 * cm)
    passos = [
        ('1', 'Triagem do estoque', 'Anexo da CAT 68/2019 que saiu <b>por inteiro</b> casa só pelo <b>NCM</b>; saída <b>parcial</b>, por <b>NCM + CEST</b>. Cada posição de estoque vale para a revogação do dia seguinte.'),
        ('2', 'Localização nas notas', 'EAN exato, depois EAN da caixa/unidade e, por último, a <b>descrição</b> (nome, dose, embalagem, laboratório...). Só entra a descrição de alta confiança (níveis A e B, sem ambiguidade).'),
        ('3', 'Fator de conversão', 'Quantas unidades do estoque vêm em 1 unidade da nota (fardo, display...). Sai da descrição do estoque, do XML e do preço. Fator sem prova não entra no crédito.'),
        ('4', 'Notas que suprem o estoque', 'Só notas <b>anteriores à vigência</b>, da mais recente para a mais antiga, até cobrir a quantidade; cada nota é usada <b>uma única vez</b>. Base de ST <b>unitária</b> × quantidade usada; alíquota da ST da nota ou do estoque.'),
        (('5', 'Fórmula do Anexo V', 'Por item de nota: <b>(BC ST − valor da mercadoria) × alíquota</b>. Total do item = soma das linhas calculadas (piso zero), sem teto pelo ST destacado. Reduções sem enquadramento ficam pendentes.')
         if _sn(D) else
         ('5', 'Fórmulas do Anexo IV', 'Por item de nota, conforme o fornecedor: <b>RPA ou ST retida antes = BC ST × alíquota</b>; Simples com retenção na nota = <b>(BC ST − valor da mercadoria) × alíquota</b>. Reduções sem enquadramento ficam pendentes.')),
    ]
    larg = (UTIL - 4 * 0.3 * cm) / 5
    cels = []
    for n, tit, txt in passos:
        c = Table([[Paragraph(f'<font color="white"><b>{n}</b></font>', st('n', fontName=FB, fontSize=13, leading=15, alignment=TA_CENTER))],
                   [Paragraph(f'<b>{tit}</b>', st('tp', fontName=FB, fontSize=9, leading=11, textColor=AZUL))], [Paragraph(txt, S['pp'])]], colWidths=[larg])
        c.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, 0), TEAL), ('BOX', (0, 0), (-1, -1), 0.6, BORDA), ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                               ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 5), ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7)]))
        cels.append(c)
    linha = Table([cels], colWidths=[larg + 0.3 * cm] * 5)
    linha.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0.3 * cm), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    return [Paragraph('Como o crédito foi apurado', S['h1']), Paragraph('Do estoque recebido até o crédito por item, em cinco passos.', S['p']), Spacer(1, 0.2 * cm),
            caixa(f, fundo=colors.white, pad=10), Spacer(1, 0.35 * cm), linha]


def _sn(D):
    return D['cli']['regime'] == 'SN'


def _anexo(D):
    return 'V' if _sn(D) else 'IV'


def _expr(r):
    """Conta da linha com os números, conforme a fórmula aplicada (Anexo IV ou V)."""
    f = str(r.get('Fórmula aplicada', ''))
    bc, v, a, c = brl(r['BC ST']), brl(r['vl Mercd']), f"{r['alíquota interna (inclui FCP)']:g}%", brl(r['crédito'])
    if f == 'C = BC ST x Alíquota interna':
        return f"{bc} × {a} = <b>{c}</b>"
    if f == 'C = (BC ST - VlMerc) x Alíquota interna':
        return f"({bc} − {v}) × {a} = <b>{c}</b>"
    return f"{esc(f.replace('C = ', ''))} = <b>{c}</b>"


def _exemplo(D):
    """Item real com 2 ou 3 notas, com desconto: a melhor ilustração da conta."""
    melhor = None
    for i in D['itens'].values():
        g = i['linhas']
        if 2 <= len(g) <= 3 and i['total'] > 0 and (g['Desconto (vDesc)'].fillna(0) > 0).any() and (g['crédito'] > 0).all():
            if melhor is None or (10 < i['total'] < 60 and abs(i['total'] - 25) < abs(melhor['total'] - 25)):
                melhor = i
    return melhor


def secao_memoria(D):
    el = []
    el.append(Paragraph('Memória de cálculo', S['h1']))
    txt_formula = ('C &nbsp;=&nbsp; ( BC ST &nbsp;−&nbsp; VlMerc ) &nbsp;×&nbsp; alíquota interna' if _sn(D)
                   else 'C &nbsp;=&nbsp; BC ST &nbsp;×&nbsp; alíquota interna')
    formula = Table([[Paragraph(txt_formula, S['form'])]], colWidths=[UTIL * 0.55])
    formula.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EAF6F4')), ('BOX', (0, 0), (-1, -1), 1, TEAL), ('TOPPADDING', (0, 0), (-1, -1), 10),
                                 ('BOTTOMPADDING', (0, 0), (-1, -1), 10)]))
    abertura = ('<b>Anexo V da Portaria CAT 28/2020</b> (detentor do estoque no Simples Nacional), aplicada <b>a cada item de nota fiscal</b> que supre o estoque.<br/>'
                if _sn(D) else
                '<b>Anexo IV da Portaria CAT 28/2020</b> (detentor do estoque no RPA), aplicada <b>a cada item de nota fiscal</b> que supre o estoque. '
                'Fórmula principal (fornecedor RPA, ou ST retida antes do fornecedor); com fornecedor do Simples que retém a ST na nota: (BC ST − VlMerc) × alíquota '
                '(interna) ou BC ST × alíquota interna − VlMerc × alíquota interestadual. Todas as fórmulas usadas estão no quadro abaixo.<br/>')
    termos = Paragraph(abertura +
                       '<b>BC ST</b> = base da substituição tributária do item: <i>vBCST</i> (ST retida na própria nota, CST 10/70) mais <i>vBCSTRet</i> (ST retida antes, CST 60/500), '
                       'por unidade, multiplicada pela quantidade do estoque que a nota supre.<br/>'
                       '<b>VlMerc</b> = valor da operação líquido de desconto: vProd + frete + seguro + outras despesas − vDesc (a base do ICMS próprio do fornecedor).<br/>'
                       '<b>Alíquota interna</b> = pICMSST + pFCPST (ST retida na nota) ou pST (ST retida antes; já inclui o FCP) e, quando a nota não traz, a alíquota interna do item no estoque.', S['pp'])
    topo = Table([[formula, termos]], colWidths=[UTIL * 0.55 + 0.4 * cm, UTIL * 0.45 - 0.4 * cm])
    topo.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (0, 0), 0.4 * cm)]))
    el += [topo, Spacer(1, 0.25 * cm)]
    regras = [['Regra de ouro', 'O que significa na prática'],
              ['1. Triagem', 'Anexo que saiu inteiro da CAT 68/2019 casa só por NCM; saída parcial, por NCM + CEST (o CEST vem da nota pelo EAN). Sem CEST, ou com o NCM em mais de um anexo, o anexo e o item são escolhidos pela descrição do produto.'],
              ['2. Estoque suprido por notas', 'A quantidade do estoque é coberta por uma ou mais notas de compra, o máximo possível; a mais recente primeiro, a última em parte.'],
              ['3. Base unitária', 'Base de ST e ST retido anteriormente de cada item de nota divididas pela quantidade da nota (já em unidades de estoque) e multiplicadas pela quantidade usada.'],
              ['4. Alíquota', 'pICMSST + pFCPST quando a nota retém a ST; pST sozinho na ST retida antes (já traz o FCP); senão a alíquota interna do item no estoque.'],
              ['5. Só antes da vigência', 'Somente notas emitidas antes da data de revogação do produto na CAT 68/2019, autorizadas, não canceladas e sem devolução.'],
              ['Regime do fornecedor', 'Pelo código de tributação do ICMS do item: CSOSN (3 dígitos) = Simples Nacional; CST (2 dígitos) = regime normal (RPA). O CRT só decide quando falta o CST. '
               + ('No Anexo V a fórmula é a mesma para fornecedor RPA ou Simples.' if _sn(D) else
                'No Anexo IV o regime do fornecedor muda a fórmula; combinações que a tabela não lista seguem a regra da mesma carga, por analogia (ver premissas).')],
              ['Responsável pela ST', 'Base de ST na própria nota (vBCST) = retenção pelo fornecedor; só vBCSTRet = retenção por substituto anterior ao fornecedor.'],
              ['Redução de BC', 'Exige enquadramento fundamentado (aplicável ou não ao consumidor final, pelo dispositivo do RICMS/SP). pRedBc da fórmula = o '
               'legal quando o dispositivo fixa a carga; senão o pRedBCST da nota. O pRedBC da operação própria não é levado à fórmula da ST sem fundamento.'],
              (['Fórmula com redução (Anexo V)', 'A fórmula sai do enquadramento jurídico, pelo texto do Anexo V. A comparação com o ICMS-ST destacado é só '
                'diagnóstico, registrado no alerta da linha; não troca a fórmula.'] if _sn(D) else
               ['Fórmula com redução (Anexo IV)', 'Fórmula do Anexo IV. Se a BC ST da nota parece já reduzida (BC ST × alíquota = ICMS-ST + ICMS próprio), a linha '
                'leva observação do cálculo, com o valor sem reaplicar a redução como alternativa.']),
              ['Observações do cálculo', 'Analogias, alíquotas presumidas, conflito CST × CRT, enquadramento por análise, percentual divergente e documento a '
               'conferir entram no crédito com a premissa registrada na mercadoria; guarde o fundamento de cada uma.'],
              ['Total do item', 'Soma dos créditos das linhas, com piso zero (a exclusão da ST nunca gera débito) sem teto pelo ICMS-ST destacado.']]
    el.append(tabela([[Paragraph(f'<b>{a}</b>' if i else a, S['th'] if i == 0 else S['cel_b']), Paragraph(b, S['th'] if i == 0 else S['cel'])] for i, (a, b) in enumerate(regras)],
                     [4.5 * cm, UTIL - 4.5 * cm]))
    L = D['L']
    calc = L[L['crédito'].notna()].copy()
    sem = calc['Fórmula aplicada'].fillna('') == ''
    calc.loc[sem, 'Linha da tabela (Anexo IV/V)'] = 'Sem base de ST na nota (art. 4º, I)'
    calc.loc[sem, 'Fórmula aplicada'] = 'crédito zero'
    if len(calc):
        g = calc.groupby(['Linha da tabela (Anexo IV/V)', 'Fórmula aplicada'])['crédito'].agg(['size', 'sum']).reset_index().sort_values('sum', ascending=False)
        dados = [[Paragraph(c, S['th_d'] if k >= 2 else S['th']) for k, c in enumerate(('Linha da tabela aplicada', 'Fórmula', 'Linhas de nota', 'Crédito'))]]
        for _, r in g.iterrows():
            dados.append([Paragraph(esc(r['Linha da tabela (Anexo IV/V)']), S['cel']), Paragraph(esc(r['Fórmula aplicada']), S['cel']),
                          Paragraph(num(r['size']), S['cel_d']), Paragraph(brl(r['sum']), S['cel_d'])])
        el += [Paragraph('Fórmulas aplicadas neste levantamento', S['h2']),
               tabela(dados, [UTIL * 0.42, UTIL * 0.34, UTIL * 0.1, UTIL * 0.14])]
    ex = _exemplo(D)
    if ex:
        el += [Paragraph('Exemplo real, passo a passo', S['h2']),
               Paragraph(f"<b>{esc(ex['desc'])}</b> · EAN {ex['ean']} · NCM {ex['ncm']} · estoque de <b>{num(ex['qtd'], 0)}</b> un. · revogado em {ex['rev'].strftime('%d/%m/%Y')} (Anexo {esc(ex['anexo'])}). "
                         'O estoque é suprido pelas notas abaixo, da mais recente para a mais antiga:', S['p']), Spacer(1, 0.1 * cm)]
        cab = ['Chave de acesso', 'Emissão', 'Qtd usada', 'vProd', 'Desconto', 'VlMerc líquido', 'BC ST', 'Alíquota', 'Crédito (fórmula da linha)']
        dados = [[Paragraph(c, S['th_d'] if k >= 2 else S['th']) for k, c in enumerate(cab)]]
        for _, r in ex['linhas'].iterrows():
            dados.append([Paragraph(r['chave NFe'], S['mono']), Paragraph(data_br(r['Emissão']), S['cel']), Paragraph(num(r['qtde utilizada do item para informar o estoque'] * r['fator de conversão para unid. de estoque'], 0), S['cel_d']),
                          Paragraph(brl(r['Vl mercadoria bruto (vProd)']), S['cel_d']), Paragraph(brl(r['Desconto (vDesc)'] if r['Desconto (vDesc)'] == r['Desconto (vDesc)'] else 0), S['cel_d']), Paragraph(brl(r['vl Mercd']), S['cel_d']),
                          Paragraph(brl(r['BC ST']), S['cel_d']), Paragraph(f"{r['alíquota interna (inclui FCP)']:g}%", S['cel_d']),
                          Paragraph(_expr(r), S['cel_d'])])
        dados.append([Paragraph('<b>Crédito do item</b>', S['cel']), '', '', '', '', '', '', '', Paragraph(f"<b>{brl(ex['total'])}</b>", st('tt', fontName=FB, fontSize=9, leading=11, alignment=TA_RIGHT, textColor=VERDE))])
        el.append(tabela(dados, [5.6 * cm, 1.7 * cm, 1.5 * cm, 1.9 * cm, 1.9 * cm, 2.2 * cm, 1.9 * cm, 1.5 * cm, UTIL - 18.2 * cm],
                         extra=[('SPAN', (0, len(dados) - 1), (7, len(dados) - 1)), ('LINEABOVE', (0, len(dados) - 1), (-1, len(dados) - 1), 0.8, AZUL)]))
    return el


def secao_competencia(D):
    comp = D['comp']
    if not _sn(D) and len(comp):                                     # RPA: soma as parcelas que caem no mesmo mês
        comp = comp.copy()
        comp['_ord'] = comp['Competência'].str[3:] + comp['Competência'].str[:2]
        comp['Observação'] = comp['Parcela'].astype(str)
        comp = (comp.groupby(['_ord', 'Competência'], as_index=False)
                .agg({'Crédito a lançar': 'sum', 'Forma de lançamento': 'first', 'Observação': lambda s: 'parcelas ' + ' + '.join(s)})
                .sort_values('_ord'))
    el = [Spacer(1, 0.35 * cm), Paragraph('Crédito por competência', S['h2'])]
    dados = [[Paragraph(c, S['th_d'] if c == 'Crédito a lançar' else S['th']) for c in (('Competência de dedução' if _sn(D) else 'Competência de lançamento'), 'Crédito a lançar', 'Forma de lançamento', 'Composição')]]
    for _, r in comp.iterrows():
        dados.append([Paragraph(f"<b>{esc(r['Competência'])}</b>", S['cel']), Paragraph(f"<b>{brl(r['Crédito a lançar'])}</b>", S['cel_d']), Paragraph(esc(r['Forma de lançamento']), S['cel']),
                      Paragraph(esc(r['Observação']), S['cel'])])
    dados.append([Paragraph('<b>Total</b>', S['cel']), Paragraph(f"<b>{brl(comp['Crédito a lançar'].sum())}</b>", S['cel_d']), '', ''])
    el.append(tabela(dados, [3.3 * cm, 3.0 * cm, 8.2 * cm, UTIL - 14.5 * cm], extra=[('LINEABOVE', (0, len(dados) - 1), (-1, len(dados) - 1), 0.8, AZUL)]))
    el.append(Spacer(1, 0.1 * cm))
    el.append(Paragraph('No Simples Nacional o crédito não é parcelado: é deduzido do ICMS devido no PGDAS-D (campo "redução da base de cálculo") no mês seguinte ao da exclusão; '
                        'o que exceder o ICMS do mês compensa nos meses seguintes (Portaria CAT 28/2020, art. 3º, §3º).' if _sn(D) else
                        'No RPA o crédito de cada data de revogação é lançado em 12 parcelas mensais, iguais e sucessivas, a partir do primeiro mês de vigência da exclusão, '
                        'no Bloco E da EFD (código de ajuste SP020750, "Outros Créditos"), com menção à Portaria CAT 28/2020 (art. 3º, §2º, redação da Portaria SRE 07/26). '
                        'Quando parcelas de datas diferentes caem no mesmo mês, o quadro mostra a soma.', S['peq']))
    tot = D['tot']
    el.append(Paragraph(f"Composição: soma das linhas {brl(tot['soma_linhas'])} + ajuste do piso zero por mercadoria "
                        f"{brl(tot['total'] - tot['soma_linhas'])} = {brl(tot['total'])}, valor do lançamento. Este relatório fornece "
                        'os valores e a memória; não comprova a escrituração do Registro de Inventário (art. 2º, II) nem os lançamentos (art. 3º).', S['peq']))
    return el


def secao_anexos(D):
    por_anexo = defaultdict(lambda: [0, 0.0, ''])
    for i in D['itens'].values():
        if i['total'] > 0:
            a = por_anexo[i['anexo']]
            a[0] += 1; a[1] += i['total']; a[2] = i['segmento']
    dados = [[Paragraph(c, S['th_d'] if k >= 2 else S['th']) for k, c in enumerate(('Anexo da CAT 68/2019', 'Segmento', 'Itens com crédito', 'Crédito'))]]
    for anexo, (n, v, seg) in sorted(por_anexo.items(), key=lambda kv: -kv[1][1]):
        dados.append([Paragraph(f'<b>Anexo {esc(anexo)}</b>', S['cel']), Paragraph(esc(seg.title()), S['cel']), Paragraph(num(n), S['cel_d']), Paragraph(f'<b>{brl(v)}</b>', S['cel_d'])])
    return [KeepTogether([Paragraph('Crédito por anexo da CAT 68/2019', S['h2']), tabela(dados, [3.3 * cm, UTIL - 12.3 * cm, 3.5 * cm, 5.5 * cm])])]


def secao_pendencias(D):
    p = D['pend']
    p = p[p['Tipo'] != 'Fora do crédito por falta de prova']
    g = p.groupby(['Severidade', 'Tipo']).agg(n=('EAN', 'count'), acao=('Ação sugerida', 'first')).reset_index()
    ordem = {'BLOQUEANTE': 0, 'Alerta': 1, 'Conferir': 2, 'Info': 3}
    g['o'] = g['Severidade'].map(ordem)
    g = g.sort_values(['o', 'n'], ascending=[True, False])
    cor = {'BLOQUEANTE': VERM, 'Alerta': AMBAR, 'Conferir': AZUL2, 'Info': CINZA_CL}
    datas_falta = sorted({m for x in p.loc[p['Tipo'] == 'Falta posição de estoque', 'Ação sugerida'] for m in re.findall(r'\d{2}/\d{2}/\d{4}', x)},
                         key=lambda x: x[6:] + x[3:5] + x[:2])
    dados = [[Paragraph(c, S['th']) for c in ('Severidade', 'Pendência', 'Ocorrências', 'Ação sugerida')]]
    extra = []
    for k, (_, r) in enumerate(g.iterrows(), start=1):
        acao = r['acao']
        if r['Tipo'] == 'Falta posição de estoque' and datas_falta:
            acao = 'Enviar as posições de estoque de ' + ' e '.join(datas_falta) + ', se havia estoque nessas datas'
        dados.append([Paragraph(f"<b>{r['Severidade']}</b>", st('sv', fontName=FB, fontSize=7.4, leading=9, textColor=cor.get(r['Severidade'], CINZA))), Paragraph(esc(r['Tipo']), S['cel']),
                      Paragraph(num(r['n']), S['cel_c']), Paragraph(esc(acao), S['cel'])])
        extra.append(('LINEBEFORE', (0, k), (0, k), 3, cor.get(r['Severidade'], CINZA)))
    return [Paragraph('Pendências que pedem ação', S['h1']), tabela(dados, [2.4 * cm, 7.0 * cm, 2.2 * cm, UTIL - 11.6 * cm], extra=extra),
            Spacer(1, 0.1 * cm), Paragraph('A lista completa, item a item, está na aba "Pendências" da planilha resultado_levantamento.xlsx.', S['peq']), Spacer(1, 0.4 * cm)]


def secao_em_aberto(D):
    """Pontos que continuam em aberto: classificar ou mostrar não é validar (revisão fiscal)."""
    tot = D['tot']
    itens = [
        ('Piso zero por mercadoria', f"Linhas negativas compensam dentro da mercadoria e o total nunca fica abaixo de zero (leitura do art. 3º, §1º). "
                                     f"Efeito no total: {brl(tot['total'] - tot['soma_linhas'])}."),
        ('VlMerc líquido de desconto', 'O valor da mercadoria entra líquido de desconto (base do ICMS próprio do fornecedor), apoiado na reprodução do imposto '
                                       'destacado nas notas; a portaria não menciona desconto. A alternativa com vProd está no Resumo da planilha.'),
        ('FCP com base própria', 'Quando a base do FCP difere da base da ST, ICMS e FCP são calculados cada um na sua base; a portaria usa uma alíquota única, '
                                 'o efeito está incluído no total.'),
        ('NF complementar', 'É somada ao item da nota original quando se liga a ele (refNFe e código, EAN ou número do item); sem vínculo, as linhas da '
                            'original levam observação.'),
        ('Entrada da mercadoria', 'Sem registro de entrada (EFD, livro, manifestação), a linha registra a evidência disponível (dhSaiEnt do emitente ou só a '
                                  'emissão), que não comprova o recebimento.'),
        ('Art. 3º, §4º (CAT 75/08)', 'A parcela do inciso XVI do art. 2º do RICMS incluída na retenção não é identificável na NF-e e não é deduzida.'),
    ] + ([('Analogias do Anexo IV', 'Combinações que o Anexo IV não lista entram no crédito por analogia, com fundamento oficial específico a documentar.')]
         if not _sn(D) else [])
    return [KeepTogether([Paragraph('Pontos de atenção', S['h2']),
                          Paragraph('Interpretações adotadas no cálculo e já incluídas no total; guarde o fundamento de cada uma antes do lançamento.', S['p']),
                          tabela([[Paragraph(f'<b>{a}</b>', S['cel']), Paragraph(b, S['cel'])] for a, b in itens], [4.6 * cm, UTIL - 4.6 * cm], cab=False)])]


def secao_interpretativo(D):
    """Observações do cálculo: premissas adotadas em parte das mercadorias, já incluídas no total."""
    if not D['interp']:
        return []
    p = D['pend']
    mot = p[p['Tipo'] == 'Observação do cálculo']
    el = [Paragraph('Observações do cálculo', S['h1']),
          Paragraph(f"<b>{brl(D['tot']['com_obs'])}</b> do total, em {num(D['tot']['n_com_obs'])} mercadorias, foram calculados com uma premissa que convém documentar "
                    '(dispositivo, cadastro fiscal, nota). Estão <b>incluídos no crédito total</b>.', S['p']), Spacer(1, 0.15 * cm)]
    if len(mot):
        dados = [[Paragraph(c, S['th_d'] if k >= 1 else S['th']) for k, c in enumerate(('Premissa', 'Mercadorias', 'Valor incluído'))]]
        for _, r in mot.iterrows():
            texto = str(r['Descrição'])
            n, _, m = texto.partition(' mercadoria(s): ')
            dados.append([Paragraph(esc(m or texto), S['cel']), Paragraph(esc(n), S['cel_d']), Paragraph(brl(r['Valor em estoque'] or 0), S['cel_d'])])
        el.append(tabela(dados, [UTIL - 6.5 * cm, 2.5 * cm, 4.0 * cm]))
        el.append(Paragraph('Uma mercadoria pode ter mais de uma premissa; por isso a soma da coluna pode passar do valor total com observações.', S['peq']))
    top = [x for x in D['interp'] if x['valor'] > 0][:15]
    if top:
        dados = [[Paragraph(c, S['th_d'] if k == 2 else S['th']) for k, c in enumerate(('Maiores valores com observações', 'Premissas', 'Valor'))]]
        for x in top:
            dados.append([Paragraph(f"<b>{esc(x['desc'])}</b>", S['cel']), Paragraph(esc(x['motivos'][:220]), S['cel']), Paragraph(brl(x['valor']), S['cel_d'])])
        el += [Spacer(1, 0.25 * cm), tabela(dados, [7.5 * cm, UTIL - 11.0 * cm, 3.5 * cm])]
    return el


def secao_leitura(D):
    """Página 'Como ler o detalhamento': um bloco real anotado, com a mesma faixa de colunas das páginas seguintes."""
    cand = [i for i in D['itens'].values() if i['total'] > 0 and len(i['linhas']) == 2]
    cand.sort(key=lambda i: -i['total'])
    exemplo = cand[min(3, len(cand) - 1)] if cand else None
    el = [Paragraph('Como ler o detalhamento', S['h1']),
          Paragraph('Cada bloco das próximas páginas mostra <b>um item do estoque</b> e as <b>notas fiscais que o suprem</b>. A leitura é da esquerda para a direita: '
                    'o produto, a chave de acesso e o item da nota que foi rastreado, os valores usados na fórmula e, por fim, o crédito da linha e o crédito total do item.', S['p']),
          Spacer(1, 0.25 * cm)]
    if exemplo:
        cab = Table([[Paragraph(r, S['th_sd'] if k >= 5 else S['th_s']) for k, r in enumerate(ROTULOS)]], colWidths=COLS)
        cab.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), AZUL2), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                                 ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5), ('FONTSIZE', (0, 0), (-1, -1), 6.6)]))
        el += [cab] + _bloco_item(exemplo) + [Spacer(1, 0.3 * cm)]
    itens = [
        ('Item do estoque', 'Descrição, EAN, NCM, anexo da CAT 68/2019 em que o produto estava e quantidade em estoque (un.).'),
        ('Chave de acesso e item', 'A nota fiscal (44 dígitos) e o número do item dentro dela que foram rastreados. É o documento que você consulta no portal da NF-e.'),
        ('Item rastreado na nota', 'Descrição do produto na nota. "fator N" aparece quando a nota vende em caixa/fardo e o estoque em unidade (1 unidade da nota = N do estoque).'),
        ('Qtd usada', 'Quantas unidades do estoque esta nota supre. A nota mais recente vem primeiro; a última pode entrar só em parte.'),
        ('Vl merc. e BC ST', 'Valor da mercadoria (líquido de desconto) e base da substituição tributária proporcionais à quantidade usada.'),
        ('Alíq.', 'pICMSST + pFCPST (ST na própria nota) ou pST (ST retida antes, já com FCP); sem alíquota na nota, a interna do item no estoque.'),
        ('Crédito da linha', ('(BC ST − Vl merc.) × alíquota.' if _sn(D) else 'Fórmula do Anexo IV da linha: BC ST × alíquota (fornecedor RPA ou ST retida antes) ou (BC ST − Vl merc.) × alíquota (fornecedor do Simples que retém na nota).') + ' Em vermelho quando negativo: a base de ST ficou abaixo do valor pago; compensa dentro do item.'),
        ('Crédito do item', 'Soma das linhas, nunca abaixo de zero, sem teto pelo ICMS-ST destacado. É o valor que entra no total.')]
    el.append(tabela([[Paragraph(f'<b>{a}</b>', S['cel']), Paragraph(b, S['cel'])] for a, b in itens], [4.2 * cm, UTIL - 4.2 * cm], cab=False))
    return el


def secao_detalhe(D):
    itens = [i for i in D['itens'].values() if i['total'] > 0]
    grupos = defaultdict(list)
    for i in itens:
        grupos[i['rev']].append(i)
    el = []
    for dt in sorted(grupos):
        lst = sorted(grupos[dt], key=lambda i: -i['total'])
        tot = sum(i['total'] for i in lst)
        titulo = Table([[Paragraph(f"<font color='white'><b>Revogação em {dt.strftime('%d/%m/%Y')}</b> · estoque de {(dt - pd.Timedelta(days=1)).strftime('%d/%m/%Y')} · {len(lst)} itens com crédito</font>",
                                   st('gt', fontName=FB, fontSize=9.6, leading=12)),
                         Paragraph(f"<font color='white'><b>{brl(tot)}</b></font>", st('gv', fontName=FB, fontSize=11, leading=13, alignment=TA_RIGHT))]], colWidths=[UTIL - 4 * cm, 4 * cm])
        titulo.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), TEAL), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                                    ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8)]))
        primeiro = _bloco_item(lst[0])
        el.append(KeepTogether([titulo, Spacer(1, 2), primeiro[0]]))
        el += primeiro[1:]
        for i in lst[1:]:
            el += _bloco_item(i)
        el.append(PageBreak())
    if el and isinstance(el[-1], PageBreak):
        el.pop()
    return el


MAX_LINHAS = 10          # item com mais notas que isso é dividido em partes (uma página tem ~28 linhas)


def _linha_nf(r):
    nf = str(r.get('Descrição na nota', ''))[:46]
    fat = r['fator de conversão para unid. de estoque']
    extra_fator = f" <font size='6' color='#64748B'>· fator {fat:g}</font>" if fat and abs(fat - 1) > 1e-9 else ''
    cr = r['crédito']
    cor_txt = '#DC2626' if (cr is not None and cr < 0) else '#1E293B'
    q = r['qtde utilizada do item para informar o estoque'] * fat
    casas = 0 if abs(q - round(q)) < 1e-3 else 2
    aliq = r['alíquota interna (inclui FCP)']
    return ['', Paragraph(r['chave NFe'], S['mono']), Paragraph(str(r['no. Item']), S['cel_c']), Paragraph(data_br(r.get('Emissão', '')), S['cel']),
            Paragraph(esc(nf) + extra_fator, S['cel']),
            Paragraph(num(q, casas), S['cel_d']), Paragraph(brl(r['vl Mercd']), S['cel_d']), Paragraph(brl(r['BC ST']), S['cel_d']),
            Paragraph(f'{aliq:g}%' if aliq == aliq else '—', S['cel_d']), Paragraph(f"<font color='{cor_txt}'>{brl(cr)}</font>", S['cel_d']), '']


def _tabela_item(cel_item, linhas, cred_txt, cor_cred, validar, largura_total=None):
    linhas[0][0] = cel_item
    linhas[0][-1] = cred_txt
    n = len(linhas)
    t = Table(linhas, colWidths=COLS)
    est = [('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 2.2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2), ('LEFTPADDING', (0, 0), (-1, -1), 5),
           ('RIGHTPADDING', (0, 0), (-1, -1), 5), ('BACKGROUND', (0, 0), (0, -1), FUNDO),
           ('BACKGROUND', (-1, 0), (-1, -1), colors.HexColor('#FFF7E6') if validar else colors.HexColor('#EAF6F4')),
           ('LINEBELOW', (1, 0), (-2, -2), 0.25, BORDA), ('LINEBELOW', (0, -1), (-1, -1), 0.6, CINZA_CL), ('LINEBEFORE', (0, 0), (0, -1), 3, cor_cred)]
    if n > 1:
        est += [('SPAN', (0, 0), (0, n - 1)), ('SPAN', (-1, 0), (-1, n - 1))]
    t.setStyle(TableStyle(est))
    return t


def _bloco_item(i):
    """Lista de flowables do item: um único bloco, ou várias partes quando o item tem muitas notas."""
    g = i['linhas']
    validar = False
    etiqueta = ''
    meta = f"EAN {i['ean']} · NCM {i['ncm']} · Anexo {esc(i['anexo'])} · estoque {num(i['qtd'], 0)} un."
    cor_cred = AMBAR if validar else TEAL
    estilo_total = st('ct', fontName=FB, fontSize=9.4, leading=11, alignment=TA_RIGHT, textColor=AZUL)
    linhas = [_linha_nf(r) for _, r in g.iterrows()]
    if len(linhas) <= MAX_LINHAS:
        cel = Paragraph(f"<b>{esc(i['desc'])}</b>{etiqueta}<br/><font size='6.4' color='#64748B'>{meta}</font>", S['cel'])
        return [KeepTogether([_tabela_item(cel, linhas, Paragraph(f"<b>{brl(i['total'])}</b>", estilo_total), cor_cred, validar)])]
    partes = [linhas[k:k + MAX_LINHAS] for k in range(0, len(linhas), MAX_LINHAS)]
    creditos = [r['crédito'] for _, r in g.iterrows()]
    blocos = []
    for k, parte in enumerate(partes):
        ultima = k == len(partes) - 1
        if k == 0:
            cel = Paragraph(f"<b>{esc(i['desc'])}</b>{etiqueta}<br/><font size='6.4' color='#64748B'>{meta} · {len(linhas)} notas (parte 1/{len(partes)})</font>", S['cel'])
        else:
            cel = Paragraph(f"<font size='6.6' color='#64748B'><i>continuação: {esc(i['desc'])[:48]} (parte {k + 1}/{len(partes)})</i></font>", S['cel'])
        if ultima:
            cred = Paragraph(f"<b>{brl(i['total'])}</b><br/><font size='6' color='#64748B'>total do item</font>", estilo_total)
        else:
            sub = sum(c for c in creditos[k * MAX_LINHAS:(k + 1) * MAX_LINHAS] if c is not None)
            cred = Paragraph(f"<font size='7' color='#64748B'>subtotal {brl(sub)}</font>", st('sub', fontSize=7, leading=8.6, alignment=TA_RIGHT))
        blocos.append(_tabela_item(cel, parte, cred, cor_cred, validar))
    return blocos


def secao_apendice(D):
    rp, pend = D['rp'], D['pend']
    el = [Paragraph('Apêndice', S['h1']), Paragraph('Itens sem crédito', S['h2'])]
    sit = rp['Situação do crédito']
    tri_v = D['tri'].drop_duplicates('EAN').set_index('EAN')['Valor total']
    def val(mask):
        return tri_v.reindex(rp.loc[mask, 'EAN']).sum()
    motivos = [('BC de ST não supera o valor da mercadoria', 'A base de ST da nota é menor ou igual ao valor pago (líquido de desconto): não há margem de ST a creditar.', sit == 'Sem crédito: BC ST não supera o valor da mercadoria'),
               ('Sem base de ST na nota', 'A nota não traz vBCST/vBCSTRet (ex.: CST 00/20, ou CST 60 sem a base). Crédito zero (art. 4º, I); pode haver NF complementar do fornecedor.', sit == 'Sem crédito: sem base de ST'),
               ('Sem nota anterior à vigência', 'Produto não localizado nas notas do pacote, ou só comprado depois da exclusão. Pedir XMLs anteriores a 01/2024 e transferências.', sit == 'Sem crédito: sem nota anterior à vigência')]
    sp = sit == 'Sem crédito: sem prova documental'
    pe = sit.str.startswith('Pendente')
    dados = [[Paragraph(c, S['th_d'] if k >= 2 else S['th']) for k, c in enumerate(('Motivo', 'Explicação', 'Itens', 'Estoque a custo'))]]
    for nome, expl, m in motivos:
        if not m.any():
            continue
        dados.append([Paragraph(f'<b>{nome}</b>', S['cel']), Paragraph(expl, S['cel']), Paragraph(num(int(m.sum())), S['cel_d']), Paragraph(brl(val(m)), S['cel_d'])])
    dados.append([Paragraph('<b>Sem prova documental</b>', S['cel']),
                  Paragraph('Nota só achada por descrição de baixa confiança (ou mais de um produto possível), ou fator de conversão sem prova. '
                            'Fica fora do crédito automaticamente; o detalhe está na trilha técnica.', S['cel']),
                  Paragraph(num(int(sp.sum())), S['cel_d']), Paragraph(brl(val(sp)), S['cel_d'])])
    dados.append([Paragraph('<b>Pendente de enquadramento fiscal</b>', S['cel']),
                  Paragraph('Há linha com redução de BC sem enquadramento informado (ou outro dado fiscal ausente). Essas linhas não são calculadas; '
                            'as demais linhas do mesmo produto continuam no crédito. Informar o enquadramento conforme a legislação do produto.', S['cel']),
                  Paragraph(num(int(pe.sum())), S['cel_d']), Paragraph(brl(val(pe)), S['cel_d'])])
    el.append(tabela(dados, [5.6 * cm, UTIL - 12.4 * cm, 1.8 * cm, 5.0 * cm - 0.0 * cm]))
    el += [Paragraph('Premissas adotadas', S['h2'])]
    dados = [[Paragraph(c, S['th']) for c in ('Premissa', 'Origem', 'Situação')]]
    for _, r in D['prem'].iterrows():
        dados.append([Paragraph(esc(r['Premissa']), S['cel']), Paragraph(esc(r['Origem']), S['cel']), Paragraph(esc(r['Responsável']), S['cel'])])
    el.append(tabela(dados, [UTIL - 9.5 * cm, 5.3 * cm, 4.2 * cm]))
    glos = [('ST', 'Substituição tributária: o fornecedor recolhe antecipadamente o ICMS devido nas etapas seguintes.'),
            ('BC ST', 'Base de cálculo da ST. vBCST: retida na própria nota (CST 10/70). vBCSTRet: retida antes, apenas informada (CST 60/500).'),
            ('VlMerc', 'Valor da mercadoria na entrada; aqui, líquido de desconto (base do ICMS próprio do fornecedor).'),
            ('CEST / NCM', 'Códigos que identificam a mercadoria na ST e na tabela aduaneira; definem se o produto saiu da ST.'),
            ('Estoque D', 'Posição de estoque do último dia antes da vigência da exclusão (art. 2º da CAT 28/2020).'),
            ('Nível A/B/C', 'Confiança da localização por descrição: A e B entram no crédito; C (ou ambíguo) não entra.')]
    el += [KeepTogether([Paragraph('Glossário', S['h2']), tabela([[Paragraph(f'<b>{a}</b>', S['cel']), Paragraph(b, S['cel'])] for a, b in glos], [3.0 * cm, UTIL - 3.0 * cm], cab=False)])]
    return el


# ----------------------------------------------------------------------------------------------- principal
def gerar_pdf(pasta, destino=None):
    D = preparar(carregar(pasta))
    destino = destino or os.path.join(pasta, 'relatorio_levantamento.pdf')
    doc = montar_doc(destino, D['cli'])
    hist = []
    hist += secao_resumo(D)
    hist += [NextPageTemplate('corpo'), PageBreak()] + secao_como(D) + secao_competencia(D)
    hist += [PageBreak()] + secao_memoria(D) + secao_anexos(D)
    interp = secao_interpretativo(D)
    hist += [PageBreak()] + secao_pendencias(D) + ((interp + [PageBreak()]) if interp else []) + secao_leitura(D)
    em_aberto = secao_em_aberto(D)
    hist += [NextPageTemplate('detalhe'), PageBreak()] + secao_detalhe(D)
    hist += [NextPageTemplate('corpo'), PageBreak()] + em_aberto + [Spacer(1, 0.6 * cm)] + secao_apendice(D)
    doc.build(hist, canvasmaker=Numerada)
    return destino


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3) or sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0 if len(sys.argv) == 2 else 1)
    print(gerar_pdf(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None))
