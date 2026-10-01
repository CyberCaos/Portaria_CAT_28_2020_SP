"""Confere (e, com --instalar, instala) as dependências da skill.

    python scripts/verificar_ambiente.py             só confere e diz o que falta
    python scripts/verificar_ambiente.py --instalar  instala o que falta com pip (requirements.txt)
"""
import importlib
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBRIGATORIAS = [('pandas', 'pandas'), ('openpyxl', 'openpyxl'), ('xlrd', 'xlrd'), ('reportlab', 'reportlab')]
OPCIONAIS = [('fitz', 'pymupdf', 'conferência visual do PDF e testes do relatório'), ('pytest', 'pytest', 'testes')]


def faltando(lista):
    out = []
    for item in lista:
        try:
            importlib.import_module(item[0])
        except ImportError:
            out.append(item)
    return out


def main(argv):
    if sys.version_info < (3, 10):
        sys.exit(f'Python 3.10 ou superior é necessário (encontrado {sys.version.split()[0]}).')
    falta = faltando(OBRIGATORIAS)
    opc = faltando(OPCIONAIS)
    if '--instalar' in argv and (falta or opc):
        req = os.path.join(RAIZ, 'requirements.txt')
        print('Instalando dependências de', req)
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', req])
        falta, opc = faltando(OBRIGATORIAS), faltando(OPCIONAIS)
    for _, pacote in falta:
        print(f'FALTA (obrigatório): {pacote}')
    for _, pacote, uso in opc:
        print(f'falta (opcional): {pacote} - {uso}')
    if falta:
        print('Rode: python scripts/verificar_ambiente.py --instalar   (ou pip install -r requirements.txt)')
        sys.exit(1)
    print(f'Ambiente OK (Python {sys.version.split()[0]}).')


if __name__ == '__main__':
    main(sys.argv[1:])
