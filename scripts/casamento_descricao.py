"""Localização de item do estoque nas NF-e de compra pela DESCRIÇÃO (quando o EAN não casa).

Método: em vez de comparar textos, extrai ATRIBUTOS da descrição (produto, qualificadores, concentração/gramatura,
volume, unidades por embalagem, forma, laboratório, variante, código de modelo, controle) e compara atributo a
atributo. Duas classes de contradição:
  DURA   -> descartam o par (embalagem diferente, dose diferente, laboratório diferente, nome diferente...);
  SUAVE  -> o par continua possível, mas fica no máximo em 'C' (revisar): qualificador só de um lado,
            dose com item extra, NCM de outro capítulo.
Níveis: 'A' (perfeito), 'B' (alto), 'C' (revisar), None (não casa). Validado com gabarito (itens que casam por EAN,
com o EAN escondido): references/casamento-descricao.md.

Regras que vieram da análise de erros:
- dose combinada é outro produto ("NAPRIX A 5/5MG" != "NAPRIX 5MG"); soma igual é aceita ("900+100MG" = "1000MG");
  40MG/5ML = 8MG/ML;
- qualificadores mudam o produto (A, D, H, PLUS, FORTE, RETARD/LP, INFANTIL, DISPERSIVEL...);
- sais e abreviações de sal (CLORIDRATO/CL/SUCC/TART...) são ruído; "C/" é "com"; controle (C1, A2) não é quantidade;
  "+4 placebos" soma na embalagem; 6 BLT 10 = 60;
- genérico sem laboratório no estoque nunca passa de 'C' (vários laboratórios = vários EANs);
- código de modelo em comum (HEM-7122, HC215) ancora produtos de nome muito diferente.
"""
import html
import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

FORMAS = {
    'COMP': ['COMP', 'CP', 'CPR', 'CPRS', 'COMPR', 'COMPRIM', 'COMPRIMIDO', 'COMPRIMIDOS', 'CPRV', 'COMPS', 'CPD', 'TAB',
             'TABLETE', 'TABLETES'],
    'CAPS': ['CAPS', 'CAP', 'CPS', 'CAPSULA', 'CAPSULAS', 'CAPSGEL', 'CAPSULAGEL', 'CPSGEL'],
    'SOL': ['SOL', 'SOLUC', 'SOLUCAO'], 'XPE': ['XPE', 'XAROPE', 'XARO'], 'SUSP': ['SUSP', 'SUS', 'SUSPENSAO'],
    'GTS': ['GTS', 'GOTAS', 'GOT', 'GOTA'], 'AMP': ['AMP', 'AMPOLA', 'AMPOLAS'], 'CR': ['CR', 'CRE', 'CREME', 'CREM'],
    'POM': ['POM', 'POMADA', 'POMAD'], 'GEL': ['GEL'], 'SPRAY': ['SPRAY', 'SPR', 'AER', 'AERO', 'AEROSSOL', 'JATO'],
    'LOC': ['LOC', 'LOCAO'], 'SACH': ['SACH', 'SACHE', 'SACHES', 'ENV', 'ENVELOPE', 'ENVELOPES'],
    'PAST': ['PAST', 'PASTILHA', 'PASTILHAS'], 'DRG': ['DRG', 'DR', 'DRAGEA', 'DRAGEAS'],
    'SUPOS': ['SUPOS', 'SUPOSITORIO', 'SUPOSITORIOS', 'SUP'], 'FILME': ['FILME', 'FILMES'], 'PO': ['PO', 'POS'],
    'EMULS': ['EMULS', 'EMULSAO'], 'ADES': ['ADES', 'ADESIVO', 'ADESIVOS'], 'INJ': ['INJ', 'INJETAVEL'],
    'COLIR': ['COLIR', 'COLIRIO'], 'SHAMPOO': ['SHAMPOO', 'SHAMP', 'SH'], 'SAB': ['SAB', 'SABONETE'],
    'DOSE': ['DS', 'DOSE', 'DOSES', 'DO'],
}
FORMA_DE = {v: k for k, vs in FORMAS.items() for v in vs}
CONTAVEIS = {'COMP', 'CAPS', 'AMP', 'SACH', 'PAST', 'DRG', 'SUPOS', 'FILME', 'ADES', 'DOSE'}
FORMAS_PARECIDAS = [{'COMP', 'CAPS', 'DRG', 'FILME'}, {'SOL', 'XPE', 'SUSP', 'GTS', 'EMULS', 'COLIR'},
                    {'SPRAY', 'SOL', 'PO'}]              # creme x pomada x gel NÃO entram: são produtos diferentes

ALIAS = {'HCT': 'HIDROCLOROTIAZIDA', 'HCTZ': 'HIDROCLOROTIAZIDA', 'AMOX': 'AMOXICILINA', 'CLAVU': 'CLAVULANATO',
         'CLAV': 'CLAVULANATO', 'MIC': 'MICONAZOL', 'TRIMET': 'TRIMETAZIDINA', 'PARACET': 'PARACETAMOL',
         'VIT': 'VITAMINA', 'VITAM': 'VITAMINA', 'MAM': 'MAMADEIRA', 'MAMAD': 'MAMADEIRA', 'SAB': 'SABONETE',
         'COND': 'CONDICIONADOR', 'DESOD': 'DESODORANTE', 'PROT': 'PROTETOR', 'PROTET': 'PROTETOR',
         'FISIOL': 'FISIOLOGICA', 'FIS': 'FISIOLOGICA', 'ESPAR': 'ESPARADRAPO', 'ALG': 'ALGODAO', 'LAB': 'LABIAL',
         'HID': 'HIDRATANTE', 'HIDRAT': 'HIDRATANTE', 'FRD': 'FRALDA', 'FD': 'FRALDA', 'AP': 'APARELHO'}
SAIS = {'CLORIDRATO', 'CL', 'CLD', 'CLOR', 'CLORID', 'SODICO', 'SODICA', 'SOD', 'POTASSICO', 'POTASSICA', 'POT', 'CALCICO',
        'CALC', 'MAGNESICO', 'MAG', 'MAGN', 'SULFATO', 'SULF', 'MALEATO', 'MALEAT', 'TARTARATO', 'TART', 'SUCCINATO',
        'SUCC', 'BROMETO', 'FUMARATO', 'ACETATO', 'DIPROPIONATO', 'DIPROP', 'MESILATO', 'NITRATO', 'NITR', 'FOSFATO',
        'BESILATO', 'CITRATO', 'LACTATO', 'VALERATO', 'PROPIONATO', 'BICARBONATO', 'OXALATO', 'DE', 'DO', 'DA', 'DOS', 'DAS',
        'DICLORIDRATO', 'DICLOR', 'DICLORID', 'DICL', 'HICLATO', 'FUROATO', 'MONOH', 'MONOHIDRATO', 'TRIIDRATO',
        'TRIHIDRATO', 'HEMIFUMARATO', 'ADIPATO', 'TOSILATO', 'CLORETO', 'CARBONATO', 'BROMIDRATO', 'ETILSUCCINATO'}
LIBPROL = {'LP', 'LR', 'XR', 'ER', 'SR', 'MR', 'RETARD', 'LIBPROL', 'CD', 'XL', 'OD'}
QUALIF_SIMPLES = {'A', 'D', 'H', 'R', 'B', 'K', 'PLUS', 'FORTE', 'MAX', 'DUO', 'TRI', 'ULTRA', 'GOLD', 'PRO', 'ANLO',
                  'COMPOSTO', 'SELECT', 'FLEX', 'IR', 'BD', 'MULHER', 'HOMEM', 'FEMININO', 'MASCULINO', 'SENIOR', 'JUNIOR',
                  'ESSENCIAL', 'PREMIUM', 'SPORT', 'NIGHT', 'DIA', 'NOITE', 'EXTRA', 'INTENSIVE', 'INTENSO', 'ADULTO',
                  'DIET', 'ZERO', 'LIGHT', 'FAST', 'FLASH', 'UNO', 'TOTAL', 'ATIVO', 'BABY', 'KIDS', 'TEEN'}
INFANTIL = {'INFANTIL', 'PEDIATRICO', 'PED', 'INF', 'PEDIATRICA', 'INFANT', 'CRIANCA'}
DISPERS = {'DISP', 'DISPERS', 'DISPERSIVEL', 'DISPERSAVEL', 'SUBLINGUAL', 'SL', 'ODT', 'MASTIGAVEL', 'EFERV', 'EFERVESCENTE'}
LABS = {'EUR': 'EUROFARMA', 'EURO': 'EUROFARMA', 'EUROFARMA': 'EUROFARMA', 'EUROF': 'EUROFARMA', 'MDL': 'MEDLEY',
        'MDLY': 'MEDLEY', 'MEDLEY': 'MEDLEY', 'MED': 'MEDLEY', 'MEDL': 'MEDLEY', 'EMS': 'EMS', 'GERMED': 'GERMED',
        'GERM': 'GERMED', 'GMD': 'GERMED', 'NEOQ': 'NEOQUIMICA', 'NEOQUIMICA': 'NEOQUIMICA', 'BIO': 'BIOSINTETICA',
        'BIOSINT': 'BIOSINTETICA', 'BIOSINTETICA': 'BIOSINTETICA', 'CIMED': 'CIMED', 'ACHE': 'ACHE', 'SDZ': 'SANDOZ',
        'SANDOZ': 'SANDOZ', 'PRT': 'PRATI', 'PRATI': 'PRATI', 'MERCK': 'MERCK', 'ALT': 'ALTHAIA', 'ALTHAIA': 'ALTHAIA',
        'PHARLAB': 'PHARLAB', 'TEUTO': 'TEUTO', 'BRAINFARMA': 'BRAINFARMA', 'LEGRAND': 'LEGRAND', 'HYPERA': 'HYPERA',
        'MANTECORP': 'MANTECORP', 'BLAU': 'BLAU', 'BIOLAB': 'BIOLAB', 'APSEN': 'APSEN', 'LIBBS': 'LIBBS', 'NOV': 'NOVAFARMA',
        'NOVA': 'NOVAFARMA', 'SAN': 'SANVAL', 'RAN': 'RANBAXY', 'ACCORD': 'ACCORD', 'ZYDUS': 'ZYDUS', 'UNIAO': 'UNIAOQUIMICA',
        'UNIAOQUIMICA': 'UNIAOQUIMICA', 'MULTILAB': 'MULTILAB', 'GEOLAB': 'GEOLAB', 'SUPERA': 'SUPERA', 'VITAMEDIC': 'VITAMEDIC',
        'MYLAN': 'MYLAN', 'TEVA': 'TEVA', 'SANOFI': 'SANOFI', 'PFIZER': 'PFIZER', 'BAYER': 'BAYER', 'NOVARTIS': 'NOVARTIS'}
VARIANTES = {'ROSA', 'AZUL', 'VERDE', 'AMARELO', 'VERMELHO', 'PRETO', 'BRANCO', 'LILAS', 'LARANJA', 'LIMAO', 'MORANGO', 'UVA',
             'MENTA', 'MENTOL', 'BAUNILHA', 'CHOCOLATE', 'TUTTI', 'MACA', 'GUARANA', 'ABACAXI', 'MARACUJA', 'COCO', 'CEREJA',
             'FRAMBOESA', 'PESSEGO', 'BANANA', 'MELANCIA', 'NEUTRO', 'CINZA', 'BEGE', 'CASTANHO', 'LOIRO', 'G', 'GG', 'XG',
             'XXG', 'M', 'RN', 'N1', 'N2', 'N3', 'T1', 'T2', 'T3', 'LENTO', 'MEDIO', 'RAPIDO', 'NATURAL', 'ORIGINAL'}
TAGS = ['DEMAIS PROD', 'OUTROS', 'GENERICO', 'SIMILAR', 'REFERENCIA', 'NAO INCLUIDO', 'NAO INCL', 'NOVO']
STOP = {'E', 'C', 'COM', 'CX', 'FR', 'FRS', 'FRASCO', 'FRASC', 'FRAS', 'FRC', 'FRAC', 'FLAC', 'FLACONETE', 'FLACONETES', 'UN', 'UND', 'UNID', 'SN', 'SC', 'PCT', 'PT', 'CAIXA', 'BL', 'BLISTER',
        'X', 'O', 'PARA', 'POR', 'EM', 'SEM', 'TAMPA', 'EMB', 'ORAL', 'OR', 'USO', 'TOPICO', 'NASAL', 'REV', 'REVEST',
        'REVESTIDO', 'REVESTIDOS', 'SIM', 'MG', 'ML', 'LT', 'LATA', 'MCG', 'UG', 'GEN', 'PRINC', 'ND', 'DSP', 'PET', 'VD', 'VG', 'POTE',
        'TB', 'BG', 'BISN', 'BIS', 'AMB', 'ESTOJO', 'DISPLAY', 'DOSE', 'COMPLETO', 'NOVA', 'EMBALAGEM', 'KIT', 'APLIC',
        'APLICADOR', 'COPO', 'MEDID', 'CART', 'PLACEBO', 'PLACEBOS', 'CADA', 'UNIT', 'UNITARIA', 'CARTELA', 'CARTELAS',
        'SB', 'UNIV', 'LIB', 'PROL', 'RET', 'FILM', 'ENVOL', 'VAG', 'DEMAIS', 'PROD', 'DIL', 'DILUENTE', 'SER', 'SERINGA',
        'PREENC', 'SIST', 'SEG', 'INODORO', 'S', 'CH', 'INODORA', 'REAGENTE', 'PRODUTO', 'ARTIGO', 'SUPER', 'MEGA'}
# palavras que, depois de um número, indicam quantidade de unidades na embalagem ("12UN", "60 FLAC", "7 BISN")
UNIDADES = {'UN', 'UND', 'UNID', 'UNIDADES', 'U', 'FLAC', 'FLACON', 'FLACONETE', 'FLACONETES', 'FRASCO', 'FRASCOS', 'FRC',
            'BISN', 'BISNAGA', 'BISNAGAS', 'TUBO', 'TUBOS', 'POTE', 'POTES', 'PC', 'PCS', 'SER', 'SERINGA', 'SERINGAS'}
STOP |= {'UNIDADES', 'U', 'TUBO', 'TUBOS', 'BISNAGA', 'BISNAGAS', 'POTES', 'PC', 'PCS', 'FLACON', 'FRASCOS', 'SERINGAS'}
CONTROLE = re.compile(r'^[ABCD][1-5]$|^[ABCD][1-5][A-Z]{0,2}$')
_NUM = r'\d+(?:\.\d+)?'
_UN = r'(?:MG|MCG|UG|GRS|GR|G|KG|UI|MEQ|ML|L|CM|MM|MT|M|%)'
_CADEIA = re.compile(rf'({_NUM})\s*({_UN})?(?:\s*[+/]\s*({_NUM})\s*({_UN})?)*(?![A-Z0-9])(?:\s*/\s*(ML|G|GR|L|DOSE))?')
_ELEM = re.compile(rf'({_NUM})\s*({_UN})?')
_CONC_REF = re.compile(rf'({_NUM})\s*(MG|MCG|UG|G)\s*/\s*({_NUM})\s*ML\b')


def _sem_acento(s: str) -> str:
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()


def normalizar(desc: str) -> Tuple[str, Optional[str]]:
    s = str(desc or '')
    for _ in range(2):
        s = html.unescape(s)                                 # notas trazem '&amp;amp;'
    s = _sem_acento(s).upper()
    cat = None
    if re.search(r'\s/\s*GEN\b', s):                         # "+ ATENOLOL 25MG 30 CPS / GEN ATENOLOL ..." = genérico
        cat = 'GENERICO'
    s = re.sub(r'\s*/\s*GEN\b.*$', '', s)
    for t in TAGS:
        m = re.search(r'(?:^|[-\s])' + t + r'\b', s)
        if m:
            if t in ('GENERICO', 'SIMILAR', 'REFERENCIA'):
                cat = t
            s = s[:m.start()] + ' ' + s[m.end():]
    if re.search(r'\(G\)|\bGEN\b', s):
        cat = cat or 'GENERICO'
    s = re.sub(r'\(G\)', ' ', s)
    s = re.sub(r'\bLIB(?:ERACAO)?\.?\s*(?:PROL|RET|CONTR)\w*', ' LIBPROL ', s)
    s = re.sub(r'\bDE\s+LIBERACAO\s+\w+', ' LIBPROL ', s)
    s = re.sub(r'^[\s\-\+\*\.]+', '', s)
    s = s.replace('&', ' ')
    s = re.sub(r'(\d),(\d)', r'\1.\2', s)                    # 4,8 -> 4.8
    s = re.sub(r'(\d)\.(\d{3})(?!\d)', r'\1\2', s)           # 5.000 -> 5000
    s = re.sub(r'(\d)([A-Z])', r'\1 \2', s)                  # 20MG30CP -> 20 MG 30 CP
    s = re.sub(r'\b([A-Z]{2,})(\d)', r'\1 \2', s)            # PRINC2 -> PRINC 2 (mantém C1, A2, N2, T2)
    s = re.sub(r'[^A-Z0-9.+/%\s]', ' ', s)
    s = re.sub(r'(?<![0-9])\.|\.(?![0-9])', ' ', s)          # pontos soltos (CAPS. -> CAPS)
    return re.sub(r'\s+', ' ', s).strip(), cat


def _canon(v: float, un: Optional[str]) -> Optional[Tuple[str, float]]:
    un = (un or '').upper()
    if un == 'MG': return 'MASSA', v
    if un in ('MCG', 'UG'): return 'MASSA', v / 1000
    if un in ('G', 'GR', 'GRS'): return 'MASSA', v * 1000
    if un == 'KG': return 'MASSA', v * 1e6
    if un == 'ML': return 'VOL', v
    if un == 'L': return 'VOL', v * 1000
    if un == 'UI': return 'UI', v
    if un == 'MEQ': return 'MEQ', v
    if un == '%': return 'PERC', v
    if un == 'CM': return 'COMP', v
    if un == 'MM': return 'COMP', v / 10
    if un in ('M', 'MT'): return 'COMP', v * 100
    return None


@dataclass
class Atributos:
    original: str
    texto: str = ''
    categoria: Optional[str] = None
    medidas: Dict[str, List[float]] = field(default_factory=dict)
    conc: List[Tuple[float, str]] = field(default_factory=list)
    qtd: Optional[int] = None
    formas: set = field(default_factory=set)
    lab: Optional[str] = None
    lab_txt: Optional[str] = None
    variantes: set = field(default_factory=set)
    qualif: set = field(default_factory=set)
    controle: Optional[str] = None
    codigos: set = field(default_factory=set)
    numeros: set = field(default_factory=set)           # estágio/modelo solto: NAN 1 x NAN 2, MACH 3
    nome: List[str] = field(default_factory=list)


def _medidas(a: Atributos, resto: str) -> str:
    def tira(m):
        den = m.group(5)
        elems = _ELEM.findall(re.sub(r'\s*/\s*(ML|G|GR|L|DOSE)\s*$', '', m.group(0)))
        vals = [[float(n), u or None] for n, u in elems]
        if not any(u for _, u in vals):
            return m.group(0)                                  # cadeia de números sem unidade: não é medida
        prox = None
        for x in reversed(vals):                               # unidade ausente herda a da direita (5000MCG+100+100MG)
            if x[1]:
                prox = x[1]
            else:
                x[1] = prox
        for n, u in vals:
            if u is None:
                continue
            if den and u in ('MG', 'MCG', 'UG', 'G', 'GR') and den in ('ML', 'G', 'GR', 'L'):
                a.conc.append((round(_canon(n, u)[1], 4), 'G' if den == 'GR' else den))
            else:
                c = _canon(n, u)
                if c:
                    a.medidas.setdefault(c[0], []).append(round(c[1], 4))
        return ' '
    return _CADEIA.sub(tira, resto)


_PACK_PATS = (r'\b\d+\s*BL[A-Z]*\s*X?\s*\d+\b', r'\b\d+\s*X\s*\d+\b', r'\bC\s*/\s*\d+\b', r'\bC\s+\d+\b', r'\bCX\s*\d+\b',
              r'\bPCT\s*\d+\b', r'\bX\s*\d+(?![\d.])', r'\bCOM\s+\d+\b', r'\b\d+\s*\+\s*0?\d+\b')


def extrair(desc: str) -> Atributos:
    texto, cat = normalizar(desc)
    a = Atributos(original=str(desc or ''), texto=texto, categoria=cat)

    def conc_ref(m):                                           # 40MG/5ML -> 8 mg/ml
        c = _canon(float(m.group(1)), m.group(2))
        a.conc.append((round(c[1] / float(m.group(3)), 4), 'ML'))
        return ' '
    texto = _CONC_REF.sub(conc_ref, texto)
    resto = _medidas(a, texto).replace('+', ' + ')
    for t in a.medidas:
        a.medidas[t].sort()
    a.conc.sort()
    # embalagem: n BL X m; n X m; C/n (nunca C1/A2); CX n; PCT n; X n; n FORMA; "+n placebos" soma
    q = None
    m = re.search(r'\b(\d+)\s*\+\s*0?(\d+)\s*(?:COMP|CPR|CP|CPS|CAPS|CPRS|PLACEBO)', resto)       # 24+4 = 28
    if m and int(m.group(1)) <= 200 and int(m.group(2)) <= 50:
        q = int(m.group(1)) + int(m.group(2))
    if q is None:
        m = re.search(r'\b(\d+)\s*BL[A-Z]*\s*X?\s*(\d+)(?![\d.])', resto) or re.search(r'\b(\d+)\s*X\s*(\d+)(?![\d.])', resto)
        if m:
            q = int(m.group(1)) * int(m.group(2))
    if q is None:
        for pat in (r'\bC\s*/\s*(\d+)\b', r'\bC\s+(\d+)\b', r'\bCX\s*(\d+)\b', r'\bPCT\s*(\d+)\b', r'\bX\s*(\d+)(?![\d.])', r'\bCOM\s+(\d+)\b'):
            m = re.search(pat, resto)
            if m:
                q = int(m.group(1))
                break
    toks0 = resto.split()
    if q is None:                                               # "30 COMP" ou "COMP 30"; dose sem unidade (5000) não é embalagem
        cands = []
        for i, t in enumerate(toks0):
            if t.isdigit() and i + 1 < len(toks0) and (FORMA_DE.get(toks0[i + 1]) in CONTAVEIS or toks0[i + 1] == 'COM'
                                                      or toks0[i + 1] in UNIDADES):
                cands.append(int(t))                            # "120 COM REV": COM = comprimidos quando vem após o número
            if FORMA_DE.get(t) in CONTAVEIS and i + 1 < len(toks0) and toks0[i + 1].isdigit():
                cands.append(int(toks0[i + 1]))
        razoaveis = [c for c in cands if c <= 500]
        q = (razoaveis or cands or [None])[-1] if len(razoaveis) <= 1 else razoaveis[-1]
    elif q is not None:
        mpb = re.search(r'\+\s*(\d+)\s*PLACEBOS?', resto)
        if mpb:
            q += int(mpb.group(1))
    a.qtd = q
    for pat in _PACK_PATS:
        resto = re.sub(pat, ' ', resto)
    resto = re.sub(r'\bC\s*/\s*', ' ', resto)                  # "C/ALGINATO" = com alginato
    toks = resto.replace('+', ' ').split()
    ult_qtd_idx = -1
    for i, t in enumerate(toks):
        if t.isdigit() and FORMA_DE.get(toks[i + 1] if i + 1 < len(toks) else '') in CONTAVEIS:
            ult_qtd_idx = i
    nome: List[str] = []
    for i, t in enumerate(toks):
        if re.fullmatch(r'[\d.+/%]+', t):
            if t.isdigit() and len(t) >= 4:
                a.codigos.add(t)                               # número de modelo solto (7122)
            elif t.isdigit() and len(t) <= 3 and t != str(q):        # o número da embalagem não é estágio/modelo
                a.numeros.add(t)
            continue
        if CONTROLE.match(t):
            a.controle = t
            continue
        if re.fullmatch(r'[A-Z]*\d+[A-Z\d]*', t) and len(t) >= 4 and any(c.isalpha() for c in t):
            a.codigos.add(t)
            continue
        f = FORMA_DE.get(t)
        if f:
            a.formas.add(f)
            continue
        if t in LIBPROL:
            a.qualif.add('LIBPROL'); continue
        if t in INFANTIL:
            a.qualif.add('INFANTIL'); continue
        if t in DISPERS:
            a.qualif.add('DISPERSIVEL'); continue
        if t in SAIS or t in STOP:
            continue
        if t in VARIANTES:
            a.variantes.add(t); continue
        if len(t) >= 4:
            v = next((v for v in VARIANTES if len(v) > 4 and v.startswith(t)), None)
            if v:
                a.variantes.add(v); continue
        if nome and t in QUALIF_SIMPLES:
            a.qualif.add(t); continue
        lab = LABS.get(t)
        final = (ult_qtd_idx >= 0 and i > ult_qtd_idx) or i >= len(toks) - 2
        if lab and nome and (final or i > 1):
            a.lab = lab; continue
        if nome and final and re.fullmatch(r'[A-Z]{2,5}', t) and t not in ALIAS and ult_qtd_idx >= 0 and i > ult_qtd_idx:
            a.lab_txt = t; continue
        nome.append(ALIAS.get(t, t))
    a.nome = nome
    return a


# ------------------------------------------------------------------ comparação
def _lev1(x: str, y: str) -> bool:
    """distância de edição <= 1 (typos: COLIDS/COLIDIS, EPHINAL/EPHYNAL)."""
    if abs(len(x) - len(y)) > 1 or x == y:
        return x == y
    if len(x) == len(y):
        return sum(1 for p, q in zip(x, y) if p != q) <= 1
    c, l = (x, y) if len(x) < len(y) else (y, x)
    i = j = diff = 0
    while i < len(c) and j < len(l):
        if c[i] == l[j]:
            i += 1; j += 1
        else:
            diff += 1; j += 1
            if diff > 1:
                return False
    return True


def _igual(x: str, y: str) -> bool:
    if x == y:
        return True
    c, l = (x, y) if len(x) <= len(y) else (y, x)
    if len(c) >= 4 and l.startswith(c):                        # abreviação: OLMESART ~ OLMESARTANA
        return True
    return len(c) >= 5 and _lev1(x, y)


def _fundir(a: List[str], b: List[str]) -> List[str]:
    """Une tokens adjacentes de `a` que juntos formam um token de `b` (ONE TOUCH ~ ONETOUCH, DFER ~ D FER)."""
    out, i = [], 0
    while i < len(a):
        if i + 1 < len(a) and any(len(a[i] + a[i + 1]) >= 6 and (a[i] + a[i + 1] == u or _lev1(a[i] + a[i + 1], u)) for u in b):
            out.append(a[i] + a[i + 1]); i += 2
        else:
            out.append(a[i]); i += 1
    return out


def _extras(a: List[str], b: List[str]) -> List[str]:
    return [t for t in a if not any(_igual(t, u) for u in b)]


@dataclass
class Resultado:
    nivel: Optional[str]
    pontos: float
    motivos: List[str]
    contradicoes: List[str]                                    # duras
    suaves: List[str] = field(default_factory=list)
    generico_sem_lab: bool = False


def _potencia_de_10(x: float, y: float) -> bool:
    """x/y é 10^k (k != 0): mesma dose com unidade trocada (125 mg x 125 mcg = 125 x 0,125)."""
    if x <= 0 or y <= 0:
        return False
    k = math.log10(x / y)
    return round(k) != 0 and abs(k - round(k)) < 1e-6


def _medidas_compat(e: Atributos, n: Atributos, duras: List[str], suaves: List[str]) -> Tuple[bool, bool]:
    """(há medida comparável, todas as comparáveis concordam)."""
    comparou, ok = False, True
    e_m, n_m = dict(e.medidas), dict(n.medidas)
    if 'MASSA' in e_m and 'VOL' in n_m and 'MASSA' not in n_m and 'VOL' not in e_m:     # 450G x 450ML
        e_m['VOL'] = [v / 1000 for v in e_m.pop('MASSA')]
    if 'VOL' in e_m and 'MASSA' in n_m and 'VOL' not in n_m and 'MASSA' not in e_m:
        n_m['VOL'] = [v / 1000 for v in n_m.pop('MASSA')]
    for tipo in set(e_m) & set(n_m):
        comparou = True
        ve, vn = sorted(e_m[tipo]), sorted(n_m[tipo])
        if ve == vn:
            continue
        if tipo == 'MASSA' and abs(sum(ve) - sum(vn)) < 1e-6:
            suaves.append(f'dose somada {ve} x {vn}')           # 900+100 = 1000: plausível, mas pede conferência
            ok = False
            continue
        if set(ve) <= set(vn) or set(vn) <= set(ve):
            suaves.append(f'{tipo.lower()} com item extra {ve} x {vn}')
            ok = False
            continue
        if tipo == 'MASSA' and len(ve) == len(vn) and all(_potencia_de_10(x, y) for x, y in zip(ve, vn)):
            suaves.append(f'unidade provavelmente trocada (mg x mcg) {ve} x {vn}')      # 125MG x 125MCG, 4MG x 0,4MG
            ok = False
            continue
        ok = False
        duras.append(f'{tipo.lower()} {ve} x {vn}')
    if e.conc and n.conc:
        comparou = True
        if len(e.conc) != len(n.conc) or any(abs(x[0] - y[0]) > 1e-3 * max(1, x[0]) for x, y in zip(e.conc, n.conc)):
            ok = False
            duras.append(f'concentração {e.conc} x {n.conc}')
    return comparou, ok


def comparar(e: Atributos, n: Atributos, ncm_e: str = '', ncm_n: str = '') -> Resultado:
    motivos, duras, suaves = [], [], []
    pts = 0.0
    ne, nn = re.sub(r'\D', '', ncm_e), re.sub(r'\D', '', ncm_n)
    ncm_exato = False
    if ne and nn:
        if ne == nn:
            pts += 2; motivos.append('NCM igual'); ncm_exato = True
        elif ne[:6] == nn[:6]:
            pts += 1.5; motivos.append('NCM 6 díg.')
        elif ne[:4] == nn[:4]:
            pts += 1; motivos.append('NCM 4 díg.')
        elif ne[:2] == nn[:2]:
            pts += 0.3; motivos.append('NCM só capítulo')
        else:
            suaves.append('NCM de outro capítulo')
    cod_comum = bool({c.lstrip('0') for c in e.codigos} & {c.lstrip('0') for c in n.codigos})
    en, nn_ = _fundir(e.nome, n.nome), _fundir(n.nome, e.nome)
    ext_e, ext_n = _extras(en, nn_), _extras(nn_, en)
    longos = [t for t in en if len(t) >= 4]
    prim = bool(en and nn_) and (_igual(en[0], nn_[0]) or any(any(_igual(t, u) for u in nn_) for t in longos))
    nome_ok, falta_max = False, 1.0
    if not en or not nn_:
        if not cod_comum:
            duras.append('sem nome comparável')
    elif not prim and not cod_comum:
        duras.append('produto diferente')
    elif ext_e and ext_n and not cod_comum:
        duras.append(f'nome difere {ext_e} x {ext_n}')
    else:
        tot_e = sum(len(t) for t in en) or 1
        tot_n = sum(len(t) for t in nn_) or 1
        falta_max = max(sum(len(t) for t in ext_e) / tot_e, sum(len(t) for t in ext_n) / tot_n)
        nome_ok = falta_max <= 0.35 or cod_comum
        extra_unico = [t for t in (ext_e + ext_n) if len(t) >= 4]
        if extra_unico and not cod_comum:
            suaves.append(f'palavra extra só de um lado {extra_unico}')          # OPTIVE x OPTIVE ADVANCE
        pts += (3 if falta_max == 0 else 2.5) if nome_ok else 1
        motivos.append('nome igual' if falta_max == 0 else ('nome (abreviado)' if nome_ok else 'nome parcial'))
    if cod_comum:
        pts += 1.5; motivos.append('código de modelo')
    # qualificadores: ambos preenchidos e diferentes = produto diferente; só de um lado = suave
    if e.qualif != n.qualif:
        if e.qualif and n.qualif and not (e.qualif <= n.qualif or n.qualif <= e.qualif):
            duras.append(f'qualificador {sorted(e.qualif)} x {sorted(n.qualif)}')
        elif not cod_comum:
            suaves.append(f'qualificador só de um lado {sorted(e.qualif ^ n.qualif)}')
    if e.numeros and n.numeros and e.numeros != n.numeros and not cod_comum:
        duras.append(f'número {sorted(e.numeros)} x {sorted(n.numeros)}')       # estágio/modelo diferente
    comparou, ok = _medidas_compat(e, n, duras, suaves)
    if comparou and ok:
        pts += 3; motivos.append('medidas iguais')
    qtd_ok = False
    if e.qtd is not None and n.qtd is not None:
        if e.qtd == n.qtd:
            pts += 2; qtd_ok = True; motivos.append(f'embalagem {e.qtd}')
        else:
            duras.append(f'embalagem {e.qtd} x {n.qtd}')
    if e.controle and n.controle and e.controle != n.controle:
        suaves.append(f'controle {e.controle} x {n.controle}')        # rótulo de controle varia entre cadastros
    lab_ok = False
    le, ln = e.lab or e.lab_txt, n.lab or n.lab_txt
    if le and ln:
        if le == ln or {le, ln} <= {'BIOLAB', 'BIOSINTETICA'}:
            pts += 1.5; lab_ok = True; motivos.append('laboratório igual')
        elif e.lab and n.lab:
            duras.append(f'laboratório {le} x {ln}')                   # dois laboratórios conhecidos e diferentes
        else:
            suaves.append(f'laboratório incerto {le} x {ln}')          # sigla desconhecida (subsidiárias: EURO x ACT)
    elif (le or ln) and 'REFERENCIA' not in (e.categoria, n.categoria) and 'SIMILAR' not in (e.categoria, n.categoria):
        suaves.append('laboratório só de um lado')                 # sem marca, vários laboratórios = vários EANs
    if e.categoria and n.categoria and e.categoria != n.categoria:
        duras.append(f'categoria {e.categoria} x {n.categoria}')
    if e.variantes and n.variantes and not (e.variantes & n.variantes):
        duras.append(f'variante {sorted(e.variantes)} x {sorted(n.variantes)}')
    if e.formas and n.formas and not (e.formas & n.formas):
        if any((e.formas & g) and (n.formas & g) for g in FORMAS_PARECIDAS):
            suaves.append(f'forma parecida {sorted(e.formas)} x {sorted(n.formas)}')   # fornecedor troca CAPS/COMP
        else:
            duras.append(f'forma {sorted(e.formas)} x {sorted(n.formas)}')
    elif e.formas & n.formas:
        pts += 0.5
    if duras:
        return Resultado(None, pts, motivos, duras, suaves)
    generico = n.categoria == 'GENERICO' or e.categoria == 'GENERICO'
    gen_sem_lab = generico and not lab_ok
    # evidência por atributo: concordância vale 1; ausência nos DOIS lados é neutra (0,5), pois não há o que contradizer
    sem_medidas = not (e.medidas or e.conc or n.medidas or n.conc)
    sem_qtd = e.qtd is None and n.qtd is None
    medida_ok = comparou and ok
    score = int(medida_ok) + int(qtd_ok) + 0.5 * int(sem_medidas) + 0.5 * int(sem_qtd) + int(lab_ok)
    compat = (medida_ok or sem_medidas or not comparou) and (qtd_ok or sem_qtd or e.qtd is None or n.qtd is None)
    estoque_sem_atributos = e.qtd is None and not e.medidas and not e.conc
    if nome_ok and falta_max == 0 and ncm_exato and not suaves and not gen_sem_lab and compat and score >= 1.5:
        nivel = 'A'
    elif nome_ok and ne[:6] == nn[:6] and not suaves and not gen_sem_lab and compat and score >= 1.0:
        nivel = 'B'
    elif (nome_ok or cod_comum) and (score >= 0.5 or (estoque_sem_atributos and ne[:6] == nn[:6] and falta_max <= 0.15)):
        nivel = 'C'
    else:
        nivel = None
    return Resultado(nivel, pts, motivos, duras, suaves, gen_sem_lab)


# ------------------------------------------------------------------ busca em universo de produtos da nota
class Indice:
    """Universo de produtos das NF-e (chave = EAN ou pseudo-chave) com índice invertido por prefixo de token."""

    def __init__(self):
        self.prod: Dict[str, dict] = {}
        self.inv: Dict[str, set] = {}

    def adicionar(self, chave: str, descricoes: List[str], ncm: str):
        attrs = [extrair(x) for x in descricoes]
        self.prod[chave] = dict(descs=descricoes, ncm=ncm, attrs=attrs)
        for a in attrs:
            for t in a.nome[:4]:
                self.inv.setdefault(t[:3], set()).add(chave)
            for c in a.codigos:
                self.inv.setdefault('#' + c.lstrip('0'), set()).add(chave)

    def candidatos(self, e: Atributos):
        out = set()
        for t in e.nome[:4]:
            out |= self.inv.get(t[:3], set())
        for c in e.codigos:
            out |= self.inv.get('#' + c.lstrip('0'), set())
        return out

    def buscar(self, desc: str, ncm: str, excluir=None, max_res: int = 6):
        """Lista ordenada de (pontos, nivel, chave, Resultado, descricao_da_nota). `excluir`: chave ou conjunto de chaves."""
        e = extrair(desc)
        excl = {excluir} if isinstance(excluir, str) else set(excluir or ())
        res = []
        for z in sorted(self.candidatos(e)):                     # ordem fixa: resultado reproduzível entre execuções
            if z in excl:
                continue
            p = self.prod[z]
            melhor = None
            for d_, na in zip(p['descs'], p['attrs']):
                r = comparar(e, na, ncm, p['ncm'])
                if r.nivel and (melhor is None or r.pontos > melhor[0].pontos):
                    melhor = (r, d_)
            if melhor:
                res.append((melhor[0].pontos, melhor[0].nivel, z, melhor[0], melhor[1]))
        res.sort(key=lambda x: (-x[0], x[2]))                   # desempate por chave: determinístico
        return res[:max_res]


def desempatar_por_preco(candidatos: List[str], custo: float, preco: Dict[str, float],
                         faixa: float = 2.0, folga: float = 0.15) -> Optional[str]:
    """Entre produtos empatados na descrição, escolhe o de preço unitário de compra mais próximo do custo do estoque.

    Só decide se o vencedor estiver dentro de `faixa` (x/÷) do custo e à frente do segundo por `folga` (em log)."""
    import math
    pontos = sorted((abs(math.log(preco[z] / custo)), z) for z in candidatos if preco.get(z, 0) > 0 and custo > 0)
    if not pontos or pontos[0][0] > math.log(faixa):
        return None
    if len(pontos) == 1 or pontos[1][0] - pontos[0][0] >= folga:
        return pontos[0][1]
    return None


def decidir(resultados) -> dict:
    """Unicidade: empate entre produtos diferentes no topo rebaixa A/B para 'C' (ambíguo, precisa de desempate)."""
    if not resultados:
        return dict(nivel=None, chave=None, ambiguo=False, candidatos=[])
    top = resultados[0]
    empatados = [r for r in resultados if r[0] >= top[0] - 0.5]
    empate = len({r[2] for r in empatados}) > 1
    nivel = 'C' if empate and top[1] in ('A', 'B') else top[1]
    return dict(nivel=nivel, chave=top[2], ambiguo=empate, pontos=top[0], motivos=top[3].motivos, suaves=top[3].suaves,
                desc_nota=top[4], generico_sem_lab=top[3].generico_sem_lab, candidatos=[r[2] for r in empatados])
