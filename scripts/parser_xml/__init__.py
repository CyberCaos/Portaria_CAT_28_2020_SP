"""Parser de XML fiscal (NF-e/NFC-e) da skill. Origem: projeto RelatorioFiscalXml (C#/WPF), portado para Python."""
from .factory import LoteParseado, processar_arquivo, processar_entrada, processar_lote  # noqa: F401
from .modelos import EventoCancelamento, ItemFiscal, TributoValor  # noqa: F401
