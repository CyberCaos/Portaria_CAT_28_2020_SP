# Fluxo de análise — detalhe e regras de borda

Complementa o fluxo de 8 passos do `SKILL.md`. Cada passo termina em um artefato conferível.

## 0. Preparação
- Confirmar o ambiente: `python -m pytest scripts/tests -q` deve passar.
- Conferir o **frescor da base legal**: data de extração no `base-legal/README.md`. Se passaram semanas ou o cliente fala de revogação recente, baixar o consolidado de novo (https://legislacao.fazenda.sp.gov.br/Paginas/Portaria-CAT-68-de-2019.aspx), salvar como `portaria-cat-68-2019.html` e rodar `python scripts/base/build_cat68_revogados.py`. O script falha (assert) se a data lida na página divergir do ato cadastrado em `ACTS`; ato novo exige incluí-lo em `ACTS` com as datas conferidas no próprio ato.

## 1. Validação das entradas
Checar o que está em `entradas-esperadas.md`. Saída: lista de inconsistências por arquivo e linha. Bloqueantes: sem regime da empresa (SN ou RPA), colunas obrigatórias ausentes no estoque, `compras.csv` sem as colunas fiscais (gerado por parser antigo). Falta de CEST não bloqueia: só pesa nos anexos de saída parcial (vira pendência "anexo parcial sem CEST").

## 2. Produtos excluídos
> **Critério vigente: regra de ouro** (`regras-do-levantamento.md`): anexo completo = só NCM; anexo parcial = NCM + CEST. Implementada em `scripts/triagem.py`; o CEST serve só aos anexos parciais e ao desempate entre anexos. Os níveis alta/revisar/nenhum descritos abaixo são do desenho antigo: hoje o resultado é `triado`, `ambiguo`, `revisar_parcial_sem_cest` ou `fora`.

`classificar_estoque()` devolve por produto: data de revogação, ato, anexo/item e confiança.
- `alta`: CEST confere e NCM confirma por prefixo, sem CEST em item vigente.
- `revisar`: NCM diverge, CEST ainda em item vigente, ou sem CEST. O analista decide; registrar decisão e motivo.
- `nenhum`: fora da lista de revogados — não entra no levantamento.
- Revogação **futura** (vigência posterior à data de hoje) não gera crédito ainda: informar como "a partir de dd/mm/aaaa".
- Produto que saiu da ST mas passou a ter **regime diferente** (ex.: realocado para outro anexo) não é exclusão — a base vigente + aviso do cruzamento cobre isso.

## 3. Data do estoque
Para cada grupo de data de revogação, a posição necessária é do dia anterior. **Conferir se as posições são realmente históricas**: relatórios de sistema muitas vezes refletem o estoque do momento da exportação, não a data do nome do arquivo. A posição enviada pelo cliente vale para a data do nome do arquivo, tal como veio (decisão do usuário): conteúdo igual entre datas gera só um aviso informativo no intake, não bloqueia. Data de revogação sem posição enviada: os itens dela ficam sem crédito, com alerta.

## 4. Seleção das notas
Usar só entradas com emissão até a data de corte. Conferir unidade/fator de conversão. Itens 1 a 9 do Anexo I vêm daqui. Produto com `descoberto > 0`: informar quantidade sem lastro; crédito só para a parte coberta. Não completar com notas de outros produtos ou valores médios.

## 5. Crédito por item
Para cada alocação: escolher fórmula (`matriz-formulas.md`), calcular, ratear pela quantidade usada (`ratear`), guardar linha da tabela, fórmula e alertas. Alíquota interna: a da ST da nota (pICMSST + pFCPST; pST já com FCP), senão a do item no estoque; sem nenhuma (ou 0%), 18%. `pRedBc`: o da nota (pRedBCST, ou pRedBC com ST), trocado pelo percentual legal quando o dispositivo enquadrado fixa a carga; o enquadramento vem do RICMS/SP (`reducao-consumidor-final.md`).

## 6. Travas e oportunidades
- BC ST não identificável → crédito 0; listar NF/item (art. 4º, I).
- BC ST a menor/ausente → candidata a NF complementar (art. 4º, II).
- Combinação sem linha → pendência `NaoPrevistoNaPortaria`.

## 7. Consolidação
Por mercadoria: totais (itens 14 a 16) e unitários por unidade de estoque (itens 17 a 19). Por competência: crédito ÷ 12 (RPA) ou dedução mensal (SN). Conferência: no Simples (Anexo V) o crédito da linha deve ficar perto do ICMS-ST cobrado; no RPA (Anexo IV, fornecedor RPA) ele inclui o ICMS próprio e fica perto de BC ST × alíquota. Não há teto pelo ICMS-ST (decisão do usuário).

## 8. Entrega
Planilha (5 abas) + PDF + trilha técnica. Um só valor de crédito (o provado); o que não tem prova aparece como motivo de "sem crédito".

## Checklist final antes de entregar
- [ ] Testes passam; base legal atualizada ou ressalva registrada
- [ ] Toda linha de crédito tem chave, item, fórmula e alertas
- [ ] Alertas do Anexo V visíveis no resumo
- [ ] Nenhum item de nota usado além da quantidade comprada (`verificar_consumo`; aba "Uso de notas" da trilha)
- [ ] Total reconcilia com a soma das mercadorias (piso zero por mercadoria; a soma simples da coluna do Anexo II pode ser menor)
- [ ] Datas de corte conferidas por grupo de revogação
