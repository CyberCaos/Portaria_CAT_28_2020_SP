# O que enviar para o levantamento

Para fazer o levantamento do crédito de ICMS sobre o estoque, envie **duas coisas**:

## 1. Pasta com os XMLs de compra

- Os XMLs das **notas fiscais de entrada** (compras de fornecedores), em uma pasta ou em um `.zip`. Subpastas e zips dentro de zips são aceitos.
- Quanto **mais notas**, melhor: cada item do estoque é localizado nas notas de compra, e só notas **anteriores à data em que o produto saiu da ST** valem. Envie o histórico de compras do período em que o estoque foi formado (de preferência, os últimos 12 a 24 meses antes de cada saída).
- Se tiver, inclua também os XMLs de **cancelamento**.

## 2. Relatório com a posição de estoque

Um arquivo **por data**, com a data no nome do arquivo:

```
estoque 31.12.2025.xls
estoque 31.03.2026.xls
estoque 30.06.2026.xls
```

(também aceita `.xlsx` e `.csv`). A posição é a do **fim do dia anterior** à data em que o produto saiu da ST; a skill lista as datas necessárias (veja `scripts/panorama_cat68.py`).

### Campos obrigatórios do relatório

| Campo | Por que é necessário |
|---|---|
| **EAN** (código de barras) | Principal chave para achar o produto nas notas de compra. |
| **Descrição do produto** | Usada para localizar o item quando o EAN não aparece nas notas e para identificar o anexo da CAT 68 quando falta o CEST. |
| **NCM** (8 dígitos) | Define se o produto saiu da ST (triagem pela CAT 68/2019). |
| **Quantidade** em estoque | Quanto precisa ser suprido pelas notas de compra. |
| **Custo unitário médio** | Valor do estoque por unidade (se vier só o total, a skill divide pela quantidade). |
| **Código do produto** | Código interno do cliente, para rastrear o item. |

O **CEST** não é necessário: a skill o obtém pelo EAN nas notas de compra.

### Dicas para o relatório

- Uma linha por produto, com **cabeçalho** (em qualquer das primeiras 40 linhas). O nome das colunas pode variar (por exemplo, "Código de Barras", "GTIN" ou "EAN"; "Qtde." ou "Quantidade"); a skill reconhece os nomes mais comuns.
- O Excel costuma perder o zero à esquerda do NCM (7 dígitos); a skill corrige e avisa.
- Linha sem EAN, descrição, NCM, quantidade ou valor é **rejeitada com o motivo** e aparece no relatório, nunca é descartada em silêncio. Coluna obrigatória ausente bloqueia o arquivo.
- A posição enviada vale **como está** para a data do nome do arquivo.

## Além dos arquivos, informe

- **Razão social e CNPJ** da empresa.
- **Regime de tributação**: Simples Nacional (SN) ou Regime Periódico de Apuração (RPA). Define o Anexo V ou IV da CAT 28/2020.

## Resultado

Uma **planilha Excel** e um **relatório em PDF** com o crédito por item, a nota fiscal usada (chave de acesso e item), a fórmula aplicada e o plano de lançamento.
