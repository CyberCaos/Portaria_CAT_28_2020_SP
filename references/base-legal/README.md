# Base documental — Portaria CAT 28/2020 (SP)

Baixado em 2026-09-30 do portal oficial da SEFAZ-SP (Legislação Tributária).

| Arquivo | Fonte |
|---|---|
| `portaria-cat-28-2020.html/.txt` | https://legislacao.fazenda.sp.gov.br/Paginas/Portaria-CAT-28-de-2020.aspx |
| `Portaria-SRE-65-de-2025.html/.txt` | https://legislacao.fazenda.sp.gov.br/Paginas/Portaria-SRE-65-de-2025.aspx (parcelas de crédito: 12 -> 24) |
| `Portaria-SRE-7-de-2026.html/.txt` | https://legislacao.fazenda.sp.gov.br/Paginas/Portaria-SRE-7-de-2026.aspx (volta para 12 parcelas, efeitos desde 01/01/2026) |

- `.html` = página original (íntegra, evidência). `.txt` = texto extraído para consulta/busca.
- Portaria CAT 28, de 19-03-2020 (DOE 20-03-2020; republicada 24-03-2020).
- Atenção: o `.txt` do ato principal traz as redações do art. 3º, § 2º, item 2 (histórico) lado a lado: vigente = 12 parcelas (SRE 7/26).
- Exclusão da ST (crédito): art. 3º a 4º, Anexos I a V. Inclusão (débito): art. 5º, Anexos VI e VII.

## Portaria CAT 68/2019 — produtos revogados (ST)

Relação de mercadorias sujeitas à ST com retenção antecipada. Base para identificar **quais produtos saíram da ST e quando** (data de revogação = início da exclusão).

| Arquivo | Conteúdo |
|---|---|
| `portaria-cat-68-2019.html/.txt` | Consolidado oficial (íntegra, com itens/anexos revogados e redações anteriores) — https://legislacao.fazenda.sp.gov.br/Paginas/Portaria-CAT-68-de-2019.aspx |
| `cat68-2019-produtos-revogados.xlsx` | **Planilha de trabalho**: abas *Itens revogados* (481), *Anexos revogados* (14), *Atos revogadores*, *Leia-me* |
| `cat68-2019-produtos-revogados.csv` | Mesma lista de itens (UTF-8, separador `;`) — lido por `scripts/produtos_excluidos.py` |
| `cat68-2019-itens-vigentes.csv` | 277 itens que continuam na ST (detecta CEST ainda vigente) |
| `atos-revogadores/` | Portarias que revogaram (CAT-57/21, CAT-91/21, SRE-18/22, SRE-69/22, SRE-64/25, SRE-94/25, SRE-9/26, SRE-19/26, SRE-20/26, SRE-34/26) — `.html` + `.txt` |

- Gerada por `scripts/base/parse_cat68.py` + `scripts/base/build_cat68_revogados.py` (raiz da skill) (reprodutível a partir do `.html`).
- Conferência: contagem de itens por ato bate com as listas de itens/anexos de cada portaria revogadora.
- Datas de vigência conferidas em cada ato. Revogações com vigência após 30/09/2026 (SRE-34/26, 01/10/2026) constam como "futura".
- Página consolidada mostrava data 06/07/2026: conferir atos posteriores antes de fechar levantamentos.
