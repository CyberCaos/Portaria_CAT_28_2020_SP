# Localização do estoque nas notas: EAN e descrição

Motor: `scripts/localizar.py` (cascata) + `scripts/casamento_descricao.py` (atributos). Validação: `scripts/validar_casamento.py <pasta_do_cliente>`. Testes: `scripts/tests/test_localizar.py`.

## 1. Cascata (primeiro método que achar vale)

| # | Método | Regra | Confiança |
|---|---|---|---|
| 1 | `ean` | EAN do estoque = `cEAN` da nota (normaliza UPC/EAN-13/GTIN-14 para 14 dígitos, então `0840646003740` = `840646003740`) | exata |
| 2 | `ean_trib` | EAN do estoque = `cEANTrib` (a nota vende caixa, o estoque guarda a unidade); traz `fator_xml = qTrib/qCom` | exata; conferir fator |
| 3 | `ean_embalagem` | mesmo núcleo de 12 dígitos (GTIN-14 de caixa × EAN-13 da unidade) | alta; fator obrigatório |
| 4 | `descricao` | comparação por atributos, níveis A / B / C (abaixo) | A, B confirmam; C e ambíguo = revisar |
| — | `nao_localizado` | sem nota, sem crédito | — |

Notas com `SEM GTIN` entram só no método 4, com chave `SEMEAN|cnpj_emitente|cod_produto`.

## 2. Atributos extraídos da descrição (e como são comparados)

O texto é normalizado antes: entidades HTML duplicadas (`&amp;amp;`), acentos, sufixos de catálogo (`-DEMAIS PROD`, `-OUTROS`, `-GENERICO`, `-SIMILAR`, `-REFERENCIA`, `/ GEN ...`), decimais (`4,8` → `4.8`), colagens (`20MG30CP` → `20 MG 30 CP`).

| Atributo | Como é lido | Contradição |
|---|---|---|
| **Produto** (nome) | tokens sem sais, forma, embalagem, unidade, palavras vazias; abreviações por prefixo (≥ 4 letras: `OLMESART` = `OLMESARTANA`), typo de 1 letra (`COLIDS` = `COLIDIS`), tokens colados (`ONE TOUCH` = `ONETOUCH`); aliases (`HCT` = hidroclorotiazida, `FD`/`FRD` = fralda) | primeiro token sem correspondência = **dura**; palavras diferentes nos dois lados = **dura**; palavra distintiva só de um lado (`OPTIVE` × `OPTIVE ADVANCE`) = suave |
| **Sais** | `CLORIDRATO`, `CL`, `SUCC`, `TART`, `DICLORIDRATO`, `MAG`... são ignorados | — |
| **Qualificadores** | `A D H R B`, `PLUS`, `FORTE`, `MAX`, `GOLD`, `PRO`, `MULHER/HOMEM`, `INFANTIL` (= `PED`/`INF`), `LIBPROL` (= `LP`, `LR`, `XR`, `ER`, `RETARD`, `LIB RET/PROL`), `DISPERSIVEL` (= `DISP`, `SL`, `EFERV`) | conjuntos diferentes nos dois lados = **dura**; só de um lado = suave |
| **Dose / gramatura / volume** | cadeias `5000MCG+100+100MG`, `20/12,5MG`, `900+100MG`, `%`, `UI`, `ML`, `G` (em mg), `CM`/`M` (comprimento); unidade ausente herda a da direita; `40MG/5ML` = `8MG/ML`; `450G` ≈ `450ML` | conjuntos diferentes = **dura**; `5/5MG` × `5MG` (dose combinada × simples) = suave; soma igual (`900+100` = `1000`) = suave; unidade trocada (`125MG` × `125MCG`, `4MG` × `0,4MG`) = suave |
| **Embalagem** | `C/30`, `CX 60`, `60X4`, `CX 60 BL X 4` (=240), `6 BLT 10` (=60), `24+4` e `+4 placebos` (=28), `30 COMP`, `COMP 30`, `120 COM`; ignora `C1`/`A2` (controle) e dose sem unidade (`5000 TAB 30` = 30) e `10X9,4` (gramatura) | quantidades diferentes = **dura** |
| **Laboratório** | siglas conhecidas (`EUR`/`EURO` = Eurofarma, `MDLY`/`MED` = Medley, `GERM`/`GMD` = Germed, `NEOQ`, `BIO`...) | dois laboratórios conhecidos e diferentes = **dura**; sigla desconhecida (`ACT`, `AB`) = suave; só de um lado = suave (sem marca, vários laboratórios = vários EANs) |
| **Categoria** | genérico / similar / referência (sufixo de catálogo, `(G)`, `/ GEN`) | categorias diferentes = **dura** |
| **Variante** | cor, sabor, tamanho (`ROSA`, `MORANGO`, `G`, `XG`, `RN`, `N1`...; `LARAN` = `LARANJA`) | sem interseção = **dura** |
| **Forma** | `COMP`, `CAPS`, `SOL`, `XPE`, `GTS`, `CR`, `POM`, `GEL`... | creme × pomada × gel, ou grupos incompatíveis = **dura**; `COMP` × `CAPS` (fornecedor troca) e líquidos entre si = suave |
| **Estágio / modelo** | número solto (`NAN 1` × `NAN 2`, `NESTOGENO 1` × `2`) | diferentes = **dura** |
| **Controle** | `A1 A2 B1 B2 C1 C5` | rótulo varia entre cadastros: suave |
| **Código de modelo** | `7122` em `OMRON R 7122` e `HEM-7122` | ancora o par mesmo com nome diferente |
| **NCM** | igual / 6 / 4 dígitos / capítulo | outro capítulo = suave (NCM do cadastro pode estar errado) |

**Contradição dura** descarta o par. **Suave** mantém o par, mas no máximo nível `C`.

## 3. Níveis

- **A (perfeito)**: nome idêntico, NCM igual, sem contradição suave, evidência por atributo suficiente (dose, embalagem; ausência nos dois lados conta como neutra), e (se genérico) laboratório igual.
- **B (alto)**: nome compatível, NCM ≥ 6 dígitos, sem suave, evidência mínima.
- **C (revisar)**: nome compatível com alguma evidência, ou com contradição suave.
- **Ambíguo**: mais de um produto com a mesma pontuação no topo (p.ex. mesmo remédio de laboratórios diferentes). Rebaixa para C e tenta **desempate por preço**: vence o de preço de compra mais próximo do custo do estoque (dentro de 2× e com folga de 15%).
- **Genérico sem laboratório no estoque** nunca passa de C: cada laboratório tem EAN próprio.

Só **EAN (qualquer método) e descrição A/B sem ambiguidade** suprem o estoque (`localizar.confirmado`). C e ambíguos ficam fora do crédito automaticamente, com o motivo na trilha técnica (aba "Fora do crédito"); não há validação manual. Sinais testados para promover C sem pessoa (30/09/2026): faixa de preço, NCM de 8 dígitos, produto único; nenhum separa acertos de erros com segurança (ver `regras-do-levantamento.md`, decisão 13).

## 4. Validação com gabarito (piloto drogaria piloto)

Os 2.689 itens do estoque que casam por EAN têm resposta certa conhecida. Escondendo o EAN e buscando só por descrição:

| Nível | Certos | Errados | Precisão |
|---|---|---|---|
| A | 1.055 | 1 | 99,9% |
| B | 259 | 6 | 97,7% |
| C (único) | 383 | 42 | 90% |
| C ambíguo, com desempate por preço | 110 | 30 | 79% |
| C ambíguo, sem desempate | 148 | 119 | 55% (sempre revisar) |
| sem candidato | 536 | — | 20% dos itens |

Quando o produto verdadeiro **não existe** nas notas, o motor aceita algum A/B errado em 3,4% dos casos (47 A e 45 B em 2.689): quase sempre o mesmo remédio com outro EAN (nova embalagem ou laboratório), não produto diferente. É o risco residual; por isso A/B são conferíveis na planilha com `desc_nota` e motivos.

Preço ajuda pouco como veto (falsos positivos: 24% acima de 2× o custo contra 11% dos corretos), então fica só como desempate e alerta.

**Evolução do método** (mesma base de teste): a comparação de texto simples (difflib) achava só 33 dos itens sem EAN com similaridade ≥ 0,95 e errava dose (NOVANLO 5 MG × 2,5 MG = 0,89). A primeira versão por atributos deixava 27% dos itens conhecidos sem candidato e aceitava um A/B errado em 9% dos casos sem o produto verdadeiro (hoje 20% e 3,4%); as correções abaixo vieram de erros concretos vistos com gabarito e estão em `tests/test_localizar.py`: embalagem fora do nome, `LIB RET`, concentração por volume, dose combinada, qualificadores de uma letra, `%`, estágio, tamanho `G`, `LT` = lata, prefixo mínimo de 4 letras, creme × pomada, `COM` = comprimidos.

## 5. Medição no piloto (histórico de calibração, 30/09/2026; não é resultado esperado)

| Método | Itens | % | Valor |
|---|---|---|---|
| EAN | 2.539 | 78,1% | R$ 177,6 mil |
| EAN tributável | 51 | 1,6% | R$ 8,3 mil |
| EAN de embalagem | 4 | 0,1% | R$ 0,1 mil |
| Descrição A/B (confirmados) | 89 | 2,7% | R$ 7,4 mil |
| **Total confirmado** | **2.683** | **82,5%** | **R$ 193,4 mil (79,9%)** |
| Descrição C / ambíguo (revisar) | 128 | 3,9% | R$ 10,9 mil |
| Não localizados | 440 | 13,5% | R$ 37,9 mil |

Por que sobram 440 sem localização: (a) produtos comprados antes de 02/01/2024 (início dos XMLs); (b) fornecedores sem XML no pacote; (c) transferências entre filiais; (d) descrição do estoque muito diferente da nota (kits, nomes comerciais reescritos). Próximas ações: pedir XMLs de 2023 e anteriores, conferir a lista dos 440 (ordenada por valor) com o cliente.

## 6. Como evoluir sem quebrar

1. Mude `casamento_descricao.py` (vocabulário: `LABS`, `ALIAS`, `SAIS`, `QUALIF_SIMPLES`, `VARIANTES`).
2. Rode `python scripts/tests/test_localizar.py` e `python scripts/validar_casamento.py <cliente>`.
3. A precisão de A e B não pode cair; se cair, a regra nova é frouxa demais. Recall que sobe com precisão estável é ganho real.
4. Acrescente ao `test_localizar.py` o caso que motivou a mudança.
