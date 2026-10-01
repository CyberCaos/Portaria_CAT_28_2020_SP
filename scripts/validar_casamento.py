"""Mede a qualidade do casamento por descrição com GABARITO, sem depender de ninguém para rotular nada.

Ideia: os itens do estoque que já casam por EAN com as notas têm resposta certa conhecida. Escondemos o EAN, buscamos
só pela descrição e conferimos se o motor devolve o mesmo produto. Duas provas:
  COM o produto verdadeiro no universo -> precisão por nível (A/B/C) e quantos ficam sem candidato (recall);
  SEM o produto verdadeiro (removido do universo) -> falsos positivos: o que o motor aceitaria errado quando o produto
  nunca foi comprado.

Uso:  python scripts/validar_casamento.py <pasta_do_cliente>            (usa relatorio_parser/compras.csv e estoque.csv)
Rode depois de QUALQUER mudança em casamento_descricao.py e compare com a tabela de references/casamento-descricao.md.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import casamento_descricao as CD  # noqa: E402
import localizar as L  # noqa: E402


def carregar(pasta: str):
    import pandas as pd
    base = os.path.join(pasta, 'relatorio_parser')
    est = pd.read_csv(os.path.join(base, 'estoque.csv'), sep=';', dtype=str, encoding='utf-8-sig').fillna('')
    cmp_ = pd.read_csv(os.path.join(base, 'compras.csv'), sep=';', dtype=str, encoding='utf-8-sig').fillna('')
    est = est[est.arquivo == est.arquivo.iloc[0]].copy()               # uma posição basta (o conteúdo é o que importa)
    est['valor'] = est.valor.astype(float)
    for c in ('qtd', 'qtd_trib', 'vl_merc'):
        cmp_[c] = pd.to_numeric(cmp_[c], errors='coerce').fillna(0)
    return est.to_dict('records'), cmp_.to_dict('records')


def validar(pasta: str):
    est, compras = carregar(pasta)
    loc = L.Localizador(compras)
    gold = [e for e in est if L.gtin14(e['ean']) in loc.por_ean]        # itens com resposta conhecida
    resultados = {'com': collections.Counter(), 'sem': collections.Counter()}
    for e in gold:
        z = L.gtin14(e['ean'])
        dec = CD.decidir(loc.indice.buscar(e['descricao'], e['ncm']))
        dec2 = CD.decidir(loc.indice.buscar(e['descricao'], e['ncm'], excluir=z))
        for chave, d, verdade in (('com', dec, True), ('sem', dec2, False)):
            n = d['nivel']
            if n is None:
                resultados[chave][('nenhum', '')] += 1
                continue
            ch, amb, via = d['chave'], d['ambiguo'], ''
            if amb:
                w = CD.desempatar_por_preco(d['candidatos'], e['valor'], loc.preco)
                if w:
                    ch, amb, via = w, False, '+preço'
            rot = n + (' amb' if amb else via)
            resultados[chave][(rot, ('certo' if ch == z else 'ERRADO') if verdade else 'aceitou')] += 1
    print(f'gabarito: {len(gold)} itens | universo de produtos nas notas: {len(loc.indice.prod)}')
    for chave, tit in (('com', 'COM o produto verdadeiro no universo'), ('sem', 'SEM o produto verdadeiro (falso positivo)')):
        print(f'\n== {tit}')
        for k, v in sorted(resultados[chave].items()):
            print(f'   {k[0]:10} {k[1]:8} {v}')
    print('\nLeitura: A e B podem entrar no crédito confirmado; C e ambíguos ficam fora do crédito (sem validação manual).')
    return resultados


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    validar(sys.argv[1])
