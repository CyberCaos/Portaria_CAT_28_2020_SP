# Entradas esperadas — campos canônicos

> **STATUS.** **Compras** vêm direto dos XMLs de NF-e (`scripts/parser_xml/` + `scripts/compras.py`). **Estoque**: layout real confirmado com os arquivos da drogaria piloto (relatório "Posição de Estoque (Inventário)", `.xls`), leitor e validação em `scripts/estoque.py`. **Empresa**: CNPJ e regime vêm da conversa.

Os nomes canônicos são os usados em `scripts/*.py`. Obrigatório = sem ele o item vai para pendência.

## 1. Empresa (um registro)

| Campo | Obrig. | Observação |
|---|---|---|
| `cnpj`, `razao_social` | sim | identificação do relatório |
| `uf` | sim | esta skill cobre SP (Portaria CAT 28/2020) |
| `regime_apuracao` | sim | `RPA` ou `SN` — define Anexo IV ou V |
| `ie` | não | útil para o Bloco H/EFD |
| `periodo_analise` | não | competências a considerar |

## 2. Posição de estoque (uma linha por produto e data de posição)

Um arquivo por data, com a data no nome: `estoque 31.12.2025.xls` (aceita `.xls`, `.xlsx`, `.csv`). O cabeçalho pode estar
em qualquer uma das 40 primeiras linhas; linha de totais no rodapé é reconhecida e usada para conferir a soma.

**OBRIGATÓRIOS (definidos pelo usuário para os cruzamentos): EAN, DESCRIÇÃO, NCM e VALOR.** Além deles, quantidade e código do
produto, sem os quais a linha não serve ao cálculo. Coluna obrigatória ausente = erro **bloqueante** do arquivo; linha com
campo obrigatório ausente/inválido = linha **rejeitada** com motivo (aba "Estoque rejeitadas"), nunca descartada em silêncio.

| Campo canônico | Coluna do relatório | Obrig. | Regra de validação |
|---|---|---|---|
| `ean` | Código de Barras | **sim** | só dígitos, 8/12/13/14; "SEM GTIN" ou vazio rejeita. DV GTIN inválido = aviso (pode ser etiqueta interna) |
| `descricao` | Descrição do Produto | **sim** | não vazia |
| `ncm` | NCM | **sim** | 8 dígitos. O Excel grava NCM como número e perde o zero à esquerda: 7 dígitos é corrigido com aviso (`9021000` → `09021000`) |
| `valor` | Preço Custo Médio | **sim** | custo unitário médio > 0. Se só houver o total, `valor = total / qtd` |
| `qtd` | Qtde. | sim | > 0 |
| `cod_produto` | Produto ID | sim | código interno (Anexo I item 2) |
| `valor_total` | Total Preço Custo Médio | não | conferido contra o total do rodapé |
| `unidade` | Unidade | não | |
| `grupo_pai`, `grupo_filho` | Grupo pai / filho | não | ajuda a segmentar (ex.: ÉTICO, GENÉRICO, PERFUMARIA) |
| `cst_icms` | CST | não | **classificação atual do cadastro, não a histórica**: não prova o regime na data da posição |
| `totalizador`, `aliq_totalizador` | Totalizador (ex.: `TC (18.00)`) | não | alíquota do totalizador fiscal do PDV; dica para a alíquota interna, **não** substitui a legislação |
| `cest` | *(não existe neste layout)* | — | resolvido pelo EAN nas NF-e de compra (`cest_origem`: `nfe_ean`, `nfe_ean_ambiguo`, `nao_encontrado`, `estoque`) |
| `data_posicao` | nome do arquivo | sim | deve ser o **dia anterior** à data de revogação do produto |

Preço de venda e custo total de venda são lidos mas não usados no crédito.

**Verificação de histórico.** O intake compara o conteúdo das posições: datas diferentes com conteúdo idêntico geram só aviso
informativo: a posição enviada vale como está (decisão do usuário; ver `fluxo-analise.md`).

## 3. Compras — um registro por item de NF-e de entrada (gerado pelo parser de XML)

| Campo | Obrig. | Observação |
|---|---|---|
| `chave_nfe`, `numero`, `serie`, `data_emissao` | sim | Anexo I item 1 |
| `n_item` | sim | Anexo I item 6 |
| `cnpj_emitente`, `uf_emitente` | sim | define operação interna/interestadual |
| `crt_emitente` (ou `regime_fornecedor`) | sim | Simples × regime normal |
| `cod_produto` (e/ou código do fornecedor) | sim | de-para com o estoque; se o código do fornecedor difere do interno, é preciso tabela de de-para |
| `ncm`, `cest` | sim | |
| `cfop` | sim | |
| `unid_comercial`, `qtd` | sim | unidade e quantidade do item na NF (Anexo I itens 7 e 8) |
| `fator_conversao` | sim | unidades de estoque por unidade comercial; default 1 |
| `vl_merc` | sim | valor da mercadoria do item (Anexos IV/V: "indicado no item do documento fiscal"). Conferir se o layout traz líquido de desconto / com frete e rateios |
| `cst` ou `csosn` | sim | 60 / 500 indicam ST retida anteriormente |
| `vbc_st_ret` | sim | `vBCSTRet` — sem ele crédito = 0 (art. 4º, I) |
| `vbc_fcp_st_ret` | não | `vBCFCPSTRet` |
| `vicms_st_ret` | não | conferência cruzada |
| `p_icms` | não | alíquota do item (interestadual) |
| `responsavel_st` | não | retenção fornecedor / antecipação adquirente / substituto anterior; se ausente, inferir pela nota e sinalizar |

## Parâmetros por produto (não vêm dos arquivos de entrada)

Alíquota interna (+FCP) e `p_red` vêm da nota (com o percentual legal quando o dispositivo fixa a carga). Se a redução é aplicável ao consumidor final vem do RICMS/SP: `references/base-legal/ricms-sp-reducoes.csv` (automático) e `<cliente>/enquadramento_reducao.csv` (usuário/análise); ver `reducao-consumidor-final.md`.

## Validações mínimas na entrada

- Duplicidade de `chave_nfe + n_item`; NF cancelada/denegada fora da base.
- `data_emissao` válida e ≤ data da posição; CEST com 7 dígitos; NCM com 8 dígitos.
- Unidades divergentes sem `fator_conversao` → pendência.
- Soma de compras do produto < estoque → `descoberto` (alertar).

## Mapeamento real (preencher ao receber os arquivos)

**Compras (XML → canônico)** — feito em `scripts/compras.py`: `chave_nfe`=chave, `n_item`=nItem, `cnpj_emitente`=emit/CNPJ, `uf_emitente`=emit/enderEmit/UF, `crt_emitente`=emit/CRT, `cod_produto`=prod/cProd, `unid_comercial`=uCom, `qtd`=qCom, `unid_trib`/`qtd_trib`=uTrib/qTrib, `vl_merc`=vProd, `cst`=CST ou CSOSN (CSOSN = fornecedor do Simples), `orig`=orig (origem da mercadoria: 1, 2, 3, 8 = importado, alíquota interestadual 4%), `vbc_st_ret`=vBCSTRet, `p_st`=pST, `vicms_st_ret`=vICMSSTRet, `vbc_fcp_st_ret`=vBCFCPSTRet, `vicms_substituto`=vICMSSubstituto, `p_icms`=pICMS, `c_stat`/`protocolo`=protNFe/infProt. Campos que o XML **não** traz e precisam vir de outro lugar: `cod_produto` do estoque (de-para com o código do fornecedor), `fator_conversao`, alíquota interna/FCP/redução (legislação do produto), responsável pela ST quando a nota não deixa claro, e a BC ST da antecipação pelo adquirente (coluna opcional `bc_st_antecipacao`, quando a ST foi paga por guia).

**Estoque** — mapeamento acima (apelidos em `estoque.py`, `APELIDOS`). Novo layout de outro sistema: ajustar os apelidos (ou criar adaptador) e acrescentar um teste com arquivo sintético no mesmo formato.
