"""Extrai da Portaria CAT 68/2019 (HTML oficial) todos os itens/anexos revogados."""
import re, sys, json, csv
from bs4 import BeautifulSoup

import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BASE = os.path.join(ROOT, 'references', 'base-legal')
SRC = os.path.join(BASE, 'portaria-cat-68-2019.html')
raw = open(SRC, 'rb').read()
try:
    txt = raw.decode('utf-8')
except UnicodeDecodeError:
    txt = raw.decode('utf-8', errors='replace')
soup = BeautifulSoup(txt, 'lxml')

def clean(s):
    return re.sub(r'\s+', ' ', (s or '').replace('​', '').replace('\xa0', ' ')).strip()

MESES = {'janeiro':1,'fevereiro':2,'março':3,'marco':3,'abril':4,'maio':5,'junho':6,'julho':7,'agosto':8,
         'setembro':9,'outubro':10,'novembro':11,'dezembro':12}

def parse_rev(text):
    """Retorna dict com ato revogador, data do ato, DOE e vigência (data de revogação efetiva)."""
    t = clean(text)
    m = re.search(r'Portaria\s+((?:CAT|SRE|SF|SFP)[\s-]*\d+/\d+)', t)
    ato = re.sub(r'\s+', '', m.group(1)).replace('CAT', 'CAT-').replace('SRE', 'SRE-').replace('--', '-') if m else ''
    dm = re.search(r'Portaria\s+(?:CAT|SRE)[\s-]*\d+/\d+\s*,\s*de\s*(\d{2}[-/]\d{2}[-/]\d{4})', t)
    data_ato = dm.group(1).replace('/', '-') if dm else ''
    dd = re.search(r'DOE\s*(\d{2}\s*[-/]\s*\d{2}\s*[-/]\s*\d{4})', t)
    doe = re.sub(r'\s', '', dd.group(1)).replace('/', '-') if dd else ''
    vig = ''
    v = re.search(r'(?:em vigor em|a partir de|vigor a partir de)\s*(?:de\s*)?1[º°o]?\s*de\s*(\w+)\s*de\s*(\d{4})', t, re.I)
    if v and v.group(1).lower() in MESES:
        vig = f"01-{MESES[v.group(1).lower()]:02d}-{v.group(2)}"
    return dict(ato=ato, data_ato=data_ato, doe=doe, vigencia=vig, nota=t)

body = soup.body
out = []
annex = {'num': '', 'titulo': '', 'rev': None}
skip_title_for = None

def handle_annex_p(p):
    t = clean(p.get_text(' '))
    m = re.match(r'^ANEXO\s+([IVXL]+)\b(.*)$', t)
    return m

elements = body.find_all(['p', 'table'])
def norm(t): return re.sub(r'\s+', '', t).lower()
for el in elements:
    if el.name == 'p':
        if el.find_parent('table'):
            continue
        t = clean(el.get_text(' '))
        m = re.match(r'^ANEXO\s+([IVXL]+)\b\s*(.*)$', t)
        if m:
            annex = {'num': m.group(1), 'titulo': '', 'rev': None, 'open': True}
            if 'revogad' in norm(m.group(2)):
                annex['rev'] = parse_rev(m.group(2))
            continue
        if annex['num'] and annex.get('open') and t:
            if 'revogad' in norm(t):
                annex['rev'] = parse_rev(t)
            elif norm(t).startswith('(artigo') or norm(t).startswith('doricms') or norm(t).startswith('nota'):
                pass
            elif not annex['titulo']:
                annex['titulo'] = t
    elif el.name == 'table':
        if el.find_parent('table'):
            continue
        rows = el.find_all('tr')
        if not rows:
            continue
        hdr = [clean(c.get_text(' ')).upper() for c in rows[0].find_all(['td', 'th'])]
        if not hdr or hdr[0] != 'ITEM':
            continue
        annex['open'] = False
        for tr in rows[1:]:
            cells = [clean(c.get_text(' ')) for c in tr.find_all('td')]
            if len(cells) < 3:
                continue
            first = cells[0]
            item_m = re.match(r'^(\d+(?:\.\d+)*)', first)
            if not item_m:
                continue
            out.append(dict(anexo=annex['num'], anexo_titulo=annex['titulo'], item=item_m.group(1),
                       cest=cells[1], ncm=cells[2], descricao=cells[3] if len(cells) > 3 else '',
                       first_cell=first, anexo_rev=annex['rev']))

print(len(out), 'linhas de tabela')
from collections import Counter
print(Counter(r['anexo'] for r in out))

# ---------- classificação ----------
from collections import Counter
if '--acts' in sys.argv:
    c = Counter()
    for r in out:
        if re.search(r'revogad', r['first_cell'], re.I):
            x = parse_rev(r['first_cell']); c[(x['ato'], x['data_ato'], x['doe'], x['vigencia'])] += 1
    for k, v in sorted(c.items()): print(k, v)
