# Redução de BC: aplicável ou não ao consumidor final

A CAT 28/2020 tem duas fórmulas para a linha de nota com redução da base de cálculo, conforme a redução **alcance ou não a venda ao consumidor final** (Anexos IV e V; a fórmula sai do enquadramento jurídico, pelo texto do anexo; comparações com o ICMS-ST destacado são só diagnóstico: ver `matriz-formulas.md`). A NF-e não traz essa informação: ela vem do dispositivo do RICMS/SP que concede a redução. Tabela: `base-legal/ricms-sp-reducoes.csv`. Código: `scripts/enquadramento_auto.py`.

## Dispositivos (RICMS/SP, Anexo II), conferidos em 30/09/2026

| Dispositivo | Produtos | Carga | Quem aplica | Alcança o consumidor final? |
|---|---|---|---|---|
| Art. 3º, XXIV | medicamentos com paracetamol, tramadol, montelucaste, amoxicilina + clavulanato, levonorgestrel, carbamazepina, ibuprofeno, glicosamina/condroitina | 7% | todas as operações internas | **sim**: "abrange toda a cadeia de comercialização da mercadoria neste Estado" e entra na base da ST (Resposta à Consulta 4231/2014, item 12) |
| Art. 3º, I a XXV (demais) | cesta básica (alimentos; água mineral retornável) | 7% | operações internas | sim |
| Art. 3º, XXVI e XXVII | arroz e feijão | 7% | operações internas | **não**: o inciso exclui a saída a consumidor final |
| Art. 34 | higiene pessoal: papel higiênico, fraldas, absorventes, perfumes, cosméticos, sabões, dentifrícios, fios dentais, lenços, escovas | 12% | fabricante ou atacadista | **não**: § 1º, 1, b exclui a saída a consumidor final |
| Art. 39 | alimentícios (pescados, laticínios, frutas, preparações, néctares 2202.99 etc.) | 12% | fabricante ou atacadista | **não**: § 1º, 2, b exclui a saída a consumidor final (e a destinada a empresa do Simples) |
| Benefício de outra UF | redução na operação interestadual do fornecedor | — | fornecedor de fora de SP | **não**: a base da ST para SP não é reduzida |

Todos os benefícios do Anexo II acima vigoram até **31/12/2026** (Decretos 69.207/2024 e 70.293/2025). Fontes: [art. 3º](https://legislacao.fazenda.sp.gov.br/Paginas/an2art003.aspx), [art. 34](https://legislacao.fazenda.sp.gov.br/Paginas/an2art034.aspx), [art. 39](https://legislacao.fazenda.sp.gov.br/Paginas/an2art039.aspx), [RC 4231/2014](https://legislacao.fazenda.sp.gov.br/Paginas/RC4231_2014.aspx).

## Como a skill decide (ordem) — revisão fiscal de 01/10/2026

1. **Regra do usuário** em `<cliente>/enquadramento_reducao.csv` (`fonte = usuario`): prevalece sobre o automático; com a evidência registrada (tipo, fonte, apresentação, vigência e condições); evidência incompleta não exclui o crédito: a linha leva observação do cálculo.
2. **Automático** (`enquadramento_auto.classificar`), só com **identificação positiva** dos atributos do dispositivo:
   - art. 3º, XXIV: princípio ativo listado **escrito** na descrição; associações como condições conjuntas (amoxicilina só com clavulanato; "+" com um só princípio do inciso vai para análise); NCM de medicamento; operação interna SP; emissão na vigência (04/07/2014 a 31/12/2026). Carga destacada é indício: carga diferente de 7% mantém o enquadramento, mas deixa a linha interpretativa;
   - marca, arts. 34 e 39, demais incisos do art. 3º e redução de outra UF **não** são automáticos (a descrição precisa ser conferida com o dispositivo).

   A decisão vai para o arquivo com `fonte = automatico`, o dispositivo e a justificativa, e é refeita a cada rodada.
3. **Análise** (o Claude, ao rodar a skill): linhas com `reducao` vazia. Identificar o produto (a coluna `sugestao` traz a marca conhecida como pista) e comprovar a composição da apresentação exata (GTIN/registro sanitário, bula ou ficha do fabricante, documento oficial); achar o dispositivo e conferir vigência e condições. Preencher `reducao`, `dispositivo`, `evidencia_tipo`, `evidencia_fonte`, `apresentacao_confirmada`, `vigencia_condicoes`, `justificativa` e `fonte = analise`.

**Evidência, não autor.** O que sustenta a decisão é a evidência registrada, não quem analisou: `evidencia_tipo` (`descricao_principio_ativo`, `gtin_registro_sanitario`, `documentacao_fabricante`, `documento_oficial`, `descricao_e_classificacao`), `evidencia_fonte` (registro na ANVISA, bula/ficha do fabricante, link oficial), `apresentacao_confirmada = sim` (a evidência é da apresentação exata: EAN e descrição) e, no enquadramento, `vigencia_condicoes = sim` (vigência, UF e condições do dispositivo conferidas). Evidência completa = definitivo, venha do automático, da análise ou do usuário; incompleta = interpretativo, com o que falta.

**Percentual que entra na fórmula:** o legal, `(alíquota − carga) / alíquota`, quando o dispositivo fixa a carga; senão o `pRedBCST` da nota (redução da base da ST). O `pRedBC` da operação própria do fornecedor é outra informação: não é levado à fórmula da ST sem fundamento (se for o único percentual, a linha fica interpretativa). A redução de outra UF é benefício da origem e não decide, sozinha, o alcance nas operações internas de SP.

Para trocar uma decisão automática, preencher a linha com `fonte = usuario` e a evidência completa.

## Piloto (calibração)

Com as regras de 01/10/2026, a maior parte dos medicamentos do piloto (marcas como Tylenol e Clavulin, sem o princípio ativo escrito) vai para análise: a marca não é identificação positiva.
