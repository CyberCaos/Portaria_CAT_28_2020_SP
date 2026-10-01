"""Modelos de dados do parser (porte de RelatorioFiscalXml/Models/*.cs, com campos extras para o levantamento de ST)."""
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

ZERO = Decimal(0)
NFE, NFCE = 'NFe', 'NFCe'
NORMAL, CANCELADA = 'Normal', 'Cancelada'


@dataclass(frozen=True)
class TributoValor:
    base: Decimal = ZERO
    aliquota: Decimal = ZERO
    valor: Decimal = ZERO


@dataclass(frozen=True)
class ItemFiscal:
    arquivo: str
    chave: str
    modelo: str
    numero: str
    serie: str
    data_emissao: Optional[datetime]
    sequencia: int
    emitente_documento: str
    emitente_nome: str
    destinatario_documento: str
    destinatario_nome: str
    codigo_produto: str
    ean: str
    ncm: str
    cest: str
    descricao: str
    cfop: str
    unidade: str                 # uCom
    quantidade: Decimal          # qCom
    valor_item: Decimal          # vProd
    frete: Decimal
    seguro: Decimal
    outras_despesas: Decimal
    desconto: Decimal
    valor_contabil: Decimal
    icms: TributoValor
    icms_st: TributoValor
    ipi: TributoValor
    pis: TributoValor
    cofins: TributoValor
    # ICMS-ST retido em etapa anterior (CST 60/70, CSOSN 500): base/alíquota/valor apenas repassados neste documento
    icms_st_retido_ant: TributoValor
    fcp_st_retido_ant: TributoValor
    cst_icms: str = ''
    orig_icms: str = ''          # origem da mercadoria (0 nacional; 1, 2, 3, 8 importado/conteúdo importado > 40%)
    p_red_bc: Decimal = ZERO
    p_red_bc_st: Decimal = ZERO
    emitente_uf: str = ''
    destinatario_uf: str = ''
    situacao: str = NORMAL
    # --- extras (não existiam no projeto original; necessários ao levantamento CAT 28/2020) ---
    crt_emitente: str = ''       # 1/2 = Simples Nacional, 3 = regime normal
    unidade_trib: str = ''       # uTrib
    quantidade_trib: Decimal = ZERO  # qTrib
    v_icms_substituto: Decimal = ZERO  # vICMSSubstituto (ICMS próprio do substituto, CST 60/CSOSN 500)
    tp_nf: str = ''              # 0 = entrada, 1 = saída (do ponto de vista do emitente)
    fin_nfe: str = ''            # 1 normal, 2 complementar, 3 ajuste, 4 devolução
    nat_op: str = ''
    c_stat: str = ''             # cStat do protocolo de autorização (100/150 = autorizada)
    protocolo: str = ''
    tp_amb: str = ''             # 1 produção, 2 homologação
    indicador_ie_dest: str = ''
    ean_trib: str = ''           # cEANTrib (EAN da unidade tributável; difere do cEAN quando o item é caixa/pacote)
    p_fcp_st: Decimal = ZERO     # pFCPST (FCP da ST retida na própria nota, CST 10/70)
    v_fcp_st: Decimal = ZERO     # vFCPST
    v_bc_fcp_st: Decimal = ZERO  # vBCFCPST (base do FCP da ST na própria nota; pode diferir de vBCST)
    data_saida_entrada: str = ''  # dhSaiEnt/dSaiEnt informado pelo EMITENTE (não comprova o recebimento pelo destinatário)
    ref_nfe: str = ''            # chaves referenciadas (NFref/refNFe), separadas por "|": liga complementar/devolução à original

    def como_cancelada(self) -> 'ItemFiscal':
        """Zera valores (monetários/tributários) e marca Cancelada; mantém identificação (a nota existiu)."""
        z = TributoValor()
        return replace(self, situacao=CANCELADA, valor_item=ZERO, frete=ZERO, seguro=ZERO, outras_despesas=ZERO,
                       desconto=ZERO, valor_contabil=ZERO, icms=z, icms_st=z, ipi=z, pis=z, cofins=z,
                       icms_st_retido_ant=z, fcp_st_retido_ant=z, v_icms_substituto=ZERO)

    @property
    def autorizada(self) -> bool:
        """True se há protocolo com cStat de uso autorizado. Sem protocolo (root NFe solto) = indeterminado."""
        return self.c_stat in ('100', '150')


@dataclass(frozen=True)
class EventoCancelamento:
    ch_nfe: str
    dh_evento: Optional[datetime]
    nome_arquivo: str


@dataclass
class ResultadoArquivo:
    caminho: str
    nome: str
    itens: List[ItemFiscal] = field(default_factory=list)
    erro: Optional[str] = None
    evento: Optional[EventoCancelamento] = None
    aviso: Optional[str] = None   # ignorado de propósito (ex.: resNFe), diferente de erro
