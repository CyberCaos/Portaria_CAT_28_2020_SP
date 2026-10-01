# Lançamento e escrituração do crédito

Fonte: Portaria CAT 28/2020, arts. 2º e 3º, Anexo III; Portarias SRE 65/25 e SRE 7/26. Textos em `base-legal/`.

## Antes do crédito
- Elaborar o relatório por mercadoria em arquivo digital (Anexo I, tabela A, no modelo do Anexo II) e manter pelo prazo do art. 202 do RICMS, para apresentação quando solicitado.
- Escriturar o Registro de Inventário com o estoque do fim do dia anterior ao início da vigência da exclusão. Quem escritura por EFD preenche o Bloco H conforme o Anexo III (abaixo).
- Quem **optar por não aproveitar** o crédito fica dispensado do procedimento (art. 1º, parágrafo único, 1).
- A SEFAZ pode divulgar procedimento específico por segmento (art. 1º, par. único, 2): verificar atos do segmento do produto.

## Contribuinte no RPA (art. 3º, §2º)
- Lançar no Registro de Apuração do ICMS (Bloco E da EFD), código de ajuste **SP020750**, quadro "Crédito do Imposto – Outros Créditos", com menção expressa à Portaria CAT 28/2020.
- **12 parcelas mensais, iguais e sucessivas**, a primeira na referência do mês de início da vigência da exclusão (redação da SRE 7/26, efeitos desde 01/01/2026; vigorou 24 parcelas pela SRE 65/25, de 01/10/2025).
- Transição SRE 7/26 (mercadorias excluídas pela SRE 64/25): se 1/24 foi lançado em janeiro e fevereiro/2026, permite lançamento complementar de 2/24 na referência de março/2026; a partir de março/2026, lançar 1/12 por mês.
- Exclusões com início de vigência anterior a 2026 ou outros casos de transição: conferir o texto vigente à época no histórico de redações (`base-legal/portaria-cat-28-2020.txt`).

## Contribuinte do Simples Nacional (art. 3º, §3º)
- Compensar deduzindo do ICMS devido no Simples, **no mês posterior** ao da exclusão, usando o campo "redução da base de cálculo" do PGDAS-D.
- Se o crédito superar o ICMS do mês, a diferença compensa nos meses seguintes.

## Parcela do inciso XVI do art. 2º do RICMS
A exclusão da ST **não** enseja compensar a parcela do imposto do inciso XVI do art. 2º do RICMS incluída na retenção/antecipação (Portaria CAT 75/08) — art. 3º, §4º. Não incluir essa parcela no cálculo. **Na skill:** a parcela não é identificável na NF-e e não é deduzida automaticamente; fica registrada como premissa "confirmar" na planilha e no PDF. Se algum produto do levantamento estiver sujeito a ela, ajustar o crédito antes do lançamento.

## Bloco H da EFD (Anexo III)
| Registro / campo | Conteúdo na exclusão da ST |
|---|---|
| H005 campo 04 | motivo do inventário `02` — mudança de forma de tributação da mercadoria (ICMS) |
| H010 campo 04 | quantidade em estoque |
| H010 campo 05 | valor unitário médio ponderado da mercadoria (Anexo I, tabela A, item 17) |
| H020 campo 03 | valor unitário médio ponderado da BC da ST (item 18) |
| H020 campo 04 | valor unitário do crédito (item 19) |

## Nota fiscal complementar (art. 4º, II)
Se o fornecedor não lançou a BC da ST ou lançou a menor, ele pode emitir NF complementar só com os campos a complementar (par. único). Sem a BC na NF, o crédito do item é zero até a regularização; listar essas notas como oportunidade.
