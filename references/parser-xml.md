# Parser de XML (NF-e / NFC-e)

Origem: projeto **RelatorioFiscalXml** (C#/WPF, projeto interno de origem), portado para Python em `scripts/parser_xml/`. Os testes do projeto original (fixtures e expectativas de NfeNfceParser/ParserFactory) foram reproduzidos em `scripts/tests/test_parser_xml.py`.

## O que foi portado
| Original (C#) | Python | Observação |
|---|---|---|
| `XmlHelpers.cs` | `xmlhelpers.py` | sanitiza `&`/`<` soltos no texto; tolera bytes inválidos; data como escrita no XML (sem converter fuso); valores em `Decimal` |
| `DetectorXml.cs` + `ParserFactory.cs` | `factory.py` | detecta por elemento raiz + `<mod>`; erro por arquivo não derruba o lote |
| `NfeNfceParser.cs` + extractors ICMS/IPI/PIS/COFINS | `nfe.py` | um `ItemFiscal` por `<det>` |
| `EventoCancelamentoExtractor.cs` + `AplicadorEventosCancelamento.cs` | `nfe.py` / `factory.py` | evento 110111 zera valores da nota (mantém identificação); evento sem nota = órfão |
| `ItemFiscal`, `TributoValor`, `EventoCancelamento` | `modelos.py` | |

## O que foi acrescentado para o levantamento
`ean_trib` (`cEANTrib`, EAN da unidade tributável: permite achar o produto quando a nota vende caixa e o estoque guarda a unidade), `crt_emitente` (Simples × regime normal), `c_stat`/`protocolo` (autorização), `tp_nf`, `fin_nfe` (devolução/complementar), `nat_op`, `uTrib`/`qTrib`, `vICMSSubstituto`, `tpAmb`, `indIEDest`; dedupe por chave (mantém a versão com protocolo autorizado); leitura de zips (aninhados, com proteção zip-slip); contagem de duplicatas, cancelamentos e órfãos.

## O que NÃO foi portado
CF-e-SAT (`CfeSatParser`, `CfeCancExtractor`), CT-e (`CteParser`), IBS/CBS e a interface WPF/relatório Excel original. Compras para revenda com ST retida vêm de NF-e; se o usuário enviar esses tipos, eles caem em "Erros XML" com mensagem de tipo não suportado. `resNFe` (resumo) é ignorado com aviso: é preciso o XML completo.

## Regras de leitura que importam para o crédito
- `vBCSTRet`, `pST`, `vICMSSTRet`, `vBCFCPSTRet` vêm do primeiro filho de `<ICMS>` (ICMS60, ICMSSN500, ICMSST...). Sem base de ST identificável no item (`vBCSTRet` na CST 60/CSOSN 500, `vBCST` na CST 10/30/70) o crédito é zero (CAT 28/20, art. 4º, I). Também são lidos `vICMS`/`vBC` (ICMS próprio) e `vFCPST`/`vFCPSTRet` (FCP da ST): provas das fórmulas com redução.
- `cst` = CST (regime normal) ou CSOSN (Simples do emitente). CST 60 / CSOSN 500 indicam ST retida anteriormente.
- `orig` = origem da mercadoria (N11). 1, 2, 3 e 8 = importado ou conteúdo importado > 40%: alíquota interestadual 4%.
- Nota sem `protNFe` (root `NFe` solto) tem `c_stat` vazio: autorização indeterminada — sinalizar, não descartar em silêncio.
- Se o mesmo XML aparece várias vezes (pastas repetidas, nfeProc e NFe), conta uma vez por chave.

## Como estender
Novo tipo de documento: criar `suporta(root, modelo)` + `parse(root, nome)` no módulo novo, registrar o ramo em `factory.processar_arquivo`, e copiar um XML real sanitizado (sem dados sensíveis) para `scripts/tests/fixtures/` com teste.
