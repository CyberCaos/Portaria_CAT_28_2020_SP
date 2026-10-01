---
name: credito-icms-estoque-st
description: Levantamento do crédito de ICMS sobre o estoque de mercadorias de qualquer segmento (medicamentos, bebidas, autopeças, tintas, pneus, materiais de construção, eletrônicos, papelaria, alimentos, higiene e demais anexos da CAT 68) excluídas do regime de substituição tributária (ICMS-ST) em São Paulo, conforme Portaria CAT 28/2020 (Anexos I a V) e a relação de produtos revogados da Portaria CAT 68/2019. Use sempre que o usuário falar em crédito de ICMS de estoque, exclusão/saída de produtos da ST, ressarcimento ou complementação de ICMS-ST, Portaria CAT 28/2020, CAT 68/2019, SRE 64/25, SRE 34/26, inventário na mudança de tributação (Bloco H, motivo 02), código de ajuste SP020750, ou quando enviar posição de estoque, planilha de notas de compra (NF-e parseadas) e dados de empresa (RPA ou Simples Nacional) para calcular o crédito — mesmo que ele não cite a portaria pelo número.
---

# Crédito de ICMS sobre estoque na exclusão da ST (SP)

Quando um produto sai da ST (revogado da Portaria CAT 68/2019), o contribuinte que tem estoque dele pode se creditar do imposto que já foi retido/antecipado. A Portaria CAT 28/2020 define como apurar: qual estoque, quais notas de entrada o lastreiam, a fórmula do crédito e como lançar. Esta skill executa esse levantamento de ponta a ponta e deixa o resultado auditável. Serve a **qualquer segmento** dos 18 anexos da CAT 68/2019 (não é só farmácia): a triagem, a alocação e as fórmulas são as mesmas; o casamento por descrição foi calibrado em farmácia e perfumaria, então nos demais segmentos o EAN é o caminho principal (o que não casa com segurança fica fora, com o motivo).

## Instalação e dependências

Quando o usuário pedir para **instalar** a skill, ou na **primeira vez** que for usá-la numa máquina, confira e instale as dependências antes de qualquer outra coisa:

```bash
python scripts/verificar_ambiente.py --instalar
```

O script exige **Python 3.10+**, confere `pandas`, `openpyxl`, `xlrd` (posições de estoque em `.xls`) e `reportlab` (PDF), mais `pymupdf` e `pytest` (opcionais), e instala o que faltar com `pip install -r requirements.txt`. Sem `--instalar` ele só informa o que falta. Depois, para validar a instalação, rode `python -m pytest scripts/tests -q`. Se o `pip` falhar (sem internet ou sem permissão), mostre o erro ao usuário e peça para instalar manualmente com `pip install -r requirements.txt`; não siga sem as dependências obrigatórias.

## Estado da skill

- **Pronto**: leitura do pacote (XMLs de compras + posições de estoque), parser de NF-e, base legal, **levantamento completo** em `scripts/levantamento.py` (triagem pela regra de ouro, localização nas notas por EAN e descrição, fator de conversão, alocação de notas com base de ST unitária e alíquota, **fórmula do Anexo V/IV** em `credito.py`, Anexo II, resumo por produto e por competência, pendências). Saída: `resultado_levantamento.xlsx`.
- **PDF**: pronto (`python scripts/gerar_relatorio.py <pasta_cliente>` → `relatorio_levantamento.pdf`: resumo, memória de cálculo, detalhamento item do estoque + chave de acesso + item rastreado + crédito por item, apêndice).
- **Crédito unificado** (decisão do usuário, 01/10/2026). Todo crédito calculado pela fórmula do anexo é crédito e entra no **total único** (e no lançamento); não há separação entre definitivo e interpretativo. As premissas adotadas em parte das linhas (analogia, alíquota presumida, percentual da operação própria, base que parece já reduzida, enquadramento por análise, conflito CST × CRT, documento a conferir, identidade a documentar) viajam como **observações do cálculo** (coluna do Anexo II e do Resumo por produto, aba Pendências e seção do PDF), já somadas ao total. Só ficam sem valor: linha sem dado fiscal para a fórmula (pendente), mercadoria que a análise concluiu não ser o item da CAT 68 e item sem nota provada. Critério de aceite: cada linha é reproduzível pelos parâmetros exportados no Anexo II (BC, VlMerc, alíquota, pRedBc e sua origem, enquadramento). Só entra nota **provada** (EAN, ou descrição A/B sem ambiguidade, com fator A/B); o resto sai com o motivo na trilha técnica.
- **Posição de estoque = a enviada pelo cliente**, na data do nome do arquivo, mesmo que duas datas tenham conteúdo igual. Não peça reexportação nem trate isso como bloqueio. Data de revogação sem posição enviada: os itens dela ficam sem crédito (alerta).

## Panorama das saídas da ST

Para saber **tudo que saiu e vai sair da ST em um ano** (por data, anexo e item) e **quais posições de estoque pedir ao cliente**, rode `python scripts/panorama_cat68.py --ano 2026 --saida <pasta>`: grava `panorama_cat68_2026.xlsx` (Resumo por data, Por anexo, Itens, Posições de estoque, Ainda na ST). A situação (já saiu / sai hoje / vai sair) é calculada pela data de hoje (`--hoje AAAA-MM-DD` para simular). Se não houver saída futura na base, diga isso ao usuário e peça para conferir atos novos (`references/base-legal/README.md`) antes de concluir; não invente datas.

## Pacote de entrada

Resumo para o cliente (o que enviar, campos do estoque, regime): `docs/O-QUE-ENVIAR.md`. Quando o usuário perguntar o que precisa mandar, responda com esse resumo: **pasta de XMLs de compra + relatório de posição de estoque (um por data) com EAN, descrição, NCM, quantidade, custo unitário médio e código do produto**, mais razão social, CNPJ e regime.

O usuário entrega **uma pasta ou um .zip** (ex.: `CLIENTE/XML/*.xml` e `CLIENTE/ESTOQUE/estoque 31.12.2025.xls`) contendo, em qualquer subpasta:

1. **XMLs de compras** — o máximo possível de NF-e de entrada (e eventos de cancelamento, se tiver). Zips aninhados são abertos.
2. **Posições de estoque** — arquivos com "estoque" no nome e a data no nome, p. ex. `estoque 31.12.2025.xls` (também `.xlsx`, `.csv`). **Estrutura adaptativa: só DESCRIÇÃO e QUANTIDADE são indispensáveis**; EAN, NCM, custo unitário e código são recomendados (sem eles o produto é identificado pela descrição nas notas de compra, `scripts/identificacao_estoque.py`). Linha sem descrição ou quantidade é rejeitada com motivo; coluna indispensável ausente bloqueia o arquivo. O relatório da drogaria piloto não traz CEST: ele é resolvido pelo EAN nas NF-e de compra. Detalhes em `references/entradas-esperadas.md`.
3. **Dados da empresa** — nome, CNPJ e regime (RPA ou Simples Nacional), informados na conversa. Sem o regime o cálculo não começa: ele escolhe o Anexo IV (RPA) ou V (Simples). Se o usuário tiver as notas emitidas pela própria empresa, o regime pode ser **sugerido** pelo CRT (NF-e/NFC-e) ou cRegTrib (CF-e-SAT) — `--xml-proprios`; o resultado fica marcado "INFERIDO" e deve ser confirmado. Notas próprias com CRT diferentes ao longo do tempo indicam mudança de regime: definir por período. CRT 2 (excesso de sublimite) significa ICMS pelo regime normal.

Resultado esperado ao final: **um Excel e um PDF** com o levantamento.

## Pasta do cliente (padrão de trabalho)

Todo levantamento começa montando a pasta do cliente — `python scripts/preparar_cliente.py --cliente "<NOME>" --cnpj <CNPJ> --pacote <zip|pasta> --saida <pasta_base> [--regime RPA|SN] [--xml-proprios <pasta>] [--zip]`:

```
<NOME DO CLIENTE>/
  LEIAME.txt, cliente.json          identificação, regime (informado/inferido), resumo e alertas da leitura
  estoque/                          as posições de estoque recebidas (cópia)
  relatorio_parser/                 entrada_consolidada.xlsx + compras.csv + estoque.csv + intake_resumo.json
  resultado_levantamento.xlsx       nasce vazio; levantamento.py preenche (Resumo, Anexo II, resumos, Pendências)
  relatorio_levantamento.pdf        gerar_relatorio.py
  enquadramento_reducao.csv         se houver nota com redução de BC: decisões automáticas + linhas para análise (com evidência)
  identidade_cat68.csv              mercadorias sem identidade confirmada no item da CAT 68 (análise com evidência)
  entradas.csv                      opcional: registro de entrada das notas (chave;data_entrada;origem)
```

Os XMLs originais não são copiados. O modelo vazio vem de `scripts/resultado_modelo.py` e é preenchido por `scripts/levantamento.py`. Ao terminar, entregue a pasta (zip com `--zip`) e os dois xlsx ao usuário. Detalhes e caso piloto em `references/estrutura-cliente.md`.

## Regras do levantamento (definidas pelo usuário)

**Regra de ouro.** Na CAT 68/2019 houve saída de anexo **completo** (ex.: Anexo IX, medicamentos) e saída **parcial**. Para o item do estoque entrar no levantamento: anexo de saída completa → considerar **somente o NCM**; saída parcial → **NCM + CEST**. **Sem CEST** (ou com CEST que não casa) em anexo parcial, e **NCM em mais de um anexo**: a skill escolhe o anexo e o item pela **descrição do produto**, o que mais corresponde à descrição legal do item (`triagem._por_descricao` sobre `identidade_cat68.avaliar`; empate desfeito pelo NCM mais específico e pela data; a escolha e o CEST divergente ficam na coluna de flags da triagem). Sem nenhuma correspondência de descrição, o item fica fora, com o motivo.

**Organização dos dados (ordem):** (1) planilha `resultado_levantamento`; (2) triagem dos estoques com EAN, descrição, NCM, quantidade, valor unitário e total, unificada nela; (3) aba com o relatório do parser; (4) localizar cada item do estoque no parser pelo **EAN** e, se falhar, pela **descrição** com inteligência (mais itens localizados = mais crédito); (5) fator de conversão pela descrição da compra, com base nas vendas.

**Mais regras de ouro (30/09/2026):**
1. **Quantidade do estoque suprida por uma ou mais notas de compra**, localizando o máximo possível: primeiro o produto pelo EAN, depois outros equivalentes por descrição; da nota mais recente para a mais antiga, a última em parte.
2. **Base de ST e base de ST retido anteriormente UNITÁRIAS** do item de cada nota (base da linha ÷ quantidade da nota em unidades de estoque) **× a quantidade do estoque** que a nota supre; só então se aplica a CAT 28/2020.
3. **Alíquota interna**: a alíquota da ST do parser quando houver (pICMSST + pFCPST nas CST 10/30/70; pST sozinho nas 60/500, porque já inclui o FCP); senão, a alíquota interna do item no estoque (totalizador). Sem nenhuma das duas (ou cadastro com 0%), a linha é calculada a 18% como **presunção**, somada ao total com observação do cálculo e a pendência "Alíquota interna presumida": a alíquota legal tem de vir do cadastro fiscal (Anexo I, item 5).
4. **Sempre notas anteriores à vigência da exclusão** da CAT 68/2019 (emissão < data de revogação).

**Fator de conversão** (passo 5): sai da **descrição do estoque** comparada com a da nota e dos XMLs de compra (o usuário só anexa XMLs de compra; não há vendas). Ver `references/fator-conversao.md`.

**Base de ST:** considerar a base de ST retido anteriormente (`vBCSTRet`) **e também** a da própria nota (`vBCST`). As regras e decisões estão em `references/regras-do-levantamento.md`.

**O que ler.** Para **rodar** um levantamento basta este SKILL.md (e `references/estrutura-cliente.md` para entender a pasta do cliente): os três comandos são `preparar_cliente.py`, `levantamento.py` e `gerar_relatorio.py`. Antes de **alterar** código ou regra, leia `references/regras-do-levantamento.md` e `references/matriz-formulas.md`; para mexer na localização ou no fator, `casamento-descricao.md` e `fator-conversao.md`.

**Enquadramento da redução de BC** (detalhes e fontes em `references/reducao-consumidor-final.md`). Linha de nota com redução (`pRedBCST`, ou `pRedBC` com ST na nota) só é calculada com o enquadramento: a redução alcança ou não a venda ao consumidor final, pelo dispositivo do RICMS/SP que a concede. A ordem é:
1. regra do usuário ou da análise em `<cliente>/enquadramento_reducao.csv`;
2. automático (`scripts/enquadramento_auto.py`) **só com identificação positiva**: art. 3º, XXIV quando o princípio ativo listado está ESCRITO na descrição (associações como condições conjuntas: amoxicilina só com clavulanato; "+" com um só princípio do inciso vai para análise), NCM de medicamento, operação interna SP e emissão na vigência. Carga destacada é indício, não confirmação (carga divergente = observação do cálculo). Marca, arts. 34 e 39, demais incisos e redução de outra UF não são automáticos;
3. **análise sua**: depois do `levantamento.py`, abra o arquivo e trate as linhas com `reducao` vazia. Identifique o produto (a coluna `sugestao` traz a marca conhecida como pista, não como prova) e comprove a composição da **apresentação exata** por GTIN/registro sanitário (consulta ANVISA), bula ou ficha do fabricante ou documento oficial; ache o dispositivo na tabela ou no RICMS/SP e confira vigência e condições. Preencha `reducao` (`aplicavel`/`nao_aplicavel`), `dispositivo`, `evidencia_tipo`, `evidencia_fonte`, `apresentacao_confirmada`, `vigencia_condicoes`, `justificativa` e `fonte = analise`; rode `levantamento.py` e `gerar_relatorio.py` de novo. Sem evidência, deixe vazio (fica pendente) e diga ao usuário; nunca escolha pela fórmula de maior ou menor crédito.

**Evidência, não autor.** O que sustenta a decisão é a evidência registrada, não quem analisou: `evidencia_tipo` (`descricao_principio_ativo`, `gtin_registro_sanitario`, `documentacao_fabricante`, `documento_oficial`, `descricao_e_classificacao`), `evidencia_fonte` (registro na ANVISA, bula/ficha do fabricante, link oficial), `apresentacao_confirmada = sim` (a evidência é da apresentação exata: EAN e descrição) e, no enquadramento, `vigencia_condicoes = sim` (vigência, UF e condições do dispositivo conferidas). Evidência completa ou incompleta, o crédito é somado; a incompleta leva observação do cálculo com o que falta documentar.

**Identidade da mercadoria na CAT 68** (`scripts/identidade_cat68.py`). O NCM é a busca inicial; a mercadoria é confirmada quando a descrição do produto corresponde à descrição legal do item (medicamento: NCM 3003/3004/3006 com dose ou forma; demais: termo da descrição legal ou sinônimo de catálogo) e o CEST da nota não aponta outro item (CEST ausente ou ambíguo não impede). Sem correspondência, o levantamento lista a mercadoria em `<cliente>/identidade_cat68.csv`: analise como no enquadramento (o que é o produto, por GTIN/registro/fabricante) e preencha `confirmado` (`sim` = é o item; `nao` = não é, sai do crédito), `evidencia_tipo`, `evidencia_fonte`, `apresentacao_confirmada` e `justificativa`.

**Entrada da mercadoria.** A evidência da entrada é o registro de entrada (EFD C100 `DT_E_S`, livro de entradas, manifestação do destinatário), informado em `<cliente>/entradas.csv` (`chave;data_entrada;origem`): nota com entrada registrada na vigência não supre o estoque. Sem ele, cada linha registra a evidência disponível (`dhSaiEnt` do emitente, que **não** comprova o recebimento, ou só a emissão); a emissão perto da revogação só prioriza a revisão (coluna "Revisar entrada"), não é critério de conformidade.

**Reconciliação.** A cada mudança de regra, rode `python scripts/reconciliar.py <pasta_do_cliente> --anterior-total <valor>`: recalcula as duas versões sobre os mesmos dados e gera a ponte por produto e motivo em `relatorio_parser/ponte_reconciliacao.xlsx`. Não apresente uma mudança de total como simples separação do anterior.
O arquivo é reescrito a cada rodada: linhas automáticas são refeitas; as preenchidas pelo usuário ou pela análise são preservadas. Para trocar uma decisão automática, preencher a linha com `fonte = usuario` e a evidência.

## Fluxo

1. **Ler e validar o pacote** — feito por `preparar_cliente.py` (acima) ou, isolado, `python scripts/intake.py --entrada <pasta|zip> [...] --saida <dir> --cnpj <CNPJ>`. Faz o parse dos XMLs (`scripts/parser_xml/`), descarta duplicatas por chave, aplica cancelamentos, lê as posições de estoque e grava `entrada_consolidada.xlsx` (abas Resumo, Compras, Estoque, Erros XML, Avisos XML, Eventos) + CSVs + `intake_resumo.json`. Leia o Resumo e os alertas antes de seguir; os que começam com BLOQUEANTE impedem o cálculo: colunas obrigatórias ausentes no estoque. As posições recebidas são usadas nas datas declaradas, inclusive quando seu conteúdo é idêntico; a coincidência não prova erro histórico nem bloqueia automaticamente. Os demais: XMLs com erro, itens ST sem base de ST (vBCSTRet / vBCST), notas sem protocolo, eventos órfãos, linhas de estoque rejeitadas, CEST não resolvido. Números sobre dado ruim parecem corretos e não são.
2. **Triar o estoque pela regra de ouro** — `scripts/triagem.py` (ver seção acima e `references/regras-do-levantamento.md`): anexo que saiu **por inteiro** casa **só por NCM**; **parcialmente**, por **NCM + CEST**. Base: `references/base-legal/cat68-2019-produtos-revogados.csv`. O estoque não traz CEST: resolve-se pelo EAN nas NF-e (`resolver_cest`), necessário só nos anexos parciais. Item em mais de um anexo: o CEST da nota desempata; sem CEST, vai para pendência. NCM amplo (≤ 4 dígitos) sem confirmação de CEST é sinalizado como ruído (vitaminas no NCM 2106 do Anexo IV): o crédito fica zero sem base de ST na nota. `particionar` divide por data: a posição de D serve à revogação de D+1.
3. **Checar a data do estoque** — o estoque que conta é o do **fim do dia anterior** à data de revogação (CAT 28/20, art. 2º). Produtos com datas de revogação diferentes (01/01/2026, 01/04/2026, 01/07/2026, 01/08/2026, 01/10/2026…) exigem posição de cada data. A posição enviada vale para a data do nome do arquivo, tal como veio (ver "Estado da skill"). Se faltar a posição de alguma data de revogação, os itens dela ficam sem crédito (alerta): informe o usuário e diga que, se havia estoque nessa data, basta enviar a posição e rodar de novo. Não "ajuste" quantidades por conta própria.
4. **Localizar cada item do estoque nas notas** — `scripts/localizar.py`, cascata: EAN → EAN tributável (`cEANTrib`, traz fator do XML) → EAN de embalagem (GTIN-14) → **descrição por atributos** (nome, qualificadores, dose, embalagem, laboratório, variante, forma; níveis A/B/C, desempate por preço). Só EAN e descrição A/B sem ambiguidade suprem o estoque; C e ambíguos ficam fora do crédito, automaticamente (medido com gabarito: C acerta 55% a 90% e nenhum sinal independente, nem preço nem NCM, separa os acertos); o resto é "não localizado" (sem nota, sem crédito). Critérios, vocabulário e validação com gabarito em `references/casamento-descricao.md`; ao mexer no casamento, rode `scripts/validar_casamento.py <pasta_do_cliente>` e não deixe a precisão de A/B cair.
4b. **Fator de conversão e alocação das notas** — `scripts/fator_conversao.py` e `scripts/alocacao.py` (regras de ouro 1 a 4): para cada item triado, notas anteriores à vigência (autorizadas, não canceladas, não devolução) da mais recente para a mais antiga até cobrir a quantidade, com fator de conversão por linha (XML qTrib/qCom, embalagem da descrição da nota e do estoque, arbitrados pelo preço; fator menor que o real SUPERCONTA o crédito, então fator sem prova (confiança C) não supre o estoque), base de ST unitária × quantidade usada e alíquota da ST. Estoque sem nota suficiente fica `descoberto`.
4c. **Uso único de cada item de nota** — um livro-razão de consumo para o levantamento inteiro (todas as posições e itens): um item de nota nunca supre mais do que comprou. Ordem de escolha pela força da prova: itens casados por EAN primeiro, depois descrição A/B (a ordem do arquivo não decide). `alocacao.verificar_consumo` interrompe o levantamento se houver excesso; a aba "Uso de notas" da trilha lista os itens de nota divididos entre itens do estoque.
4d. **Rodar tudo e montar a planilha** (os passos 2 a 6 rodam juntos aqui) — `python scripts/levantamento.py <pasta_do_cliente>` grava `resultado_levantamento.xlsx` (só o que o cliente usa: Resumo com premissas, Anexo II, Resumo por produto, Resumo por competência, Pendências) e a trilha técnica `relatorio_parser/trilha_levantamento.xlsx` (Triagem estoque, Localização, Alocação de notas, Fora do crédito, Uso de notas, Premissas), que o PDF lê. Já aplica a fórmula do passo 5. Não acrescente abas à planilha do cliente: o que é de trabalho vai para a trilha.
5. **Calcular o crédito por item de nota** — `scripts/credito.py` sobre `scripts/formulas.py` (Anexos IV/V; SN = Anexo V). **VlMerc = valor da operação líquido de desconto** (`vProd + frete + seguro + outras − vDesc`), não `vProd`: nas notas CST 10 do piloto só assim a fórmula reproduz o ICMS-ST cobrado (98% das linhas contra 13%); sem teto pelo ICMS-ST destacado; total da mercadoria = soma das linhas com piso zero (ver `references/matriz-formulas.md`). Insumos por item: base de ST (`vBCSTRet` nas notas CST 60/CSOSN 500 **e também** `vBCST` nas CST 10/30/70), valor da mercadoria, alíquota interna (+FCP), responsável (retenção pelo fornecedor / antecipação pelo adquirente / substituto anterior), operação interna ou interestadual, regime do fornecedor, redução de BC. Ver `references/matriz-formulas.md`.
6. **Aplicar as travas do art. 4º** — sem base de cálculo da ST identificável no item (`vBCSTRet`/`vBCFCPSTRet` em CST 60/CSOSN 500; `vBCST` em CST 10/30/70), crédito = 0. Essa trava também "limpa" o ruído da triagem por NCM amplo: produto sem ST na nota não gera crédito. Nota com BC ST ausente ou a menor pode ser sanada por nota fiscal complementar do fornecedor: listar essas notas como oportunidade, sem contá-las no crédito.
7. **Consolidar** — relatório por mercadoria no modelo do Anexo II (19 itens do Anexo I, tabela A), totais e valores unitários. Esses unitários alimentam o Bloco H (H010/H020, motivo de inventário 02).
8. **Orientar o lançamento** — `references/lancamento-e-escrituracao.md`: 12 parcelas mensais (RPA, código SP020750) ou dedução no PGDAS-D (Simples).

## Princípios (o porquê)

- **Nada de fórmula inventada.** Toda combinação usa uma linha dos Anexos IV/V; as que o Anexo IV não lista (fornecedor RPA com CST 60, substituto anterior ou antecipação com redução, antecipação interna) são calculadas por analogia, e entram no total com **observação do cálculo** (fundamento oficial específico a documentar) (ver `references/matriz-formulas.md`). Crédito de imposto é passível de fiscalização; errar para cima gera autuação.
- **Relatório conforme o regime.** Planilha e PDF mudam textos, fórmula em destaque, premissas e lançamento pelo regime do detentor: Simples = Anexo V e dedução no PGDAS-D; RPA = Anexo IV e 12 parcelas no Bloco E (SP020750), a última absorvendo o arredondamento.
- **Alertas viajam com o número.** A fórmula sai sempre do enquadramento jurídico, pelo texto do anexo (art. 3º). Comparações com o ICMS-ST destacado (rótulos do Anexo V, base que parece já reduzida no Anexo IV) são **diagnóstico** no alerta da linha: nunca trocam a fórmula nem o valor; no Anexo IV, a base aparentemente já reduzida leva observação do cálculo, com o valor alternativo.
- **Rastreabilidade.** Cada valor de crédito precisa apontar para chave NF-e, item, fórmula e linha da tabela aplicada — é o que o fisco pede (arquivo guardado pelo prazo do art. 202 do RICMS).
- **Base legal versionada.** As parcelas já mudaram (24 → 12, SRE 65/25 e SRE 7/26) e novas revogações saem sempre. Antes de fechar um levantamento, verifique se há ato novo após a data de extração em `references/base-legal/README.md` e, se houver, rode `scripts/base/build_cat68_revogados.py` após baixar o consolidado atualizado.

## Saídas

- **Excel** (`resultado_levantamento.xlsx`) e **PDF** (`relatorio_levantamento.pdf`) finais. Excel com 5 abas: Resumo (totais e premissas), Anexo II (notas selecionadas), Resumo por produto, Resumo por competência (lançamento), Pendências. Trilha técnica à parte (`relatorio_parser/trilha_levantamento.xlsx`).
- Memória de cálculo em linguagem simples para o cliente e para auditoria.
- O crédito a lançar é o **total unificado**. Mostre a composição (soma das linhas + ajuste do piso zero = total) e diga que o relatório não comprova a escrituração do Registro de Inventário nem dos lançamentos.

## Mapa dos arquivos

| Arquivo | Uso |
|---|---|
| `README.md`, `docs/GUIA-DE-USO.md` | Apresentação da skill (com imagens do relatório) e guia de uso passo a passo para quem vai usar |
| `exemplos/` | Gerador do pacote fictício (`gerar_pacote_demo.py`) e modelos de saída SN e RPA |
| `references/fator-conversao.md` | Como o fator nota → estoque é inferido da descrição do estoque, do XML e do preço |
| `references/casamento-descricao.md` | Cascata de localização, critérios de casamento por atributos, validação com gabarito, evolução do método |
| `references/reducao-consumidor-final.md` | Redução de BC aplicável ou não ao consumidor final: dispositivos do RICMS/SP, regras automáticas e passo de análise |
| `references/regras-do-levantamento.md` | Regra de ouro, passos 1 a 5 do usuário, estudo do piloto, plano dos passos 6 a 12, decisões em aberto |
| `references/fluxo-analise.md` | Passo a passo detalhado, regras de borda e checklist de validação |
| `references/matriz-formulas.md` | Anexos IV e V literais, árvore de decisão, divergência de rótulos |
| `references/entradas-esperadas.md` | Campos canônicos das entradas (estoque: layout real confirmado com a drogaria piloto) |
| `references/estrutura-cliente.md` | Pasta do cliente, regra do modelo vazio e caso piloto (drogaria piloto) |
| `references/parser-xml.md` | O que o parser extrai, regras de tolerância, o que não foi portado |
| `references/lancamento-e-escrituracao.md` | Parcelas, códigos de ajuste, Bloco H, Simples Nacional |
| `references/base-legal/` | Portarias em HTML/TXT, planilha de produtos revogados, atos revogadores |
| `scripts/panorama_cat68.py` | Panorama das saídas da ST em um ano (o que saiu, o que sai, posições de estoque a pedir) |
| `scripts/verificar_ambiente.py` | Confere (e com `--instalar` instala) Python 3.10+ e as dependências do `requirements.txt` |
| `scripts/preparar_cliente.py` | Monta a pasta do cliente: estoque, relatório do parser, modelo vazio, inferência de regime |
| `scripts/resultado_modelo.py` | Modelo vazio de `resultado_levantamento.xlsx` (abas e cabeçalhos) |
| `scripts/intake.py` | Entrada: pasta/zip -> `entrada_consolidada.xlsx` (compras + estoque + auditoria) |
| `scripts/parser_xml/` | Parser de NF-e/NFC-e e eventos de cancelamento (porte do projeto RelatorioFiscalXml) |
| `scripts/compras.py` | Item de NF-e -> linha canônica de compras |
| `scripts/estoque.py` | Descobre e lê posições de estoque (layout do relatório "Posição de Estoque"; outros ERPs podem exigir ajuste) |
| `scripts/formulas.py` | Crédito por item (Anexos IV/V) |
| `scripts/triagem.py` | Passo 2: regra de ouro (anexo completo = NCM; parcial = NCM+CEST ou, sem CEST, a descrição), partição por data, CEST via EAN |
| `scripts/fator_conversao.py` | Passo 5: fator de conversão nota → estoque pela descrição do estoque, XML e preço |
| `scripts/credito.py` | Fórmula do Anexo V/IV por linha alocada: VlMerc líquido, enquadramento fiscal explícito, piso zero por mercadoria |
| `scripts/alocacao.py` | Regras de ouro 1 a 4: notas que suprem o estoque, base de ST unitária, alíquota |
| `scripts/levantamento.py` | Orquestra triagem, localização, fator e alocação e preenche `resultado_levantamento.xlsx` |
| `scripts/enquadramento_auto.py` | Enquadramento automático da redução de BC (aplicável ou não ao consumidor final) pelo RICMS/SP |
| `scripts/localizar.py`, `scripts/casamento_descricao.py` | Passo 4: localização do estoque nas notas por EAN e por descrição (atributos) |
| `scripts/validar_casamento.py` | Mede precisão/recall do casamento por descrição com gabarito (EAN escondido) |
| `scripts/gerar_relatorio.py` | Gera o PDF final a partir do `resultado_levantamento.xlsx` + `cliente.json` (reportlab; `python scripts/gerar_relatorio.py <pasta_cliente> [destino.pdf]`) |
| `scripts/base/` | Regenera a base CAT 68 a partir do consolidado oficial |
| `scripts/tests/` | Todos os `test_*.py` (parser, intake, cliente, localização, triagem, alocação, crédito, levantamento, regressões fiscais, relatório). Rodar com `python -m pytest scripts/tests -q` (a partir da pasta da skill) |
| `assets/anexo-ii-colunas.json` | Colunas e numeração oficial do relatório (Anexo II) |


## Correções fiscais e cronologia

Identificar por EAN e por descrição antes de alocar: reunir todas as entradas da mesma mercadoria
com identidade confirmada e ordená-las globalmente da mais recente à mais antiga, preservando
origem da identificação, conversão e controle de consumo. EAN não faz nota antiga preceder nota nova.
Não limitar créditos ao ICMS-ST destacado. No Anexo IV, fornecedor RPA com redução não aplicável
ao consumidor final usa BC ST × alíquota interna. Redução exige enquadramento explícito;
seguir os campos e unidades de `references/matriz-formulas.md`; redução em `pRedBCST` ou, com `vBCST`, em `pRedBC`.
Regime do fornecedor pelo CST/CSOSN do item (CSOSN = SN, CST = RPA); CRT só sem CST válido. Responsável pela base presente (`vBCST` = fornecedor; só `vBCSTRet` = substituto anterior).
Regime do fornecedor desconhecido, redução sem enquadramento e VlMerc zero geram pendências fiscais (sem valor); alíquota interna ausente (18% presumido), alíquota interestadual sem origem (12% presumido), analogias e conflito CST × CRT geram crédito **com observação**,
somado ao total. Não esconder a premissa: ela aparece na observação do cálculo.
Total e valor unitário da mercadoria devem usar a mesma definição de VlMerc.
