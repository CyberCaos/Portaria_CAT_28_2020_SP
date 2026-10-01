"""Monta a pasta de um cliente para o levantamento (regra padrão da skill).

    <saida>/<NOME DO CLIENTE>/
        LEIAME.txt
        cliente.json                    nome, CNPJ, regime (informado ou inferido), origens, contagens
        estoque/                        cópia das posições de estoque recebidas (estoque dd.mm.aaaa.xls...)
        relatorio_parser/               entrada_consolidada.xlsx, compras.csv, estoque.csv, intake_resumo.json
        resultado_levantamento.xlsx     modelo VAZIO (só cabeçalhos) a ser preenchido pela regra do levantamento

Os XMLs originais NÃO são copiados (são grandes e já estão na origem); fica registrado de onde vieram.

Uso:
    python scripts/preparar_cliente.py --cliente "DROGARIA EXEMPLO LTDA" --cnpj 33.333.333/0001-33 \\
        --pacote <zip|pasta com XML + ESTOQUE> --saida <pasta_base> [--regime RPA|SN] [--xml-proprios <pasta>] [--zip]
    (alternativa: --xml <pasta|zip> ... --estoque <arquivo|pasta|zip> ...)

`--xml-proprios`: pasta com notas emitidas PELA empresa, usada só para inferir o regime (CRT da NF-e/NFC-e, cRegTrib do
CF-e-SAT). Se `--regime` não for dado, o regime inferido vale como sugestão e fica marcado como "inferido".
"""
import argparse
import json
import os
import re
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import estoque as E  # noqa: E402
import intake  # noqa: E402
import resultado_modelo as RM  # noqa: E402

_CRT = re.compile(rb'<CRT>(\d)</CRT>')
_REG = re.compile(rb'<cRegTrib>(\d)</cRegTrib>')
_EMIT = re.compile(rb'<emit>.*?<CNPJ>(\d{14})</CNPJ>', re.S)
_DATA = re.compile(rb'<(?:dhEmi|dEmi)>(\d{4})-?(\d{2})')


def nome_pasta(cliente: str) -> str:
    """Nome do cliente como nome de pasta (remove só o que o Windows não aceita)."""
    return re.sub(r'\s+', ' ', re.sub(r'[<>:"/\\|?*]+', ' ', cliente)).strip().rstrip('.')


def _regime_de(crt: str = '', creg: str = '') -> str:
    """CRT 1 = Simples; 2 = Simples com excesso de sublimite (ICMS pelo regime normal); 3 = regime normal.
    cRegTrib (CF-e): 1 = Simples; 2 = Simples excesso de sublimite; 3 = regime normal."""
    v = crt or creg
    return {'1': 'SN', '2': 'SN_EXCESSO_SUBLIMITE', '3': 'RPA'}.get(v, '')


def inferir_regime(pastas, cnpj: str, amostra_por_pasta: int = 2500) -> dict:
    """Infere o regime da empresa pelas notas que ELA emitiu. Devolve contagem por mês e uma conclusão prudente."""
    cnpj = re.sub(r'\D', '', cnpj)
    por_mes = defaultdict(Counter)
    lidos = 0
    for raiz in pastas:
        for dp, _, fs in os.walk(raiz):
            xmls = sorted(f for f in fs if f.lower().endswith('.xml'))
            passo = max(1, len(xmls) // amostra_por_pasta)
            for f in xmls[::passo]:
                try:
                    with open(os.path.join(dp, f), 'rb') as fh:
                        b = fh.read(10000)
                except OSError:
                    continue
                e = _EMIT.search(b)
                if not e or e.group(1).decode() != cnpj:
                    continue
                c, r, d = _CRT.search(b), _REG.search(b), _DATA.search(b)
                reg = _regime_de(c.group(1).decode() if c else '', r.group(1).decode() if r else '')
                if reg and d:
                    por_mes[f'{d.group(1).decode()}-{d.group(2).decode()}'][reg] += 1
                    lidos += 1
    total = Counter()
    for m in por_mes.values():
        total.update(m)
    if not total:
        return dict(regime='', conclusao='Sem notas próprias com CRT/cRegTrib para inferir o regime.', notas_lidas=0, por_mes={})
    if len(total) == 1:
        reg = next(iter(total))
        concl = f'Todas as {lidos} notas próprias amostradas indicam {reg}.'
    else:
        reg = ''
        concl = 'Regimes diferentes nas notas próprias: houve mudança de regime. Definir o regime por período antes de calcular.'
    if 'SN_EXCESSO_SUBLIMITE' in total:
        concl += ' Há notas com CRT 2 (excesso de sublimite): nesses meses o ICMS é apurado pelo regime normal.'
    return dict(regime=reg, conclusao=concl, notas_lidas=lidos,
                periodo=[min(por_mes), max(por_mes)], por_mes={k: dict(v) for k, v in sorted(por_mes.items())})


def _coletar_estoque(fontes, destino):
    """Copia as posições de estoque para <cliente>/estoque. Fontes: arquivos, pastas ou .zip (o zip é aberto)."""
    os.makedirs(destino, exist_ok=True)
    copiados = []
    for f in fontes:
        f = str(f)
        if os.path.isfile(f) and not f.lower().endswith('.zip'):
            achados, limpar = [(f, None)], (lambda: None)
        else:
            raizes, limpar = intake.preparar_origem(f)
            achados = E.descobrir(raizes)
        try:
            for cam, _ in achados:
                alvo = os.path.join(destino, os.path.basename(cam))
                shutil.copy2(cam, alvo)
                copiados.append(alvo)
        finally:
            limpar()
    return sorted(set(copiados))


def preparar(cliente, cnpj, xml=(), estoque=(), saida='.', regime='', xml_proprios=(), zip_final=False, progresso=None,
             pacote=None) -> dict:
    """pacote: zip/pasta único com os XMLs de compras e as posições de estoque (caso normal de uso da skill)."""
    xml, estoque = list(xml), list(estoque)
    if pacote:
        xml.append(str(pacote))
        estoque.append(str(pacote))
    cnpj_d = re.sub(r'\D', '', cnpj)
    if len(cnpj_d) != 14:
        raise ValueError(f'CNPJ inválido: {cnpj}')
    pasta = os.path.join(saida, nome_pasta(cliente))
    os.makedirs(pasta, exist_ok=True)

    est_copiados = _coletar_estoque(list(estoque), os.path.join(pasta, 'estoque'))
    if not est_copiados:
        raise ValueError('Nenhum arquivo de estoque encontrado nas fontes informadas.')

    resumo = intake.consolidar([*xml, os.path.join(pasta, 'estoque')], os.path.join(pasta, 'relatorio_parser'), cnpj_d,
                               progresso)

    inf = inferir_regime(list(xml_proprios), cnpj_d) if xml_proprios else None
    regime_final, origem_regime = regime, 'informado pelo usuário' if regime else ''
    if not regime and inf and inf['regime']:
        regime_final, origem_regime = inf['regime'], 'INFERIDO das notas próprias (confirmar com o cliente)'

    RM.criar_vazio(os.path.join(pasta, 'resultado_levantamento.xlsx'), cliente, cnpj, regime_final)

    info = dict(cliente=cliente, cnpj=cnpj_d, regime=regime_final or 'não informado', origem_regime=origem_regime,
                regime_inferencia=inf, origens_xml=[str(x) for x in xml],
                estoques=[os.path.basename(e) for e in est_copiados], gerado_em=datetime.now().isoformat(timespec='seconds'),
                resumo_parser={k: resumo[k] for k in ('xml_arquivos_lidos', 'xml_com_erro', 'notas_unicas',
                                                      'itens_de_compra', 'estoque_linhas_total',
                                                      'estoque_linhas_rejeitadas', 'alertas')})
    with open(os.path.join(pasta, 'cliente.json'), 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2, default=str)
    with open(os.path.join(pasta, 'LEIAME.txt'), 'w', encoding='utf-8') as f:
        f.write(f"""{cliente}  |  CNPJ {cnpj}
Regime: {info['regime']} {('(' + origem_regime + ')') if origem_regime else ''}

estoque/                       posições de estoque recebidas
relatorio_parser/              entrada_consolidada.xlsx (Resumo, Compras, Estoque, Estoque rejeitadas, Erros XML, Avisos XML, Eventos)
resultado_levantamento.xlsx    MODELO VAZIO — preenchido por: python scripts/levantamento.py <pasta do cliente>
cliente.json                   dados do cliente e resumo da leitura

Alertas da leitura:
""" + '\n'.join(f'- {a}' for a in resumo['alertas']) + '\n')
    if zip_final:
        zpath = shutil.make_archive(pasta, 'zip', os.path.dirname(pasta), os.path.basename(pasta))
        info['zip'] = zpath
    info['pasta'] = pasta
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cliente', required=True)
    ap.add_argument('--cnpj', required=True)
    ap.add_argument('--pacote', help='zip ou pasta único com XMLs de compras e posições de estoque ("estoque ...")')
    ap.add_argument('--xml', nargs='*', default=[], help='pastas/zips com XMLs de compras (emissão de terceiros)')
    ap.add_argument('--estoque', nargs='*', default=[], help='arquivos, pastas ou zips com as posições de estoque')
    ap.add_argument('--saida', required=True, help='pasta base onde a pasta do cliente será criada')
    ap.add_argument('--regime', choices=['RPA', 'SN'], default='')
    ap.add_argument('--xml-proprios', nargs='*', default=[], help='notas emitidas pela empresa (só para inferir o regime)')
    ap.add_argument('--zip', action='store_true', help='gera também <cliente>.zip')
    a = ap.parse_args()
    if not (a.pacote or (a.xml and a.estoque)):
        ap.error('informe --pacote, ou --xml e --estoque')
    info = preparar(a.cliente, a.cnpj, a.xml, a.estoque, a.saida, a.regime, a.xml_proprios, a.zip,
                    lambda i, n: print(f'  {i}/{n} XML...', flush=True), pacote=a.pacote)
    print(json.dumps({k: v for k, v in info.items() if k != 'regime_inferencia'}, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
