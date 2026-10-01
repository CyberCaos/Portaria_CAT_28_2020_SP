"""Leitura tolerante de XML fiscal. Porte de RelatorioFiscalXml/Parsing/XmlHelpers.cs (+ regras de DetectorXml.cs).

Problemas reais de lotes de NF-e que este módulo absorve (mesmos tratados no projeto original):
- '&' e '<' literais dentro de texto de produto (ex.: xProd = "P & G", "NEO < 700GR"), que quebram o parser padrão;
- bytes de encoding corrompidos no meio do arquivo;
- dhEmi com offset de fuso: o horário deve ficar como escrito no documento (sem converter para o fuso da máquina).
"""
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator, Optional

# '&' que não inicia entidade válida; '<' que não inicia tag real (tag nunca começa com espaço/dígito/pontuação).
_E_AMP_SOLTO = re.compile(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9A-Fa-f]+;)')
_MENOR_SOLTO = re.compile(r'<(?![a-zA-Z/!?])')
_DECL = re.compile(r'^\s*<\?xml[^>]*\?>', re.I)
_ENC = re.compile(r'encoding\s*=\s*["\']([\w\-]+)["\']', re.I)
_CTRL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def sanitizar_xml_bruto(xml: str) -> str:
    xml = _E_AMP_SOLTO.sub('&amp;', xml)
    return _MENOR_SOLTO.sub('&lt;', xml)


def decodificar(dados: bytes) -> str:
    """bytes -> str respeitando BOM e a declaração de encoding; bytes inválidos viram U+FFFD (não derrubam o arquivo)."""
    if dados.startswith(b'\xef\xbb\xbf'):
        return dados[3:].decode('utf-8', errors='replace')
    if dados.startswith((b'\xff\xfe', b'\xfe\xff')):
        return dados.decode('utf-16', errors='replace')
    cab = dados[:200].decode('ascii', errors='ignore')
    m = _ENC.search(cab)
    codec = (m.group(1) if m else 'utf-8').lower()
    try:
        return dados.decode(codec, errors='replace')
    except LookupError:
        return dados.decode('utf-8', errors='replace')


def carregar_sanitizado(caminho: str) -> ET.Element:
    with open(caminho, 'rb') as f:
        texto = decodificar(f.read())
    texto = _DECL.sub('', texto, count=1)
    texto = _CTRL.sub('', texto)
    return ET.fromstring(sanitizar_xml_bruto(texto))


def local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


def child(parent: Optional[ET.Element], nome: str) -> Optional[ET.Element]:
    if parent is None:
        return None
    return next((e for e in parent if local(e.tag) == nome), None)


def children(parent: Optional[ET.Element], nome: str) -> Iterator[ET.Element]:
    if parent is None:
        return iter(())
    return (e for e in parent if local(e.tag) == nome)


def descendant(parent: Optional[ET.Element], nome: str) -> Optional[ET.Element]:
    if parent is None:
        return None
    return next((e for e in parent.iter() if e is not parent and local(e.tag) == nome), None)


def el(parent: Optional[ET.Element], nome: str) -> Optional[str]:
    """Texto do filho direto `nome` (None se não existe)."""
    c = child(parent, nome)
    return None if c is None else (c.text or '')


def uf(parent: Optional[ET.Element]) -> Optional[str]:
    """<UF> em qualquer profundidade (o wrapper do endereço muda por participante: enderEmit, enderDest...)."""
    d = descendant(parent, 'UF')
    return None if d is None else (d.text or '')


def parse_dec(valor: Optional[str]) -> Decimal:
    if valor is None or not valor.strip():
        return Decimal(0)
    try:
        return Decimal(valor.strip())
    except InvalidOperation:
        return Decimal(0)


def parse_data(valor: Optional[str]) -> Optional[datetime]:
    """Horário como escrito no documento (descarta o offset de fuso)."""
    if valor is None or not valor.strip():
        return None
    v = valor.strip()
    try:
        return datetime.fromisoformat(v).replace(tzinfo=None)
    except ValueError:
        pass
    try:
        return datetime.strptime(v[:8], '%Y%m%d')
    except ValueError:
        return None


def detectar(root: ET.Element):
    """(nome local do elemento raiz, modelo <mod>)."""
    mod = descendant(root, 'mod')
    return local(root.tag), (mod.text.strip() if mod is not None and mod.text else None)
