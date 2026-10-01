"""Testes da triagem (regra de ouro) e da partição por data. Rodar: python scripts/tests/test_triagem.py"""
import os
import sys
from collections import Counter
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import triagem as T  # noqa: E402

TRI = T.Triagem()


def test_anexo_completo_so_ncm():
    r = TRI.classificar('30049099')                      # medicamento, Anexo IX saiu por inteiro em 01/01/2026 (SRE 64/25)
    assert r['status'] == 'triado' and r['criterio'] == 'NCM' and r['anexo'] == 'IX' and r['data_revogacao'] == date(2026, 1, 1)
    assert TRI.classificar('30049099', '9999999')['status'] == 'triado'      # CEST qualquer não atrapalha anexo completo
    assert 'IX' in TRI.completos and 'III' not in TRI.completos and 'XVI' not in TRI.completos


def test_anexo_parcial_exige_ncm_e_cest():
    r = TRI.classificar('22011000', '0300300')           # Anexo III item 3 (revogado em 01/07/2026 pela SRE 09/26)
    assert r['status'] == 'triado' and r['criterio'] == 'NCM+CEST' and r['anexo'] == 'III' and r['data_revogacao'] == date(2026, 7, 1)
    sem = TRI.classificar('22011000')
    assert sem['status'] == 'revisar_parcial_sem_cest' and 'CEST' in sem['flags'][0]
    assert TRI.classificar('22011000', '1111111')['status'] == 'revisar_parcial_sem_cest'   # CEST não casa


def test_item_em_mais_de_um_anexo_cest_desempata():
    amb = TRI.classificar('39241000')                    # mamadeira: XX, XI e XIII, datas diferentes
    assert amb['status'] == 'ambiguo' and {a for a, _ in amb['alternativas']} == {'XX', 'XI', 'XIII'}
    r = TRI.classificar('39241000', '2006300')
    assert r['status'] == 'triado' and r['anexo'] == 'XI' and r['data_revogacao'] == date(2026, 4, 1) and r['cest_confirma']


def test_ncm_amplo_so_sinaliza_sem_confirmacao_de_cest():
    sem = TRI.classificar('21069030')                    # suplemento: cai no NCM 2106 do Anexo IV (sorvete), sem ser sorvete
    assert sem['status'] == 'triado' and any('NCM amplo' in f for f in sem['flags'])
    med = TRI.classificar('30049099', '1300100')         # remédio com CEST de medicamento: sem ruído
    assert not any('NCM amplo' in f for f in med['flags'])


def test_fora_da_lista():
    assert TRI.classificar('99999999')['status'] == 'fora' and TRI.classificar('')['status'] == 'fora'


def test_particao_por_data_da_posicao():
    itens = [TRI.classificar('30049099'), TRI.classificar('33049990'), TRI.classificar('22011000', '0300300'),
             TRI.classificar('21069030')]
    for i, it in enumerate(itens):
        it['_i'] = i
    p = T.particionar(itens, [date(2025, 12, 31), date(2026, 3, 31)])
    assert [x['_i'] for x in p['por_posicao'][date(2025, 12, 31)]] == [0]        # IX: revogação 01/01/2026
    assert [x['_i'] for x in p['por_posicao'][date(2026, 3, 31)]] == [1]         # XI: revogação 01/04/2026
    assert sorted(p['sem_posicao']) == [date(2026, 7, 1)]                        # III e IV: falta a posição de 30/06/2026
    assert len(p['sem_posicao'][date(2026, 7, 1)]) == 2


def test_cest_via_ean():
    compras = [dict(ean='7896015591212', cest='1300100'), dict(ean='7896015591212', cest='1300100'),
               dict(ean='7891317038878', cest='1300100'), dict(ean='7891317038878', cest='1300200'),
               dict(ean='SEM GTIN', cest='1300100')]
    est = [dict(ean='7896015591212'), dict(ean='7891317038878'), dict(ean='7897074002015'), dict(ean='7898040321499', cest='2300100')]
    cob = T.resolver_cest(est, T.indice_cest_por_ean(compras))
    assert [e['cest_origem'] for e in est] == ['nfe_ean', 'nfe_ean_ambiguo', 'nao_encontrado', 'estoque'] and cob['total'] == 4


if __name__ == '__main__':
    for n, fn in list(globals().items()):
        if n.startswith('test_'):
            fn()
            print('ok', n)


# ---------------------------------------------------------------- anexo pela descrição do produto (01/10/2026)
def test_anexo_parcial_sem_cest_e_resolvido_pela_descricao():
    tri = T.Triagem()
    sem = tri.classificar('39241000', '')                                   # NCM em anexos parciais, sem CEST: fora
    assert sem['status'] in ('ambiguo', 'revisar_parcial_sem_cest')
    r = tri.classificar('39241000', '', 'MAMADEIRA ANPLAS 240ML BICO REDONDO SIL AZUL')
    assert r['status'] == 'triado' and r['anexo'] == 'XI' and 'pela descrição' in r['flags'][0]


def test_item_em_mais_de_um_anexo_escolhe_o_melhor_pela_descricao():
    tri = T.Triagem()
    r = tri.classificar('22029900', '', 'GATORADE FRUTAS CITRICAS PET 500ML')
    assert r['status'] == 'triado' and r['anexo'] == 'XVI'


def test_descricao_sem_correspondencia_continua_fora():
    tri = T.Triagem()
    r = tri.classificar('39269090', '', 'DISPLAY DE BALCAO 60 PERFUMES')
    assert r['status'] in ('ambiguo', 'revisar_parcial_sem_cest') and any('não corresponde' in f for f in r['flags'])
