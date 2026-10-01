# Regras do levantamento (definidas pelo usuário) e plano de aplicação da CAT 28/2020

Fonte: orientações do usuário (30/09/2026) + estudo com os dados reais do cliente piloto (drogaria piloto). Números do piloto são de ordem de grandeza, servem de baliza e não de resultado.

## 1. Regra de ouro (critério de triagem do estoque)

A CAT 68/2019 teve anexos que saíram **por inteiro** e anexos que saíram **parcialmente**. Para decidir se um item do estoque entra no levantamento:

| Situação do anexo | Critério de casamento | Anexos (em 30/09/2026) |
|---|---|---|
| **Saída completa** | **somente NCM** (prefixo: o NCM do produto começa com o NCM do anexo) | IV, VII, VIII, IX (medicamentos), X, XI, XII, XIII, XIV, XV, XVIII, XIX, XX, XXI |
| **Saída parcial** | **NCM + CEST** | III, XVI, XVII, XXII (só os itens revogados) |

Consequências:
- O estoque da drogaria **não tem CEST**; na saída completa isso não importa (só NCM). O CEST só é exigido nos anexos parciais e vem das NF-e pelo EAN.
- O NCM do anexo pode ter 4 a 8 dígitos (103 de 456 NCMs de anexos completos têm 4 dígitos). NCM amplo gera **ruído**: o Anexo IV (sorvete) traz 1806, 1901, 2106 e 0404 e casa suplementos e vitaminas (NCM 2106.90). O crédito desses itens fica **zero por falta de base de ST na nota**, mas eles aparecem na triagem; marcar `NCM amplo (<=4 dígitos)` para o analista enxergar.
- Item que casa em **mais de um anexo** (ex.: mamadeiras, NCM 3924, em XI/XIII/XX, datas diferentes): o NCM define a entrada no levantamento e o **CEST da nota desempata** o anexo (resolveu 62 de 75 casos no piloto). Sem CEST ou CEST que não casa: o anexo e o item são escolhidos pela **descrição do produto** (seção 9); sem correspondência de descrição o item fica fora.
- NCM que também aparece em item **vigente** da ST só conflita se o CEST também casar (NCM + CEST, pois vigentes parciais seguem a mesma regra). No piloto: 9 casos.

## 2. Passo a passo de organização dos dados (definido pelo usuário)

1. Criar a planilha `resultado_levantamento` (feito: modelo vazio na pasta do cliente).
2. **Triagem dos relatórios de estoque**: o que saiu da CAT 68/2019 e entra no cálculo, unificado na `resultado_levantamento` com **EAN, descrição, NCM, quantidade em estoque, valor unitário e valor total** (aplicando a regra de ouro).
3. Nova aba em `resultado_levantamento` com o **relatório do parser** colado.
4. **Localizar todos os itens do estoque no parser pelo EAN**; o que não achar por EAN, analisar pela **descrição** para tentar localizar, com inteligência (cada item localizado vira crédito).
5. **Fator de conversão**: analisar a descrição da compra para montar o fator com base nas vendas.

## 2b. Mais regras de ouro (30/09/2026)

1. **A quantidade em estoque deve ser suprida com uma ou mais notas de compra**, localizando o máximo possível: primeiro o produto pelo EAN, depois outros equivalentes por descrição; nota mais recente primeiro, a última em parte (`scripts/alocacao.py`).
2. **Base de ST e base de ST retido anteriormente "unitárias"** do item de cada nota (base da linha ÷ quantidade da nota em unidades de estoque, já com o fator de conversão), **multiplicadas pela quantidade do estoque** que a nota supre; só então se aplica a CAT 28/2020.
3. **Alíquota interna**: a alíquota da ST do parser quando houver (pICMSST + pFCPST nas CST 10/30/70; pST sozinho nas 60/500, porque já inclui o FCP pela NT 2016.002); quando não houver, a alíquota interna do item no estoque (totalizador do PDV).
4. **Sempre compras anteriores à vigência da exclusão** da CAT 68/2019 (emissão < data de revogação).
5. **O fator de conversão sai da descrição do estoque** (comparada com a da nota e com os XMLs de compra), porque o usuário só anexa XMLs de compra: `references/fator-conversao.md`.

Situação da implementação: passos 1 a 5 do usuário, as regras acima e **a fórmula do Anexo V** rodam em `scripts/levantamento.py` (`scripts/credito.py`). O PDF (`scripts/gerar_relatorio.py`) e o quadro de lançamento (PGDAS-D no Simples; 12 parcelas no Bloco E no RPA) também estão prontos; o que segue em aberto está na seção 6.

## 3. Base de cálculo da ST: considerar as duas fontes

Usar a base de **ST retido anteriormente** (`vBCSTRet`, CST 60 / CSOSN 500) **e também** a base da ST retida na própria nota (`vBCST`, CST 10/30/70, fornecedor substituto). Antes só se olhava `vBCSTRet`, o que escondia R$ 145 mil de compras do piloto. Mapeamento:

| CST/CSOSN da nota | Base de ST | Responsável (Anexos IV/V) |
|---|---|---|
| 10, 30, 70, 90; CSOSN 201, 202, 203, 900 (com `vBCST`) | `vBCST` (+ `vBCFCPST`) do item | retenção pelo fornecedor |
| 60, 500 | `vBCSTRet` (+ `vBCFCPSTRet`) | retenção por substituto anterior ao fornecedor |
| qualquer, com `bc_st_antecipacao` informada | a base do recolhimento por guia | antecipação pelo adquirente |
| 00, 20, 40, 41, 51; CSOSN 101, 102, 103, 300, 400 | sem base de ST | sem crédito (interestadual: pendência "possível antecipação") |
| 60/500 sem `vBCSTRet` (ou 10/70 sem `vBCST`) | não identificável | crédito zero; candidata a NF complementar (art. 4º, II) |

O responsável sai da base presente no item (`credito._responsavel`), não do código; o regime do fornecedor sai do CST/CSOSN (CSOSN = Simples; CST = RPA), com o CRT só quando falta o CST.

O art. 4º, I, da CAT 28/20 cita `vBCSTRet` para fornecedor "contribuinte substituído"; para fornecedor substituto a base é a retenção da própria nota. Leitura da skill, coerente com as tabelas dos Anexos IV/V; confirmar quando surgir dúvida.

## 4. Estudo com dados reais (piloto drogaria piloto)

**Triagem (regra de ouro)** — 3.472 produtos, R$ 275,5 mil de estoque por posição:
- 3.246 (R$ 241,8 mil) casam em anexo de saída completa, só por NCM. Maiores: IX medicamentos 2.034 itens (R$ 173,6 mil), XI perfumaria 861 (R$ 44,2 mil), IV 265 (R$ 20,7 mil, ruído de NCM amplo).
- 5 casam NCM + CEST em anexo parcial; 39 casam só por NCM e faltam CEST/CEST ambíguo (R$ 17,3 mil em 3 itens do XVI); 182 fora.
- 75 itens em mais de um anexo.

**Datas e posições.** Cada posição serve às revogações do dia seguinte:

| Posição (arquivo) | Revogações em vigor no dia seguinte | Anexos / itens |
|---|---|---|
| 31/12/2025 | 01/01/2026 | IX, X, XV, XX e itens de XVI/XVII |
| 31/03/2026 | 01/04/2026 | XI |
| 30/06/2026 | 01/07/2026 | IV, XIX e itens de III/XVII |
| 31/07/2026 (**falta arquivo**) | 01/08/2026 | XII, XIII e itens de XVII/XXII |
| 30/09/2026 (**falta arquivo**; revogação é amanhã) | 01/10/2026 | VII, VIII, XIV, XVIII, XXI e itens de XXII |

Por isso cada arquivo de estoque só contribui com os itens cuja data de revogação é o dia seguinte à data da posição. As posições valem como enviadas pelo cliente (decisão do usuário, 30/09/2026), mesmo com conteúdo igual entre datas; faltam as de 31/07 e 30/09/2026 (itens dessas revogações ficam sem crédito).

**Localização nas notas (passo 4) — IMPLEMENTADA** (`scripts/localizar.py`, método e validação em `casamento-descricao.md`). Dos 3.251 itens triados: EAN 2.539 (78,1%), EAN tributável 51, EAN de embalagem 4, **descrição A/B 89** → **2.683 confirmados (82,5%; R$ 193,4 mil = 79,9% do valor)**; descrição C/ambíguo **128 para revisar** (R$ 10,9 mil); **440 não localizados** (R$ 37,9 mil). A comparação de texto simples (difflib) errava dose (NOVANLO 5 MG × 2,5 MG = 0,89); o motor compara **atributos** (nome, qualificadores, dose, embalagem, laboratório, variante, forma, estágio) e foi validado com gabarito: nível A 99,9% e B 97,7% de precisão. O parser agora lê também `cEANTrib`.

**Cobertura de quantidade (itens com EAN achado e data única)** — 2.526 itens, R$ 183,4 mil: notas anteriores à data de revogação cobrem **89,6%** do valor (R$ 164,3 mil): 2.314 itens totalmente cobertos, 185 parciais, 27 sem nenhuma nota. As notas começam em 02/01/2024.

**Fator de conversão (passo 5)**:
- Unidade da última compra: UN 72%, CX 17%, FR, PCT, FD, CT. Só 282 de 16.949 linhas têm `qTrib` ≠ `qCom`; entre os itens com EAN exato, **1** tem evidência de fator ≠ 1. Padrão: **fator 1**.
- Razão preço da nota ÷ custo médio do estoque **não** serve como fator: 16% dos itens têm razão > 1,75, mas os valores não são inteiros (2,04; 2,22; 2,64), reflexo de custo médio e preços antigos.
- Exceções a tratar: (a) XML com `qTrib`/`qCom` e EAN tributável igual ao do estoque; (b) caixa × unidade (GTIN-14 / núcleo de 12 dígitos); (c) descrição da compra com embalagem ("PCT12", "C/ n", "n X") somada à unidade de venda. Para (c), a base de vendas (CF-e/NFC-e de emissão própria: unidade e descrição vendidas por EAN) define a unidade do estoque; **ainda não testada**.

**Base de ST nas notas que cobrem o estoque** (3.277 linhas, R$ 284 mil de compras): CST 10/30/70 com `vBCST` 1.582 linhas (R$ 145,0 mil); CST 60/500 com `vBCSTRet` 1.209 linhas (R$ 116,2 mil); **sem base de ST 486 linhas (R$ 22,9 mil)**. Fornecedores praticamente todos RPA (CRT 3) e operações internas (SP).

**Ordem de grandeza** (estudo inicial, antes das regras atuais; não usar como resultado): no Simples o crédito é só a parcela (BC ST − valor da mercadoria) × alíquota; no RPA, com fornecedor RPA, é BC ST × alíquota, por isso várias vezes maior. **Regime confirmado pelo usuário: Simples Nacional, sem mudança de regime** → Anexo V para todo o período.

## 5. Como aplicar a CAT 28/2020 a partir daqui (proposta de passos 6 a 12)

| # | Passo | Regra | Base |
|---|---|---|---|
| 6 | **Partição por data** | Para cada posição, reter só itens cuja data de revogação = dia seguinte. Item sem posição correspondente vai para "falta posição de dd/mm/aaaa" | CAT 28 art. 2º |
| 7 | **Notas de lastro** | Por item: entradas com emissão ≤ data da posição, da mais recente para a mais antiga, até cobrir a quantidade (a última parcial, conforme `qtd utilizada`). Só NF autorizada, não cancelada, não devolvida (`finNFe`), CFOP de compra | Anexo I itens 1 a 9 |
| 8 | **Base e responsável por item de nota** | CST → fonte da base (seção 3); operação interna/interestadual por UF; regime do fornecedor pelo CST/CSOSN (CRT só na falta) | Art. 3º, 4º |
| 9 | **Alíquota e redução** | Alíquota interna: pICMSST + pFCPST, ou pST (já com FCP), senão o totalizador do PDV; sem nenhum (ou 0%), 18%, a alíquota geral de SP (decisão do usuário, com alerta). `pRedBc`: o da nota, trocado pelo legal quando o dispositivo fixa a carga; enquadramento pelo RICMS/SP (`reducao-consumidor-final.md`) | Anexo I item 5 |
| 10 | **Fórmula** | Regime da empresa decide: SN → Anexo V; RPA → Anexo IV (`scripts/formulas.py`). Rateio por `qtd utilizada / qtd do item`. Redução de BC sem enquadramento (`enquadramento_reducao.csv`) → pendência; com enquadramento, calcula (Anexo V: a fórmula que reproduz o ICMS-ST da nota, senão a literal; Anexo IV: sem reaplicar a redução se a BC ST da nota já está reduzida). Combinações que o Anexo IV não lista → analogia marcada (`matriz-formulas.md`) | Anexos IV e V |
| 11 | **Consolidação** | Relatório por mercadoria (Anexo II, itens 1 a 19) + unitários para o Bloco H (H010/H020, motivo 02) | Anexo I, II, III |
| 12 | **Lançamento** | RPA: 12 parcelas, código SP020750, primeira parcela no mês da exclusão. SN: dedução no PGDAS-D no mês seguinte. Competências futuras marcadas como a vencer | Art. 3º §§ 2º e 3º |

Regras de borda: produto com `descoberto > 0` tem crédito só na parte coberta; crédito de item não localizado por EAN só entra se a descrição passar na validação por atributos e ficar rotulado "localizado por descrição" (confiança menor); toda linha guarda chave, item, fórmula, linha da tabela e alertas.

## 6. Decisões

**Confirmada pelo usuário**
1. **Regime da drogaria piloto: Simples Nacional, nunca mudou.** Fórmulas do Anexo V.

**Adotadas por sugestão (o usuário aceitou sugestões; mudar se ele vetar)**
2. **Posições históricas** — *substituída pela decisão 12.* Texto original: o ideal era o cliente reexportar cada posição pela data. Enquanto isso, **alternativa a testar**: reconstruir o estoque de cada data D pela movimentação, `estoque(D) = estoque_atual + vendas(D até hoje) − compras(D até hoje)`, usando os XMLs de compra (terceiros) e de venda (CF-e/NFC-e/NF-e próprias); exige a data real da exportação e fica registrada como **premissa** (não captura quebras, ajustes e transferências). A exportação de 31/07/2026 e a de 30/09/2026 também fazem falta (datas de revogação 01/08 e 01/10/2026).
3. **Rótulos do Anexo V** (aplicável/não aplicável ao consumidor final, invertidos em relação ao Anexo IV): só afetam linhas com redução da base da ST. No piloto são **116 linhas (1% das linhas com ST; R$ 10,7 mil de compras)**, todas CST 70 (`pRedBCST` 61,11% e 41,66%). *Revisão fiscal de 01/10/2026:* vale o rótulo literal do Anexo V conforme o enquadramento jurídico; a comparação com o ICMS-ST destacado é só diagnóstico (`matriz-formulas.md`). A decisão anterior (fórmula escolhida pela prova da nota) foi revogada.
4. **Item em mais de um anexo e sem CEST** (13 no piloto): revisão manual; o motor não escolhe data sozinho. O CEST da nota desempata os demais.
5. **Descrição na localização**: níveis **A e B** entram no crédito; **C e ambíguos** ficam fora automaticamente (decisão 13).
6. **Itens sem base de ST** (486 linhas) e CST 60/500 sem `vBCSTRet`: só pendência e oportunidade de nota complementar.
7. **Não localizados (440 no piloto)**: não geram crédito; pedir ao cliente XMLs anteriores a 02/01/2024 e outras fontes (transferências, fornecedores sem XML) antes de desistir deles.

9. **VlMerc líquido de desconto** (`vProd + frete + seguro + outras − vDesc`), sem teto pelo ICMS-ST cobrado (decisão do usuário); a leitura literal (`vProd`) fica no Anexo II só nas fórmulas que usam VlMerc. Prova e números em `matriz-formulas.md`. Adotada; o PDF não mostra a leitura literal (pedido do usuário, 30/09/2026).
10. **Piso zero por mercadoria**: o valor por linha pode ser negativo (base de ST menor que o valor da mercadoria, comum em CST 60 e 70); o total da mercadoria é a soma das linhas (art. 3º, §1º) com piso zero, pois a exclusão nunca gera débito.
11. **Simples Nacional**: sem parcelas; o crédito total é deduzido do ICMS devido no PGDAS-D no mês posterior ao da exclusão e o excedente compensa nos meses seguintes (art. 3º, §3º). A aba "Resumo por competência" traz uma linha por data de revogação.


**Decisões de 30/09/2026 (usuário)**
12. **Posição de estoque é a enviada.** O arquivo "estoque dd.mm.aaaa" é a posição daquela data, tal como veio, sempre; conteúdo igual entre datas não bloqueia nem vira "simulação". Data de revogação sem arquivo: itens sem crédito, com alerta.
13. **Sem validação manual.** Só gera crédito a nota provada: localização por EAN (qualquer método) ou descrição A/B sem ambiguidade, e fator A/B. Por quê: com gabarito (EAN escondido), o nível C acerta 55% a 90% e nenhum sinal independente separa os acertos (faixa de preço 0,85 a 1,15 do custo + NCM de 8 dígitos + produto único: 95% de acerto, mas 69 falsos positivos para 179 acertos quando o produto verdadeiro não está nas notas). Fator C nas notas casadas por EAN é quase sempre custo do estoque 10× a 20× menor que o preço da nota, sem prova de unidade. O que fica fora vai para a aba "Fora do crédito" da trilha, com motivo e potencial, e não exige ação. Notas provadas mais antigas completam a quantidade que a nota sem prova ocuparia.
14. **Uso único do item de nota.** Livro-razão global (todas as posições), prioridade por prova (EAN, depois descrição A/B), trava `verificar_consumo` e auditoria na aba "Uso de notas". Antes o consumo era zerado a cada posição e itens de descrição podiam tomar a nota de um item com EAN que viesse depois no arquivo.
15. **Planilha do cliente enxuta** (5 abas); passos intermediários na trilha técnica.


**Em aberto**
8. **Fator de conversão — resolvido pela descrição do estoque** (sem vendas): XML (qTrib/qCom), embalagem da nota e do estoque, arbitrados pelo preço; dúvida vira confiança C, que não supre o estoque. Ver `fator-conversao.md`. Ponto a acompanhar: 30 linhas em que o preço sugere unidade avulsa com descrições iguais (confiança B, sinalizadas).

## 7. Revisão fiscal de 01/10/2026: crédito definitivo × interpretativo (SUPERADA pela seção 9: hoje o crédito é unificado)

Critério de aceite: cada linha reproduzível pelos parâmetros exportados (Anexo II: BC usada, VlMerc usado, alíquota usada e sua origem, pRedBc usado e sua origem, enquadramento, classe), apontando para documento e fundamento; só entra no **definitivo** quando tudo está resolvido. Mudanças:
1. Anexo V: fórmula pelo enquadramento jurídico; ST destacado só como diagnóstico.
2. Anexo IV: base que parece já reduzida → interpretativo, com o valor alternativo.
3. Enquadramento automático só com identificação positiva (art. 3º, XXIV com princípio ativo escrito; associações conjuntas; vigência, UF).
4. `pRedBC` da operação própria não vai para a fórmula da ST sem fundamento; redução de outra UF não decide sozinha.
5. Analogias do Anexo IV → interpretativo.
6. Alíquota interna presumida (18%), interestadual sem origem (12%) e conflito CST × CRT → interpretativo.
7. Triagem: NCM é busca inicial; definitivo só com CEST confirmando o item da CAT 68 e sem CEST ambíguo.
8. Anexo II exporta os parâmetros efetivamente usados e os originais da nota.
9. Documento: sem protocolo, emissão a menos de 7 dias da revogação, bases de ST somadas, base do FCP diferente, nota complementar vinculada (refNFe) → interpretativo.
10. Resumo/PDF: composição do definitivo (soma das linhas + ajuste do piso zero), alternativa com vProd e aviso de que o relatório não comprova a escrituração.

## 8. Revisão fiscal, 2ª rodada (01/10/2026): critérios de evidência (os critérios de evidência valem; a separação em classes foi superada pela seção 9)

1. Análise automatizada pode ser definitiva: o critério é a evidência (produto identificado, dispositivo aplicável, vigência e condições verificadas, parâmetros documentados), não quem analisou. Revogada a regra "fonte = analise fica interpretativa".
2. Janela de 7 dias revogada como critério: só prioriza a revisão. Evidência de entrada registrada por documento (registro de entrada em `entradas.csv`; `dhSaiEnt` não comprova recebimento).
3. Identidade da mercadoria contra a descrição legal do item da CAT 68 (`identidade_cat68.py`); CEST é uma evidência, não condição suficiente nem necessária.
4. Princípio ativo escrito é uma evidência entre outras: GTIN/registro sanitário, documentação do fabricante e documento oficial também comprovam, registrada a fonte e a apresentação exata.
5. Reconciliação explícita por produto e motivo (`reconciliar.py`).
6. Pontos que só ganharam classificação continuam em aberto e são ditos assim: a NF complementar agora é incorporada ao item original quando se liga a ele (sem vínculo, interpretativo); o FCP com base própria é calculado em cada base, mas a linha segue interpretativa (a portaria usa alíquota única); piso zero por mercadoria e VlMerc líquido são interpretações registradas, mostradas com seu efeito, não validadas juridicamente.

## 9. Decisão do usuário (01/10/2026): crédito unificado e anexo pela descrição

1. Revogada a separação definitivo × interpretativo: todo crédito calculado é somado e apresentado de forma unificada. As ressalvas continuam registradas como **observações do cálculo** (Anexo II, Resumo por produto, Pendências, PDF), sem alterar o total. Sem valor continuam: dado fiscal ausente (pendente), mercadoria que a análise concluiu não corresponder ao item da CAT 68 e item sem nota provada.
2. Anexo parcial sem CEST: a análise é pela descrição do produto contra a descrição legal do item (`triagem._por_descricao`).
3. Item em mais de um anexo: a skill escolhe o melhor anexo pela descrição (maior correspondência; empate pelo NCM mais específico e pela data). Se o CEST da nota diverge do item escolhido, a divergência fica registrada.
4. Sem correspondência de descrição com nenhum item candidato, o item fica fora do crédito (flag na triagem).
