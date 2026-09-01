#!/usr/bin/env python
# coding: utf-8

# Testes unitários da página de comparação dos fundos imobiliários

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app  # noqa: F401 - inicializa o Dash antes de importar a página
import tema
from pages import comparacao


def resultado_fii(symbol: str, dy: float) -> dict:
    return {
        "symbol": symbol,
        "nome": f"Fundo {symbol}",
        "preco": 100.0,
        "proventos": dy,
        "dy": dy,
    }


class ComparacaoTest(unittest.TestCase):
    def test_taxa_selic_liquida_desconta_ir_e_anualiza(self):
        esperado = ((1 + ((1.14 ** (1 / 12) - 1) * 0.775)) ** 12 - 1) * 100

        self.assertAlmostEqual(comparacao.taxa_selic_liquida(14), esperado)

    def test_taxa_poupanca_acima_de_85_por_cento(self):
        esperado = ((1 + (0.5 + 0.1693) / 100) ** 12 - 1) * 100

        self.assertAlmostEqual(comparacao.taxa_poupanca(14), esperado)

    def test_taxa_poupanca_ate_85_por_cento(self):
        mensal_selic = (1 + (8.5 * 0.7) / 100) ** (1 / 12) - 1
        esperado = ((1 + mensal_selic + 0.1693 / 100) ** 12 - 1) * 100

        self.assertAlmostEqual(comparacao.taxa_poupanca(8.5), esperado)

    def test_grafico_ordena_fundos_e_aplica_cores_por_faixa(self):
        resultados = [
            resultado_fii("ERRO11", 7.5),
            resultado_fii("SUCESSO11", 11.0),
            resultado_fii("NULL11", 6.0),
            resultado_fii("ALERTA11", 9.0),
        ]

        figura = comparacao.criar_grafico(resultados, 10.0, 7.0, 8.0)

        self.assertEqual(list(figura.data[0].text), ["SUCESSO11", "ALERTA11", "ERRO11", "NULL11"])
        self.assertEqual(
            list(figura.data[0].marker.color),
            [tema.COR_SUCESSO, tema.COR_ALERTA, tema.COR_ERRO, tema.COR_NULL],
        )

    def test_grafico_adiciona_as_tres_linhas_com_cores_do_tema(self):
        figura = comparacao.criar_grafico([resultado_fii("FII11", 9.0)], 10.0, 7.0, 8.0)

        self.assertEqual(len(figura.layout.shapes), 3)
        self.assertEqual(
            [linha.line.color for linha in figura.layout.shapes],
            [tema.COR_SUCESSO, tema.COR_ERRO, tema.COR_ALERTA],
        )
        self.assertEqual([linha.y0 for linha in figura.layout.shapes], [10.0, 7.0, 8.0])

    def test_grafico_adiciona_linha_da_poupanca_com_cor_null(self):
        figura = comparacao.criar_grafico(
            [resultado_fii("FII11", 9.0)], 10.0, 7.0, 8.0, 8.33
        )

        self.assertEqual(len(figura.layout.shapes), 4)
        self.assertEqual(figura.layout.shapes[-1].line.color, tema.COR_NULL)
        self.assertEqual(figura.layout.shapes[-1].y0, 8.33)
        self.assertIn("Poupança", figura.layout.annotations[-1].text)

    def test_grafico_suporta_mais_de_dez_fundos(self):
        resultados = [resultado_fii(f"FII{indice:02d}", 8 + indice / 10) for indice in range(15)]

        figura = comparacao.criar_grafico(resultados, 10.0, 7.0, 8.0)

        self.assertEqual(len(figura.data[0].x), 15)
        self.assertEqual(len(figura.data[0].y), 15)

    def test_comparacao_exige_ao_menos_um_ticker(self):
        figura, resumo, fonte, mensagem, erro_aberto = comparacao.comparar_tickers(None, [])

        self.assertEqual(len(figura.data), 0)
        self.assertEqual(resumo, "")
        self.assertEqual(fonte, "")
        self.assertIn("ao menos um ticker", mensagem)
        self.assertTrue(erro_aberto)

    @patch.object(comparacao, "obter_indices", return_value=(14.0, 5.0, "fonte teste"))
    @patch.object(comparacao, "obter_fii")
    def test_callback_compara_mais_de_dez_tickers_sem_erro(self, obter_fii, _obter_indices):
        obter_fii.side_effect = lambda symbol: {
            "symbol": symbol.removesuffix(".SA"),
            "nome": symbol,
            "preco": 100.0,
            "proventos_3m_anualizados": 10.0,
        }
        symbols = [f"FII{indice:02d}.SA" for indice in range(12)]

        figura, resumo, fonte, mensagem, erro_aberto = comparacao.comparar_tickers(None, symbols)

        self.assertEqual(len(figura.data[0].y), 12)
        self.assertEqual(len(figura.layout.shapes), 4)
        self.assertEqual(figura.layout.shapes[-1].line.color, tema.COR_NULL)
        self.assertIsNotNone(resumo)
        self.assertIn("fonte teste", fonte)
        self.assertIn("TR mensal 0.1693%", fonte)
        self.assertEqual(mensagem, "")
        self.assertFalse(erro_aberto)


if __name__ == "__main__":
    unittest.main()
