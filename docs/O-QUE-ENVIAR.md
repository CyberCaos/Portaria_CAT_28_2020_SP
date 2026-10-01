# O que enviar para o levantamento

Para fazer o levantamento do crédito de ICMS sobre o estoque, envie **duas coisas**:

## 1. Pasta com os XMLs de compra

- Os XMLs das **notas fiscais de entrada** (compras de fornecedores), em uma pasta ou em um `.zip`. Subpastas e zips dentro de zips são aceitos. Se o pacote trouxer também notas **emitidas pela própria empresa** (vendas), a skill as separa sozinha: só entram como compra as notas em que a empresa é a destinatária.
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

### Campos do relatório

A skill se adapta à estrutura do seu relatório. **Só duas colunas são indispensáveis**; as demais deixam o cruzamento mais seguro:

| Campo | Situação | Por que importa |
|---|---|---|
| **Descrição do produto** | indispensável | Identifica o produto quando faltam EAN/NCM e escolhe o anexo da CAT 68 quando falta o CEST. |
| **Quantidade** em estoque | indispensável | Quanto precisa ser suprido pelas notas de compra. |
| **EAN** (código de barras) | recomendado | Principal chave para achar o produto nas notas. Sem ele, a skill acha o produto pela descrição. |
| **NCM** (8 dígitos) | recomendado | Define se o produto saiu da ST. Sem ele, a skill usa o NCM da nota em que o produto foi identificado. |
| **Custo unitário médio** | recomendado | Confere o fator de conversão (caixa x unidade). O crédito usa o valor das notas. |
| **Código do produto** | opcional | Se faltar, a skill numera as linhas. |

O **CEST** não é necessário: vem das notas de compra.

**Estruturas aceitas (exemplos):**

- Relatório completo (EAN, descrição, NCM, quantidade, custo, código).
- Relatório só com **descrição, custo e quantidade**, sem EAN nem NCM (por exemplo, um controle de estoque em planilha própria).
- **Custo por caixa** ("CUSTO CX") com quantidade em caixas: a skill lê a quantidade na mesma unidade e confere o fator pelo preço das notas.
- Colunas com **nomes livres** ("Qtd", "Saldo", "Quantidade em estoque", "Custo médio", "GTIN", "Cód. barras"...), cabeçalho em qualquer das 40 primeiras linhas, várias abas (usa a maior), totais em fórmula, `.xls`, `.xlsx` ou `.csv`.
- Linhas com **saldo zero** são ignoradas.

**Quando falta EAN ou NCM**, a skill compara a descrição do estoque com a descrição das notas de compra (inclusive abreviações como "SORV", "MOR" para morango, e a marca igual ao nome do fornecedor) e herda da nota o EAN, o NCM e o CEST. Quando a correspondência não é segura, o produto **não entra** no crédito e vai para o arquivo `identificacao_estoque.csv` da pasta do cliente, com o melhor candidato; informar o EAN/NCM ali e rodar de novo resolve.

### Dicas para o relatório

- Uma linha por produto, com **cabeçalho**. Quanto mais próxima a descrição do estoque da descrição das notas, melhor a identificação.
- Se o relatório trouxer EAN e NCM, informe: o cruzamento fica mais seguro e mais rápido.
- Linha sem descrição ou sem quantidade é **rejeitada com o motivo** e aparece no relatório, nunca é descartada em silêncio.
- A posição enviada vale **como está** para a data do nome do arquivo.

## Além dos arquivos, informe

- **Razão social e CNPJ** da empresa.
- **Regime de tributação**: Simples Nacional (SN) ou Regime Periódico de Apuração (RPA). Define o Anexo V ou IV da CAT 28/2020.

## Resultado

Uma **planilha Excel** e um **relatório em PDF** com o crédito por item, a nota fiscal usada (chave de acesso e item), a fórmula aplicada e o plano de lançamento.
