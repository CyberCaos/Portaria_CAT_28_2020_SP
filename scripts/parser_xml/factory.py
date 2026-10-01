"""Processamento de arquivos e lotes de XML. Porte de ParserFactory.cs + AplicadorEventosCancelamento.cs.

Só NF-e/NFC-e interessam ao levantamento (compras). CF-e-SAT e CT-e do projeto original não foram portados:
não carregam ICMS-ST retido de mercadoria adquirida para revenda no formato usado aqui.
"""
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from . import nfe, xmlhelpers as X
from .modelos import EventoCancelamento, ItemFiscal, ResultadoArquivo


def processar_arquivo(caminho: str) -> ResultadoArquivo:
    nome = os.path.basename(caminho)
    try:
        root = X.carregar_sanitizado(caminho)
        raiz, modelo = X.detectar(root)
        if nfe.suporta(raiz, modelo):
            return ResultadoArquivo(caminho, nome, itens=nfe.parse(root, nome))
        if raiz == 'procEventoNFe':
            ev = nfe.extrair_evento_cancelamento(root, nome)
            if ev is not None:
                return ResultadoArquivo(caminho, nome, evento=ev)
            return ResultadoArquivo(caminho, nome, erro='Evento de NF-e que não é cancelamento (tpEvento != 110111): '
                                                        'tipo de evento não suportado.')
        if raiz == 'resNFe':
            return ResultadoArquivo(caminho, nome, aviso='resNFe (resumo de NF-e, sem detalhe de produto/imposto): '
                                                         'ignorado; baixar o XML completo da nota.')
        return ResultadoArquivo(caminho, nome, erro=f'Tipo de documento não suportado (root={raiz}, mod={modelo})')
    except Exception as ex:  # um arquivo ruim não derruba o lote
        return ResultadoArquivo(caminho, nome, erro=f'{type(ex).__name__}: {ex}')


def listar_xml(pasta: str) -> List[str]:
    achados = []
    for dp, _, fs in os.walk(pasta):
        achados += [os.path.join(dp, f) for f in fs if f.lower().endswith('.xml')]
    return sorted(achados)


def extrair_zips(pasta: str, destino: str, profundidade: int = 3) -> List[str]:
    """Extrai .zip encontrados (inclusive aninhados) com proteção contra zip-slip. Devolve as pastas criadas."""
    criadas = []
    for dp, _, fs in os.walk(pasta):
        for f in fs:
            if not f.lower().endswith('.zip'):
                continue
            alvo = os.path.join(destino, f'{len(criadas):04d}_{os.path.splitext(f)[0]}')
            try:
                with zipfile.ZipFile(os.path.join(dp, f)) as z:
                    base = os.path.realpath(alvo)
                    for m in z.infolist():
                        dest = os.path.realpath(os.path.join(alvo, m.filename))
                        if not (dest == base or dest.startswith(base + os.sep)):
                            raise ValueError(f'entrada suspeita no zip: {m.filename}')
                    z.extractall(alvo)
                criadas.append(alvo)
            except Exception as ex:
                print(f'[aviso] zip ignorado {f}: {ex}')
    if criadas and profundidade > 0:
        for c in list(criadas):
            criadas += extrair_zips(c, destino, profundidade - 1)
    return criadas


@dataclass
class LoteParseado:
    itens: List[ItemFiscal] = field(default_factory=list)
    erros: List[ResultadoArquivo] = field(default_factory=list)
    avisos: List[ResultadoArquivo] = field(default_factory=list)
    eventos: List[EventoCancelamento] = field(default_factory=list)
    eventos_orfaos: List[EventoCancelamento] = field(default_factory=list)
    arquivos: int = 0
    notas_duplicadas: int = 0
    notas_canceladas: int = 0


def _score(item: ItemFiscal):
    # duplicata da mesma chave: prefere a versão autorizada (com protocolo) e, depois, a mais completa
    return (item.autorizada, bool(item.c_stat), item.valor_item > 0)


def processar_lote(caminhos: Iterable[str], progresso=None) -> LoteParseado:
    lote = LoteParseado()
    por_chave: Dict[str, List[ItemFiscal]] = {}
    caminhos = list(caminhos)
    for i, cam in enumerate(caminhos, 1):
        r = processar_arquivo(cam)
        lote.arquivos += 1
        if r.erro:
            lote.erros.append(r)
        elif r.aviso:
            lote.avisos.append(r)
        elif r.evento:
            lote.eventos.append(r.evento)
        elif r.itens:
            chave = r.itens[0].chave
            if chave in por_chave:
                lote.notas_duplicadas += 1
                if _score(r.itens[0]) > _score(por_chave[chave][0]):
                    por_chave[chave] = r.itens
            else:
                por_chave[chave] = r.itens
        if progresso and i % 500 == 0:
            progresso(i, len(caminhos))

    itens = [it for grupo in por_chave.values() for it in grupo]
    chaves_canc = {e.ch_nfe for e in lote.eventos}
    resultado = []
    for it in itens:
        if it.chave in chaves_canc:
            it = it.como_cancelada()
        resultado.append(it)
    lote.notas_canceladas = len({it.chave for it in resultado if it.situacao == 'Cancelada'})
    lote.eventos_orfaos = [e for e in lote.eventos if e.ch_nfe not in por_chave]
    lote.itens = resultado
    return lote


def _extrair_zip_seguro(caminho_zip: str, destino: str):
    with zipfile.ZipFile(caminho_zip) as z:
        base = os.path.realpath(destino)
        for m in z.infolist():
            dest = os.path.realpath(os.path.join(destino, m.filename))
            if not (dest == base or dest.startswith(base + os.sep)):
                raise ValueError(f'entrada suspeita no zip: {m.filename}')
        z.extractall(destino)


def preparar_origem(origem: str):
    """origem: pasta ou .zip. Devolve (raizes, limpar): raizes = pastas onde procurar arquivos (a própria pasta,
    mais o conteúdo de .zip encontrados, inclusive aninhados). A pasta do usuário nunca é alterada."""
    temporarios = []
    raiz = origem
    if os.path.isfile(origem) and origem.lower().endswith('.zip'):
        raiz = tempfile.mkdtemp(prefix='cat28_')
        temporarios.append(raiz)
        _extrair_zip_seguro(origem, raiz)
    extra = tempfile.mkdtemp(prefix='cat28_zips_')
    temporarios.append(extra)
    extrair_zips(raiz, extra)
    return [raiz, extra], lambda: [shutil.rmtree(t, ignore_errors=True) for t in temporarios]


def processar_entrada(origem: str, progresso=None) -> LoteParseado:
    """origem: pasta ou .zip com XMLs (em qualquer subpasta; zips aninhados são extraídos)."""
    raizes, limpar = preparar_origem(origem)
    try:
        return processar_lote([c for r in raizes for c in listar_xml(r)], progresso)
    finally:
        limpar()
