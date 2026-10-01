# Matriz de fórmulas — Anexos IV e V (Portaria CAT 28/2020, art. 3º)

Transcrição das tabelas oficiais (`base-legal/portaria-cat-28-2020.html`). Implementação: `scripts/formulas.py`.

**Notação.** C = crédito de um item de documento fiscal · BC ST = base de cálculo da retenção (`vBCSTRet`; FCP em `vBCFCPSTRet`) · VlMerc = valor da mercadoria na entrada, indicado no item · pRedBc = % de redução de BC; quando a lei fixa carga efetiva: `pRedBc = (alíq. interna − alíq. efetiva) / alíq. interna`. Alíquota interna inclui o percentual do fundo de combate à pobreza (Anexo I, item 5).

O crédito total é a soma dos créditos de cada item de nota selecionado (art. 3º, §1º). Cada item entra na proporção `qtd utilizada / qtd do item`.

## Anexo IV — detentor do estoque no RPA

| Fornecedor | Responsável | Operação | Redução de BC | Fórmula |
|---|---|---|---|---|
| RPA | retenção pelo fornecedor **ou** antecipação pelo adquirente | interna ou interestadual | sem | `C = BC ST × Aliq.int` |
| RPA | idem | idem | redução não aplicável ao consumidor final | `C = BC ST × Aliq.int` |
| RPA | idem | idem | redução aplicável ao consumidor final | `C = BC ST × (1 − pRedBc) × Aliq.int` |
| SN | retenção pelo fornecedor | interna | sem | `C = (BC ST − VlMerc) × Aliq.int` |
| SN | idem | interna | com, **não** aplicável ao consumidor final | `C = (BC ST − VlMerc) × (1 − pRedBc) × Aliq.int` |
| SN | idem | interna | com, aplicável ao consumidor final | `C = (BC ST − VlMerc × (1 − pRedBc)) × Aliq.int` |
| SN | idem | interestadual | sem | `C = BC ST × Aliq.int − VlMerc × Aliq.inter` |
| SN | idem | interestadual | com, **não** aplicável ao cons. final | `C = (BC ST × Aliq.int − VlMerc × Aliq.inter) × (1 − pRedBc)` |
| SN | idem | interestadual | com, aplicável ao cons. final | `C = BC ST × Aliq.int − VlMerc × (1 − pRedBc) × Aliq.inter` |
| SN | retenção por substituto anterior ao fornecedor | interna ou interestadual | sem | `C = BC ST × Aliq.int` |
| SN | antecipação pelo adquirente | interestadual | sem | `C = BC ST × Aliq.int` |
| SN | antecipação pelo adquirente | interestadual | com, aplicável ao cons. final | `C = BC ST × (1 − pRedBc) × Aliq.int` |

Leitura interpretativa (não consta da portaria): quando o fornecedor é do Simples, o imposto próprio dele não foi destacado como no regime normal, então a parte do imposto que o fornecedor "já recolhia" (VlMerc × alíquota) é abatida do crédito; por isso aparecem `BC ST − VlMerc` e `Aliq.inter`.

## Anexo V — detentor do estoque no Simples Nacional

Fornecedor RPA ou SN; retenção pelo fornecedor, antecipação pelo adquirente ou retenção por substituto anterior; interna ou interestadual.

| Redução de BC (rótulo literal do Anexo V) | Fórmula |
|---|---|
| sem | `C = (BC ST − VlMerc) × Aliq.int` |
| com, aplicável ao consumidor final | `C = (BC ST − VlMerc) × (1 − pRedBc) × Aliq.int` |
| com, não aplicável ao consumidor final | `C = (BC ST − VlMerc × (1 − pRedBc)) × Aliq.int` |

## VlMerc: valor da operação LÍQUIDO de desconto (decisão com prova)

Os Anexos dizem "VlMerc = valor da mercadoria, na operação de entrada, indicado no item do documento fiscal". Ler isso como `vProd` ignora o desconto incondicional (`vDesc`) que a nota traz e que reduz a base do ICMS próprio do fornecedor. A skill usa **`VlMerc = vProd + vFrete + vSeg + vOutro − vDesc`** (a base do ICMS próprio) e guarda a leitura literal como alternativa.

**Prova nos XMLs do cliente piloto** (7.041 linhas CST 10, operação interna, com ST na própria nota): a fórmula `(vBCST − VlMerc) × pICMSST` deveria reproduzir o `vICMSST` efetivamente cobrado na nota. Resultado:

| VlMerc | linhas com erro < R$ 0,10 | erro mediano | soma da fórmula × cobrado |
|---|---|---|---|
| `vProd` | 13% | R$ 0,95 | R$ 17,7 mil × R$ 38,8 mil |
| `vProd − vDesc` | 98% | R$ 0,003 | R$ 38,4 mil × R$ 38,8 mil |
| `vProd + frete + seguro + outras − vDesc` | 99% | R$ 0,003 | R$ 38,4 mil × R$ 38,8 mil |

73% das linhas do piloto têm desconto. Com `vProd` a fórmula subestima o crédito em mais da metade e cria negativos que não existem (JARDIANCE: `vProd` R$ 738,45, `vDesc` R$ 205,08, base de ST R$ 619,47: negativo pelo bruto, positivo pelo líquido). Observação testada: usar "valor unitário × quantidade do estoque" não resolve negativo, porque a quantidade multiplica os dois termos e o sinal é definido por unidade.

**Sem teto pelo imposto destacado:** aplicar o resultado dos Anexos IV/V. A igualdade com o ICMS-ST cobrado em uma amostra não constitui limite legal do crédito.

**Interpretação adotada** (premissa registrada): o texto dos Anexos não menciona desconto; a skill usa o valor líquido porque é o que reproduz o ICMS-ST cobrado. O Anexo II guarda, no alerta, o crédito que daria com `vProd` nas fórmulas que usam VlMerc.

## ⚠ Divergência de rótulos entre os Anexos IV e V

Para as mesmas duas fórmulas, o Anexo IV chama de "aplicável ao consumidor final" `(BC ST − VlMerc × (1 − pRedBc)) × alíq.` e de
"não aplicável" `(BC ST − VlMerc) × (1 − pRedBc) × alíq.`; o Anexo V faz o contrário. O enquadramento (aplicável ou não) vem do
RICMS/SP (`reducao-consumidor-final.md`); nunca do percentual do XML nem do menor ou maior resultado.

**Revisão fiscal de 01/10/2026:** a fórmula sai do enquadramento jurídico (art. 3º e Anexo V). A comparação de cada fórmula com o ICMS-ST destacado na linha inteira da nota é só **diagnóstico** no alerta ("a fórmula do rótulo X reproduziria o ICMS-ST"): não troca a fórmula. A diferença de rótulos em relação ao Anexo IV, isoladamente, não comprova erro de redação.


## Combinações que o Anexo IV não lista: analogia, com observação do cálculo

As combinações sem linha na tabela são calculadas pela regra da portaria para o mesmo tipo de carga, e a linha **entra no total** com a observação "analogia" (decisão de 01/10/2026: crédito unificado). Guarde o fundamento oficial específico de cada hipótese.

| Fornecedor | Responsável | Operação | Redução | Fórmula aplicada | Fundamento |
|---|---|---|---|---|---|
| RPA | substituto anterior (CST 60) | interna ou interestadual | sem ou não aplicável | `C = BC ST × Aliq.int` | fornecedor substituído não destaca ICMS; toda a carga foi retida antes (art. 4º trata dessa NF-e); igual à linha SN/substituto anterior |
| RPA | substituto anterior | idem | aplicável ao cons. final | `C = BC ST × (1 − pRedBc) × Aliq.int` | regra da linha RPA/RPA |
| SN | substituto anterior | idem | com redução | como RPA/RPA (sem/não aplicável: `BC ST × Aliq.int`; aplicável: `× (1 − pRedBc)`) | regra da linha RPA/RPA |
| SN | antecipação pelo adquirente | interna | qualquer | como a retenção SN interna: `(BC ST − VlMerc) × Aliq.int` (com as variantes de redução) | leitura conservadora: a guia abate a operação própria |
| SN | antecipação pelo adquirente | interestadual | não aplicável | `C = BC ST × Aliq.int` | idem |

`NaoPrevistoNaPortaria` fica só para responsável ou regime do fornecedor desconhecido. No piloto simulado como RPA, as linhas CST 60 de fornecedor RPA (distribuidores) são a maior parte do crédito e entram por essa regra.

**Base da ST que parece já reduzida (Anexo IV):** na fórmula `BC ST × (1 − pRedBc) × alíq.`, se a BC ST da nota reproduz o imposto suportado na linha (`vBCST × alíq. = ICMS-ST + FCP + ICMS próprio`), o crédito fica o da fórmula e a linha entra no total com observação do cálculo, e `BC ST × alíq.` aparece como valor alternativo: a igualdade numérica não demonstra qual base a portaria exige. Quando o dispositivo enquadrado fixa a carga (ex.: 7% no art. 3º, XXIV), `pRedBc` é o legal, `(alíquota − carga) / alíquota`, e não o da nota.

**Antecipação pelo adquirente**: a BC ST não está na nota. Informar em `bc_st_antecipacao` (coluna opcional do `relatorio_parser/compras.csv`) a base do recolhimento por guia; a linha passa a usar o responsável "antecipação". Nota interestadual sem ST e sem essa informação fica sem crédito, com a pendência "Possível antecipação pelo adquirente".

## Como descobrir cada insumo na NF-e

> Orientação prática, não texto da portaria: a coluna "Responsável" é heurística a validar com o usuário/contador caso a caso.

| Insumo | Onde achar |
|---|---|
| BC ST | CST 60/CSOSN 500: `vBCSTRet` (N26) / `vBCFCPSTRet` (N27a), ST retida anteriormente. CST 10/30/70: `vBCST` / `vBCFCPST`, ST retida na própria nota. Usar as duas fontes (ver `regras-do-levantamento.md`, seção 3) |
| Responsável | Pela base presente no item: `vBCST` > 0 (CST 10/30/70/90, CSOSN 201/202/203/900) = retenção pelo fornecedor; só `vBCSTRet` (CST 60/CSOSN 500) = retenção por substituto anterior; sem retenção na nota + recolhimento GNRE/antecipação pelo adquirente = antecipação. Quando a nota não diz, perguntar ao usuário |
| Operação | UF do emitente × UF do destinatário / CFOP (5.4xx/6.4xx etc.) |
| Regime do fornecedor | Código de tributação do ICMS do item: CSOSN (3 dígitos) = Simples; CST (2 dígitos) = RPA (inclui CRT 2, excesso de sublimite). Sem CST válido, o CRT decide (1/4 = Simples; 2/3 = RPA); os dois ausentes = pendência. CST e CRT divergentes: vale o CST, com alerta |
| Alíquota interestadual | `aliquota_interestadual` informada, senão `pICMS` do item; fornecedor do Simples não destaca `pICMS`: 4% se `orig` (N11) for 1, 2, 3 ou 8 (importado, Res. SF 13/2012), senão 12% (Res. SF 22/1989, destino SP); sem `orig`, 12% com alerta |
| Alíquota interna | `pICMSST + pFCPST` (CST 10/30/70); `pST` sozinho (CST 60/500: pela NT 2016.002 já inclui o FCP); senão o totalizador do estoque; sem nenhum (ou 0%), 18%, a alíquota geral de SP, com alerta |
| Redução de BC | Percentual: `pRedBCST`; se zero e o item tem `vBCST`, o `pRedBC` da operação própria (no piloto, 256 das 372 linhas CST 70 trazem a redução só ali). O enquadramento (aplicável ou não ao consumidor final) vem da legislação do produto; sem ele a linha fica pendente |


## Enquadramento explícito no processamento

Nas linhas de `relatorio_parser/compras.csv`, o campo opcional `reducao` aceita
`sem_reducao`, `reducao_aplicavel_consumidor_final` ou `reducao_nao_aplicavel_consumidor_final`.
Preencher conforme a legislação do produto, com justificativa guardada na memória do levantamento.
`p_red_bc_st` e `p_red_bc` são percentuais (50 significa 50%). Redução positiva (em qualquer dos dois campos) sem enquadramento gera pendência; nunca é calculada como "sem redução".
Fornecedor SN em operação interestadual sem `p_icms`: a skill usa 4% (origem importada) ou 12% (destino SP) com alerta;
`aliquota_interestadual` informada no compras.csv prevalece. Não confundir com a alíquota de crédito do Simples.
Ausências são registradas em Pendências e não interrompem as demais mercadorias.
