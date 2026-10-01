"""Gera um pacote de ENTRADA fictício (XMLs de compra + posição de estoque) para demonstrar a skill.

Nenhum dado é real: empresa, fornecedores, CNPJs, chaves e produtos são inventados. Uso:
    python exemplos/gerar_pacote_demo.py [pasta_destino]      (padrão: exemplos/pacote_demo)
"""
import os
import sys

EMPRESA = ('DROGARIA EXEMPLO LTDA', '33333333000133')
FORNECEDORES = {
    'A': ('DISTRIBUIDORA ALFA FICTICIA LTDA', '11111111000111', 'SP'),
    'B': ('LABORATORIO BETA FICTICIO S/A', '22222222000122', 'SP'),
    'C': ('COMERCIAL GAMA FICTICIA ME', '44444444000144', 'SP'),            # Simples Nacional (CRT 1, CSOSN)
}

# produto: (ean, descricao, ncm, cest, un, qtd_estoque, custo_estoque)
PRODUTOS = {
    'dipirona': ('7890000000015', 'DIPIRONA SODICA 500MG C/10 COMP', '30049099', '1300100', 3.00, 40),
    'losartana': ('7890000000022', 'LOSARTANA POTASSICA 50MG C/30 COMP', '30049069', '1300100', 8.00, 25),
    'paracetamol': ('7890000000039', 'PARACETAMOL 750MG C/20 COMP', '30049069', '1300100', 6.00, 30),
    'mamadeira': ('7890000000046', 'MAMADEIRA BICO DE SILICONE 240ML', '39241000', '', 14.00, 12),
    'shampoo': ('7890000000053', 'SHAMPOO ANTICASPA 400ML', '33051000', '', 11.00, 18),
}

# nota: (numero, data, fornecedor, [(produto, qtd, vUnCom, tipo_icms)])
# tipos: 'ST_FORN' (CST 10, ST retida na nota), 'ST_RET' (CST 60, ST retida anteriormente), 'SN_RET' (CSOSN 500)
NOTAS = [
    (1001, '2025-11-10', 'A', [('dipirona', 60, 3.00, 'ST_RET'), ('losartana', 30, 8.00, 'ST_RET'), ('mamadeira', 12, 14.00, 'ST_RET')]),
    (1002, '2025-12-02', 'A', [('dipirona', 50, 3.20, 'ST_RET'), ('shampoo', 20, 11.00, 'ST_RET')]),
    (1003, '2025-12-12', 'B', [('paracetamol', 40, 6.00, 'ST_FORN'), ('losartana', 10, 8.20, 'ST_FORN')]),
    (1004, '2025-12-20', 'C', [('shampoo', 10, 11.50, 'SN_RET')]),
]


def dv_mod11(corpo):
    peso, soma = 2, 0
    for d in reversed(corpo):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1
    r = soma % 11
    return '0' if r in (0, 1) else str(11 - r)


def chave(numero, data, cnpj):
    aamm = data[2:4] + data[5:7]
    corpo = f'35{aamm}{cnpj}55001{numero:09d}1{numero * 7919 % 10**8:08d}'
    return corpo + dv_mod11(corpo)


def icms(tipo, bc, aliq=18.0):
    if tipo == 'ST_RET':
        return (f'<ICMS60><orig>0</orig><CST>60</CST><vBCSTRet>{bc:.2f}</vBCSTRet><pST>{aliq:.4f}</pST>'
                f'<vICMSSTRet>{bc * aliq / 100:.2f}</vICMSSTRet></ICMS60>')
    if tipo == 'SN_RET':
        return (f'<ICMSSN500><orig>0</orig><CSOSN>500</CSOSN><vBCSTRet>{bc:.2f}</vBCSTRet><pST>{aliq:.4f}</pST>'
                f'<vICMSSTRet>{bc * aliq / 100:.2f}</vICMSSTRet></ICMSSN500>')
    return (f'<ICMS10><orig>0</orig><CST>10</CST><modBC>3</modBC><vBC>0.00</vBC><pICMS>0.0000</pICMS><vICMS>0.00</vICMS>'
            f'<modBCST>4</modBCST><pMVAST>40.00</pMVAST><vBCST>{bc:.2f}</vBCST><pICMSST>{aliq:.4f}</pICMSST>'
            f'<vICMSST>{bc * aliq / 100:.2f}</vICMSST></ICMS10>')


def xml_nota(numero, data, forn, itens):
    nome, cnpj, uf = FORNECEDORES[forn]
    k = chave(numero, data, cnpj)
    dets = ''
    for i, (p, qtd, vun, tipo) in enumerate(itens, 1):
        ean, desc, ncm, cest, _, _ = PRODUTOS[p]
        vprod = round(qtd * vun, 2)
        bc = round(vprod * 1.40, 2)                      # margem de valor agregado fictícia de 40%
        cest_xml = f'<CEST>{cest}</CEST>' if cest else ''
        dets += (f'<det nItem="{i}"><prod><cProd>{p.upper()[:6]}{i}</cProd><cEAN>{ean}</cEAN><xProd>{desc}</xProd><NCM>{ncm}</NCM>'
                 f'{cest_xml}<CFOP>5405</CFOP><uCom>UN</uCom><qCom>{qtd:.4f}</qCom><vUnCom>{vun:.10f}</vUnCom><vProd>{vprod:.2f}</vProd>'
                 f'<cEANTrib>{ean}</cEANTrib><uTrib>UN</uTrib><qTrib>{qtd:.4f}</qTrib><vUnTrib>{vun:.10f}</vUnTrib></prod>'
                 f'<imposto><ICMS>{icms(tipo, bc)}</ICMS></imposto></det>')
    return (f'<?xml version="1.0" encoding="UTF-8"?><nfeProc versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe">'
            f'<NFe><infNFe versao="4.00" Id="NFe{k}"><ide><cUF>35</cUF><mod>55</mod><serie>1</serie><nNF>{numero}</nNF>'
            f'<dhEmi>{data}T10:00:00-03:00</dhEmi><tpNF>1</tpNF><idDest>1</idDest><finNFe>1</finNFe><tpAmb>1</tpAmb></ide>'
            f'<emit><CNPJ>{cnpj}</CNPJ><xNome>{nome}</xNome><enderEmit><UF>{uf}</UF></enderEmit>'
            f'<CRT>{"1" if forn == "C" else "3"}</CRT></emit>'
            f'<dest><CNPJ>{EMPRESA[1]}</CNPJ><xNome>{EMPRESA[0]}</xNome><enderDest><UF>SP</UF></enderDest></dest>{dets}</infNFe></NFe>'
            f'<protNFe versao="4.00"><infProt><tpAmb>1</tpAmb><chNFe>{k}</chNFe><nProt>13525{numero:010d}</nProt><cStat>100</cStat>'
            f'<xMotivo>Autorizado o uso da NF-e</xMotivo></infProt></protNFe></nfeProc>'), k


def main(destino):
    xmls = os.path.join(destino, 'xml')
    est = os.path.join(destino, 'estoque')
    os.makedirs(xmls, exist_ok=True)
    os.makedirs(est, exist_ok=True)
    for numero, data, forn, itens in NOTAS:
        conteudo, k = xml_nota(numero, data, forn, itens)
        with open(os.path.join(xmls, f'{k}.xml'), 'w', encoding='utf-8') as f:
            f.write(conteudo)
    cab = 'Código de Barras;Produto ID;Descrição do Produto;Grupo pai;Grupo filho;Qtde.;Preço Custo Médio;Total Preço Custo Médio;NCM;Unidade;Totalizador'
    virg = lambda v: f'{v:.2f}'.replace('.', ',')
    # duas posições: a de 31/12/2025 serve às exclusões de 01/01/2026 (medicamentos) e a de 31/03/2026 às de 01/04/2026
    for data, ajuste in (('31.12.2025', 1.0), ('31.03.2026', 0.5)):
        linhas = [cab]
        for p, (ean, desc, ncm, cest, custo, qtd) in PRODUTOS.items():
            q = max(1, int(qtd * ajuste))
            linhas.append(f'{ean};{p.upper()};{desc};EXEMPLO;EXEMPLO;{q};{virg(custo)};{virg(q * custo)};{ncm};UN;TC (18,00)')
        with open(os.path.join(est, f'estoque {data}.csv'), 'w', encoding='utf-8-sig', newline='') as f:
            f.write(chr(10).join(linhas) + chr(10))
    print(f'pacote de demonstração em {destino}: {len(NOTAS)} notas, {len(PRODUTOS)} produtos')


if __name__ == '__main__':
    aqui = os.path.dirname(os.path.abspath(__file__))
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(aqui, 'pacote_demo'))
