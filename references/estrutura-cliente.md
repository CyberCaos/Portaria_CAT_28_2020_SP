# Estrutura da pasta do cliente

Gerada por `scripts/preparar_cliente.py`. Uma pasta por cliente, com o nome do cliente (caracteres inválidos no Windows são removidos).

| Item | Conteúdo | Observação |
|---|---|---|
| `estoque/` | cópia das posições recebidas (`estoque dd.mm.aaaa.xls`) | extraídas do zip/pasta do pacote |
| `relatorio_parser/entrada_consolidada.xlsx` | abas Resumo, Compras, Estoque, Estoque rejeitadas, Erros XML, Avisos XML, Eventos | Resumo traz os alertas; os BLOQUEANTE impedem o cálculo |
| `relatorio_parser/compras.csv`, `estoque.csv`, `intake_resumo.json` | os mesmos dados, para reprocessar | CSV UTF-8 com `;` |
| `relatorio_parser/trilha_levantamento.xlsx` | Triagem estoque, Localização, Alocação de notas, Fora do crédito, Uso de notas, Premissas | trilha técnica e insumo do PDF |
| `resultado_levantamento.xlsx` | abas Resumo (com premissas), Anexo II (notas selecionadas), Resumo por produto, Resumo por competência, Pendências | nasce **vazio** (`preparar_cliente.py`); `python scripts/levantamento.py <pasta do cliente>` preenche todas as abas |
| `relatorio_levantamento.pdf` | relatório para o cliente | `python scripts/gerar_relatorio.py <pasta do cliente>` |
| `enquadramento_reducao.csv` | produtos com redução de BC: `tipo` (EAN, CEST ou NCM), `codigo`, `descricao`, `ncm`, `cest`, `p_red_bc`, `origem_reducao`, `reducao` (`aplicavel` ou `nao_aplicavel`), `dispositivo`, `justificativa`, `fonte` (`automatico`, `analise` ou `usuario`) | criado pelo levantamento sempre que há nota com redução: decisões automáticas pelo RICMS/SP e linhas vazias para análise. Reescrito a cada rodada: as automáticas são refeitas; as do usuário/análise e as análises em andamento são preservadas; automática editada pelo usuário vira regra dele |
| `identidade_cat68.csv` | mercadorias sem identidade confirmada no item da CAT 68: `ean`, `descricao`, `anexo`, `item`, `descricao_legal`, `motivo`, `confirmado` (`sim`/`nao`), `evidencia_tipo`, `evidencia_fonte`, `apresentacao_confirmada`, `justificativa`, `fonte` | gerado pelo levantamento; a análise preenche; preservado nas rodadas seguintes |
| `entradas.csv` (opcional) | `chave;data_entrada;origem` (EFD C100, livro de entradas, manifestação) | evidência da entrada; entrada registrada na vigência deixa a nota fora |
| `relatorio_parser/ponte_reconciliacao.xlsx` | Resumo, Por motivo, Por produto, Por linha de nota | `python scripts/reconciliar.py <pasta> --anterior-total <valor>` |
| `cliente.json` / `LEIAME.txt` | nome, CNPJ, regime e origem (informado ou INFERIDO), origens dos XML, estoques, alertas | |

**Regra do modelo vazio.** `resultado_levantamento.xlsx` nasce sem nenhuma linha de dado; só `levantamento.py` o preenche, com dados reais do cliente. Não preencher com valores de teste ou estimativas. O levantamento também atualiza o `LEIAME.txt` (troca a linha "MODELO VAZIO" pela situação e pelo crédito apurado).

**Regime.** Informado pelo usuário (`--regime`) prevalece. Sem ele, `--xml-proprios` infere pelas notas emitidas pela empresa (amostra por pasta; CRT 1 = Simples, 2 = Simples com excesso de sublimite, 3 = regime normal; CF-e-SAT usa cRegTrib). Mistura de regimes = sem conclusão automática.

## Caso piloto

DROGARIA EXEMPLO LTDA (Simples Nacional; pacote com 2.755 NF-e de terceiros e 3 posições de estoque) foi o cliente de desenvolvimento. Os resultados dele **não** ficam registrados nas referências: mudam a cada ajuste de regra e não servem de gabarito. Para conferir, rode a skill no pacote e compare com a execução anterior.
