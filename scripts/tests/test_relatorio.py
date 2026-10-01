import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gerar_relatorio as gr


def test_data_br():
    assert gr.data_br('2025-12-19') == '19/12/2025'
    assert gr.data_br('2025-12-19 00:00:00') == '19/12/2025'
    assert gr.data_br('') == ''


def test_num_formato_brasileiro():
    assert gr.num(1234567.891, 2) == '1.234.567,89'
    assert gr.num(50) == '50'
