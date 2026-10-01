# Fator de conversão (nota → estoque)

Módulo: `scripts/fator_conversao.py` (função `fator_linha`). Testes: `scripts/tests/test_alocacao.py`.

## Por que existe e por que não pode errar para baixo

O estoque conta em **unidade de venda** (5.120 das 5.123 mercadorias vendidas pela drogaria piloto saem em `UND`). A nota pode vender a mesma mercadoria em fardo, caixa ou display. O fator diz quantas unidades de estoque valem **1 unidade da nota**:

`qtd equivalente da linha = qtd da nota × fator`  ·  `base de ST unitária = base da linha ÷ qtd equivalente da linha`

Fator **menor** que o verdadeiro faz a base unitária sair maior e **superconta** o crédito (caso "CHOCOLATE BATON COM 30": se o estoque conta bombom e assumimos caixa, a base sai 30× maior). Fator maior só subconta. Por isso **dúvida nunca vira crédito confirmado**.

## Só o que o usuário anexa: XMLs de compra + descrição do estoque

Não há dados de venda. O fator sai de quatro fontes:

| Fonte | Candidato | Exemplo real |
|---|---|---|
| **XML** | `qTrib/qCom` quando ≠ 1 (o EAN tributável da nota é a unidade do estoque) | `FR GER HIGIFRAL ... 06X08UN`, `uCom` FD, `qTrib` = 6 × `qCom` → **6** |
| **Descrição da nota** | embalagem (`C/24`, `X 60`, `06X34UN` → 6 fardos ou 204 no total) quando o estoque não traz embalagem | `PASSAJA 4 ML` (estoque) × `DISPLAY C/24 FLAC 4ML` (nota) → **24** |
| **Descrição do estoque** | múltiplo inteiro da embalagem do estoque (`C/6` no estoque, `25X6` na nota → 25); ou fração 1/n quando a nota vende a unidade solta e o estoque guarda a caixa | `BENEGRIP C/6 CP` × `BENEGRIP 25X6CPR` → **25** |
| **padrão** | 1 | descrições com a mesma embalagem |

Número que aparece **igual nas duas descrições não é embalagem da nota**: `AGULHA DESC 30X7 C/100` tem "30X7" (calibre) em ambas e não vira fator 30.

## O preço arbitra, não cria

Razão `r = (preço da nota ÷ fator) ÷ custo unitário do estoque`. O custo médio do estoque costuma ser **um pouco maior** que o preço da nota (ST, frete, rateios), então:
- fator ≠ 1 é aceito se `0,4 ≤ r ≤ 1,8` **e** melhora o fator 1 em pelo menos 0,25 (log);
- fator 1 é coerente se `0,4 ≤ r ≤ 2,2`;
- sem candidato de origem declarada, **o fator é 1 mesmo com preço atípico** (o custo médio defasado é comum: genéricos com preço da nota 5× o custo). O preço atípico vira observação, não fator.
- Descrições iguais com preço da nota ≥ 8× o custo (ou ≤ 1/8) e nenhum fator que feche → **confiança C** ("a unidade do estoque pode ser menor que a da nota"). Único caso em que o preço sugere unidade avulsa: embalagem igual nas duas descrições, preço 8× maior e `nota ÷ embalagem` coerente com o custo → fator = embalagem, confiança B, sinalizado.

## Confiança

| | Significado | Supre o estoque (gera crédito)? |
|---|---|---|
| **A** | XML confirmado pelo preço, ou fator 1 com descrições concordantes e preço coerente | sim |
| **B** | fator da descrição confirmado pelo preço; ou fator 1 com preço apenas plausível | sim |
| **C** | há candidatos e nada prova, ou preço absurdo com descrições iguais | **não** (fator fica 1, em revisão) |

## Medição no piloto (histórico de calibração, 30/09/2026; não é resultado esperado)

- Confiança A 2.807 · B 669 · C 112 linhas (49 itens em revisão).
- Fator ≠ 1 em 220 linhas de 151 itens (69 A pelo XML, 151 B pela descrição; nenhum fracionário escolhido). Mais frequentes: 6 e 4 (fardos de fralda, XML), 25, 12, 30, 50, 60 (displays e fardos pela descrição).
- Origens: XML 69 · múltiplo da embalagem do estoque 60 · embalagem da nota (estoque sem embalagem) 36 · preço indica unidade avulsa 30 · fardo/total `n X m` 25.

## Como evoluir

Mude as regras, rode `python scripts/tests/test_alocacao.py` e reveja uma amostra de `fator ≠ 1` na aba "Alocação de notas" (colunas Fator, Origem do fator, Obs. do fator). Caso novo vira teste em `test_alocacao.py`. Se um dia houver dados de venda, a unidade vendida por EAN pode entrar como quinta fonte, sem mudar o restante.
