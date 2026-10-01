# Guia de uso — levantamento de crédito de ICMS sobre estoque (CAT 28/2020)

Este guia leva você do pacote de arquivos ao relatório final, para qualquer segmento da CAT 68/2019 (medicamentos, bebidas, autopeças, tintas, pneus, materiais de construção, eletrônicos, alimentos, higiene e outros). Ele vale para quem usa a skill pelo Claude e para quem roda os scripts direto no terminal.

## 0. Instalação

Python 3.10+ e as dependências do `requirements.txt` (`pandas`, `openpyxl`, `xlrd`, `reportlab`; opcionais `pymupdf` e `pytest`). Para conferir e instalar de uma vez:

```bash
python scripts/verificar_ambiente.py --instalar
```

Sem `--instalar` o script só informa o que falta. Para validar: `python -m pytest scripts/tests -q`.

## 1. O que você precisa ter

> Resumo para repassar ao cliente: [`O-QUE-ENVIAR.md`](O-QUE-ENVIAR.md).

| Item | Descrição |
|---|---|
| **XMLs de compra** | O máximo possível de NF-e de **entrada** (emissão de terceiros), em pasta ou `.zip`; zips dentro de zips são abertos. Eventos de cancelamento, se tiver. |
| **Posições de estoque** | Um arquivo por data, com a data no nome: `estoque 31.12.2025.xls` (também `.xlsx` ou `.csv`). Precisa trazer **EAN, descrição, NCM, valor (custo unitário médio), quantidade e código do produto**. |
| **Dados da empresa** | Nome, CNPJ e **regime**: `SN` (Simples Nacional) ou `RPA`. Sem o regime o cálculo não começa, porque ele escolhe o Anexo V ou o IV. |

**Qual posição de estoque enviar.** A posição que vale é a do **fim do dia anterior** à data em que o produto saiu da ST. Produtos excluídos em 01/01/2026 usam a posição de 31/12/2025; em 01/04/2026, a de 31/03/2026; e assim por diante (01/07, 01/08, 01/10...). Se faltar a posição de uma data, os itens daquela data ficam sem crédito e o relatório avisa; é só enviar o arquivo e rodar de novo. A skill usa as posições **exatamente como foram enviadas**, mesmo que duas datas tenham conteúdo igual.

## 2. Passo a passo

### 2.0 (Opcional) Ver o panorama das saídas da ST

```bash
python scripts/panorama_cat68.py --ano 2026 --saida "C:\clientes\panorama"
```

Lista tudo que saiu e vai sair da ST no ano e as **posições de estoque** que o cliente precisa enviar (uma por data de saída: 31/12, 31/03, 30/06, 31/07 e 30/09 de 2026, por exemplo). Use a aba "Posições de estoque" como checklist.

### 2.1 Montar a pasta do cliente

```bash
python scripts/preparar_cliente.py --cliente "NOME DA EMPRESA" --cnpj 00.000.000/0001-00 \
    --pacote "C:\caminho\pacote.zip" --saida "C:\clientes" --regime SN --zip
```

Cria `C:\clientes\NOME DA EMPRESA\` com as posições de estoque, o relatório do parser (`relatorio_parser/`), o `LEIAME.txt` e o modelo vazio da planilha. Leia o **`LEIAME.txt`**: os alertas que começam com `BLOQUEANTE` impedem o cálculo (por exemplo, coluna obrigatória ausente no estoque).

Se tiver notas **emitidas pela própria empresa**, `--xml-proprios <pasta>` sugere o regime pelo CRT (resultado marcado como "INFERIDO"; confirme).

### 2.2 Rodar o levantamento

```bash
python scripts/levantamento.py "C:\clientes\NOME DA EMPRESA"
```

Faz a triagem, localiza cada item nas notas, aloca as notas, calcula o crédito e grava `resultado_levantamento.xlsx` e a trilha técnica `relatorio_parser/trilha_levantamento.xlsx`. Em carteiras grandes (milhares de notas) leva alguns minutos.

### 2.3 Gerar o PDF

```bash
python scripts/gerar_relatorio.py "C:\clientes\NOME DA EMPRESA"
```

Grava `relatorio_levantamento.pdf` na pasta do cliente.

### 2.4 (Opcional) Tratar as pendências com evidência

Durante o levantamento a skill pode criar dois arquivos na pasta do cliente:

- **`enquadramento_reducao.csv`**: produtos cuja nota traz **redução de base de cálculo**. A fórmula depende de a redução alcançar ou não a venda ao consumidor final (dispositivo do RICMS/SP). A skill decide sozinha o que a lei e a descrição permitem; os demais ficam sem valor até a análise. Preencha `reducao` (`aplicavel`/`nao_aplicavel`), `dispositivo` e a **evidência** (tipo, fonte, apresentação confirmada, vigência) e rode o levantamento de novo.
- **`identidade_cat68.csv`**: mercadorias cuja descrição não corresponde à descrição legal do item da CAT 68. O crédito é somado com uma observação; se a análise concluir que o produto **não é** o item (`confirmado = nao`), ele sai do crédito.

Opcional: **`entradas.csv`** (`chave;data_entrada;origem`) com o registro de entrada das notas (EFD, livro, manifestação). Nota com entrada registrada depois da vigência não supre o estoque.

Ao rodar de novo, as linhas que você preencheu são preservadas.

## 3. Lendo o resultado

### 3.1 Planilha `resultado_levantamento.xlsx`

| Aba | Para que serve |
|---|---|
| **Resumo** | Totais, composição (soma das linhas + ajuste do piso zero), regras aplicadas e premissas. |
| **Anexo II (notas selecionadas)** | Uma linha por item de nota usado: chave NF-e, item, quantidade, valores, alíquota, **fórmula aplicada**, observações do cálculo. É o modelo do Anexo II da portaria. |
| **Resumo por produto** | Total por mercadoria (itens 14 a 19 do Anexo I): valor da mercadoria, base de ST, crédito e valores unitários para o Bloco H. |
| **Resumo por competência** | **O que lançar e quando**: mês, parcela e forma de lançamento. |
| **Pendências** | Alertas e ações (produto sem posição de estoque, nota sem base de ST, alíquota presumida...). |

### 3.2 Relatório PDF

1. **Resumo**: crédito total, mercadorias com crédito, gráfico por data de revogação e situação dos itens.
2. **Como o crédito foi apurado** e **Competência de lançamento**.
3. **Memória de cálculo**: fórmula do anexo, regras aplicadas e crédito por anexo da CAT 68.
4. **Pendências** e **Como ler o detalhamento**.
5. **Detalhamento item a item**: item do estoque → chave de acesso e item da nota rastreada → valores → crédito da linha e crédito do item.
6. **Pontos de atenção**, **itens sem crédito** e **premissas adotadas**.

### 3.3 Fórmulas

| Regime da empresa | Anexo | Fórmula típica |
|---|---|---|
| Simples Nacional | V | `C = (BC ST − VlMerc) × alíquota interna` |
| RPA | IV | depende do regime do fornecedor: por exemplo `C = BC ST × alíquota interna` |

`BC ST` é a base da substituição tributária do item (unitária × quantidade em estoque), `VlMerc` é o valor da mercadoria líquido de desconto e a alíquota vem da nota (pICMSST + pFCPST, ou pST nas CST 60/CSOSN 500). Sem alíquota na nota e no cadastro do estoque, usa-se **18%** como presunção, e a linha recebe uma observação.

### 3.4 Como lançar

- **Simples Nacional**: dedução do ICMS devido no **PGDAS-D** (campo "redução da base de cálculo"), no mês seguinte ao da exclusão; o que exceder compensa nos meses seguintes.
- **RPA**: **12 parcelas** mensais, iguais e sucessivas, a partir do primeiro mês de vigência da exclusão, no **Bloco E da EFD**, código **SP020750** ("Outros Créditos"), com menção à Portaria CAT 28/2020. A última parcela absorve o arredondamento.
- O estoque também precisa constar do **Registro de Inventário (Bloco H, motivo 02)**; os valores unitários estão no Resumo por produto.

## 4. Observações do cálculo (o que são)

Todo crédito calculado entra no total. Quando uma linha depende de uma premissa, a skill registra a **observação do cálculo** e já soma o valor. As mais comuns:

| Observação | O que significa | O que guardar |
|---|---|---|
| Alíquota interna presumida (18%) | Nem a nota nem o estoque trazem a alíquota. | A alíquota legal do produto (cadastro fiscal). |
| Analogia do Anexo IV | A combinação (por exemplo, ST retida por substituto anterior) não consta da tabela do Anexo IV. | O fundamento da analogia. |
| Conflito CST × CRT | O código de tributação e o CRT do fornecedor indicam regimes diferentes; usa-se o CST/CSOSN. | A confirmação do regime do fornecedor. |
| Base que parece já reduzida | Na nota, BC ST × alíquota reproduz o imposto suportado. | A natureza da base. |
| Identidade da mercadoria | A descrição não corresponde claramente à descrição legal do item. | GTIN/registro sanitário ou documentação do fabricante. |

## 5. Casos que a skill resolve sozinha

- **Anexo parcial sem CEST** e **NCM em mais de um anexo**: escolhe o anexo e o item pela descrição do produto (mamadeira → Anexo XI, por exemplo). Se nenhum item candidato combina com a descrição, o produto fica fora do crédito, com o motivo na triagem.
- **Item de nota usado duas vezes**: impossível; um livro-razão de consumo garante que cada item de nota supre o estoque no máximo pela quantidade comprada.
- **Fator de conversão** (nota vende caixa, estoque conta unidade): inferido pela descrição do estoque e da nota; sem prova, a nota não supre o estoque.
- **NF complementar**: incorporada ao item da nota original quando se liga a ele (refNFe + código/EAN/número do item).

## 6. Quando um item fica sem crédito

O PDF e a planilha mostram o motivo de cada um: **BC ST não supera o valor da mercadoria**; **sem base de ST na nota** (CST 60/CSOSN 500 sem `vBCSTRet`: pode haver oportunidade com NF complementar do fornecedor); **sem prova documental** (descrição de baixa confiança); **sem nota anterior à vigência**; **sem posição de estoque** para a data.

## 7. Perguntas frequentes

**Posso rodar de novo depois de corrigir algo?** Sim. O levantamento é refeito do zero e preserva só as decisões que você registrou nos CSV.

**Como mudo o regime?** Rode `preparar_cliente.py` com o `--regime` correto (ou apague a pasta e refaça); o regime decide a fórmula.

**O total mudou depois de uma atualização da skill. Por quê?** Use `python scripts/reconciliar.py <pasta> --anterior-total <valor>`: gera `relatorio_parser/ponte_reconciliacao.xlsx` com a ponte por produto e por motivo.

**Saiu ato novo na CAT 68?** Atualize `references/base-legal` e regenere a base com `scripts/base/build_cat68_revogados.py`.

**Os dados dos clientes vão para o repositório?** Não. A pasta `clientes/` e certificados digitais estão no `.gitignore`.

## 8. Onde aprofundar

[`SKILL.md`](../SKILL.md) (instruções completas), [`references/regras-do-levantamento.md`](../references/regras-do-levantamento.md), [`references/matriz-formulas.md`](../references/matriz-formulas.md), [`references/estrutura-cliente.md`](../references/estrutura-cliente.md) e [`references/lancamento-e-escrituracao.md`](../references/lancamento-e-escrituracao.md).
