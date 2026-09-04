#!/usr/bin/env python
# coding: utf-8

# Testes unitários da página e dos cálculos do histórico trimestral

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app  # noqa: F401 - inicializa o Dash antes de importar a página
import tema
from calculos import calcular_historico_trimestral
from pages import historico


def pontos_historicos() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "data": pd.to_datetime(["2025-09-30", "2025-12-31"]),
            "preco": [100.0, 105.0],
            "proventos_trimestre": [2.0, 2.5],
            "dy_anualizado": [8.0, 9.5],
            "selic_liquida": [10.0, 11.0],
            "poupanca": [8.0, 8.1],
            "ipca_mais_sete_liquido": [7.0, 7.5],
            "ipca_mais_oito_liquido": [8.0, 8.5],
        }
    )


class HistoricoTest(unittest.TestCase):
    def test_calculo_trimestral_anualiza_proventos_e_inclui_data_final(self):
        indice = pd.date_range("2023-01-01", periods=13, freq="MS") + pd.Timedelta(days=14)
        history = pd.DataFrame({"Close": 100.0, "Dividends": 1.0}, index=indice)

        pontos = calcular_historico_trimestral(history, "2023-01-01", "2024-01-31")

        self.assertEqual(list(pontos["data"].dt.strftime("%Y-%m-%d")), [
            "2023-03-31", "2023-06-30", "2023-09-30", "2023-12-31", "2024-01-31"
        ])
        self.assertTrue((pontos["dy_anualizado"] == 12.0).all())
        self.assertTrue((pontos["quantidade_proventos"] == 3).all())

    def test_calculo_usa_tres_proventos_mesmo_quando_janela_tem_apenas_dois(self):
        indice = pd.to_datetime([
            "2026-05-29", "2026-06-30", "2026-07-31", "2026-09-01"
        ])
        history = pd.DataFrame(
            {
                "Close": [150.0, 151.0, 147.42, 147.0],
                "Dividends": [1.10, 1.10, 1.17, 0.0],
            },
            index=indice,
        )

        pontos = calcular_historico_trimestral(history, "2026-06-01", "2026-09-01")
        ultimo = pontos.iloc[-1]

        self.assertAlmostEqual(ultimo["proventos_trimestre"], 3.37)
        self.assertEqual(ultimo["quantidade_proventos"], 3)
        self.assertAlmostEqual(ultimo["dy_anualizado"], 3.37 * 4 / 147 * 100)

    def test_calculo_trimestral_rejeita_periodo_invertido(self):
        history = pd.DataFrame(
            {"Close": [100.0], "Dividends": [1.0]},
            index=pd.to_datetime(["2025-01-01"]),
        )

        with self.assertRaisesRegex(ValueError, "data inicial"):
            calcular_historico_trimestral(history, "2025-02-01", "2025-01-01")

    def test_indices_sao_alinhados_e_ipca_de_doze_meses_e_composto(self):
        pontos = pd.DataFrame(
            {
                "data": pd.to_datetime(["2025-12-31"]),
                "preco": [100.0],
                "proventos_trimestre": [2.0],
                "dy_anualizado": [8.0],
            }
        )
        selic = pd.Series([14.0], index=pd.to_datetime(["2025-12-30"]))
        ipca = pd.Series(1.0, index=pd.date_range("2025-01-01", periods=12, freq="MS"))

        resultado = historico.adicionar_indices(pontos, selic, ipca)

        ipca_12m = (1.01**12 - 1) * 100
        self.assertEqual(len(resultado), 1)
        self.assertAlmostEqual(resultado.iloc[0]["selic_liquida"], historico.taxa_selic_liquida(14))
        self.assertAlmostEqual(resultado.iloc[0]["poupanca"], historico.taxa_poupanca(14))
        self.assertAlmostEqual(resultado.iloc[0]["ipca_mais_sete_liquido"], (ipca_12m + 7) * 0.775)
        self.assertAlmostEqual(resultado.iloc[0]["ipca_mais_oito_liquido"], (ipca_12m + 8) * 0.775)

    def test_poupanca_usa_a_selic_correspondente_a_cada_tick(self):
        pontos = pd.DataFrame(
            {
                "data": pd.to_datetime(["2025-03-31", "2025-06-30"]),
                "preco": [100.0, 100.0],
                "proventos_trimestre": [2.0, 2.0],
                "dy_anualizado": [8.0, 8.0],
            }
        )
        selic = pd.Series(
            [10.0, 14.0],
            index=pd.to_datetime(["2025-03-30", "2025-06-29"]),
        )
        ipca = pd.Series(
            0.4,
            index=pd.date_range("2024-01-01", periods=18, freq="MS"),
        )

        resultado = historico.adicionar_indices(pontos, selic, ipca)

        self.assertAlmostEqual(
            resultado.iloc[0]["poupanca"], historico.taxa_poupanca(10.0)
        )
        self.assertAlmostEqual(
            resultado.iloc[1]["poupanca"], historico.taxa_poupanca(14.0)
        )
        self.assertNotEqual(
            resultado.iloc[0]["poupanca"], resultado.iloc[1]["poupanca"]
        )

    def test_indice_sem_doze_meses_de_ipca_e_descartado(self):
        pontos = pontos_historicos().iloc[[0]]
        selic = pd.Series([14.0], index=pd.to_datetime(["2025-09-30"]))
        ipca = pd.Series(1.0, index=pd.date_range("2025-01-01", periods=8, freq="MS"))

        resultado = historico.adicionar_indices(pontos, selic, ipca)

        self.assertTrue(resultado.empty)

    def test_grafico_usa_cores_do_tema_e_folga_de_dois_pontos(self):
        pontos = pontos_historicos()

        figura = historico.criar_grafico(pontos, "TEST11")

        self.assertEqual(len(figura.data), 5)
        self.assertEqual(
            [serie.line.color for serie in figura.data],
            [
                tema.PALETA_CORES[0],
                tema.COR_SUCESSO,
                tema.COR_NULL,
                tema.COR_ALERTA,
                tema.COR_ERRO,
            ],
        )
        self.assertEqual(list(figura.layout.yaxis.range), [5.0, 13.0])

    @patch.object(historico, "obter_historico_fii")
    @patch.object(historico, "obter_indices_historicos")
    @patch.object(historico, "calcular_historico_trimestral")
    def test_callback_monta_grafico_sem_consultas_reais(
        self, calcular_pontos, obter_indices, obter_fii
    ):
        calcular_pontos.return_value = pontos_historicos()[
            ["data", "preco", "proventos_trimestre", "dy_anualizado"]
        ]
        obter_fii.return_value = (pd.DataFrame({"Close": [100.0]}), "Fundo Teste")
        obter_indices.return_value = (
            pd.Series([14.0], index=pd.to_datetime(["2025-12-30"])),
            pd.Series(0.4, index=pd.date_range("2025-01-01", periods=12, freq="MS")),
        )

        figura, resumo, descricao, mensagem, erro_aberto = historico.carregar_historico(None, "TEST11.SA")

        self.assertEqual(len(figura.data), 5)
        self.assertIsNotNone(resumo)
        self.assertIn("Fundo Teste", descricao)
        self.assertEqual(mensagem, "")
        self.assertFalse(erro_aberto)

    @patch.object(historico, "obter_historico_fii", side_effect=ValueError("falha simulada"))
    def test_callback_exibe_erro_do_provedor(self, _obter_fii):
        figura, resumo, descricao, mensagem, erro_aberto = historico.carregar_historico(None, "TEST11.SA")

        self.assertEqual(len(figura.data), 0)
        self.assertEqual(resumo, "")
        self.assertEqual(descricao, "")
        self.assertIn("falha simulada", mensagem)
        self.assertTrue(erro_aberto)


if __name__ == "__main__":
    unittest.main()
