import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calculos import calcular_proventos, calcular_rendimentos_fii


class CalculosFiiTest(unittest.TestCase):
    def test_proventos_dos_ultimos_tres_meses_sao_anualizados(self):
        indice = pd.to_datetime(
            [
                "2025-01-15",
                "2025-05-15",
                "2025-06-15",
                "2025-07-15",
                "2025-08-15",
                "2025-08-22",
            ]
        ).tz_localize("America/Sao_Paulo")
        history = pd.DataFrame(
            {"Dividends": [1.0, 2.0, 3.0, 4.0, 5.0, 0.0]},
            index=indice,
        )

        anual, tres_meses_ajustado = calcular_proventos(history)

        self.assertEqual(anual, 15.0)
        self.assertEqual(tres_meses_ajustado, 48.0)

    def test_exemplo_obrigatorio(self):
        resultado = calcular_rendimentos_fii(89.30, 9.84)

        self.assertAlmostEqual(resultado["dy"], 11.0190, places=3)
        self.assertAlmostEqual(resultado["dy_mensal_decimal"] * 100, 0.9183, places=3)
        self.assertAlmostEqual(resultado["retorno_fii"], 11.5929, places=3)
        self.assertAlmostEqual(resultado["taxa_mensal_bruta_equivalente"] * 100, 1.1848, places=3)
        self.assertAlmostEqual(resultado["taxa_bruta_equivalente_fii"], 15.1822, places=3)

    def test_equivalencia_nao_recebe_modo_indice_ou_premio(self):
        esperado = calcular_rendimentos_fii(89.30, 9.84)["taxa_bruta_equivalente_fii"]

        for _modo, _indice, _premio in (
            ("selic", 10, 0),
            ("selic", 18, 5),
            ("ipca", 4, 0),
            ("ipca", 10, 5),
        ):
            atual = calcular_rendimentos_fii(89.30, 9.84)["taxa_bruta_equivalente_fii"]
            self.assertEqual(atual, esperado)


if __name__ == "__main__":
    unittest.main()
