"""Calculos financeiros puros usados pela calculadora."""

from __future__ import annotations

ALIQUOTA_IR = 22.5


def calcular_rendimentos_fii(
    preco: float, proventos_12m: float, aliquota_ir: float = ALIQUOTA_IR
) -> dict[str, float]:
    """Calcula DY, reinvestimento e equivalencia bruta a partir do FII."""
    if preco <= 0:
        raise ValueError("O preco da cota precisa ser maior que zero.")
    if proventos_12m < 0:
        raise ValueError("Os proventos nao podem ser negativos.")
    fator_liquido_ir = 1 - aliquota_ir / 100
    if fator_liquido_ir <= 0:
        raise ValueError("A aliquota de IR precisa ser menor que 100%.")

    dy_decimal = proventos_12m / preco
    dy_mensal_decimal = dy_decimal / 12
    retorno_fii_decimal = (1 + dy_mensal_decimal) ** 12 - 1
    taxa_mensal_bruta_equivalente = dy_mensal_decimal / fator_liquido_ir
    taxa_bruta_equivalente_fii = (
        (1 + taxa_mensal_bruta_equivalente) ** 12 - 1
    ) * 100
    return {
        "dy": dy_decimal * 100,
        "dy_mensal_decimal": dy_mensal_decimal,
        "retorno_fii": retorno_fii_decimal * 100,
        "taxa_mensal_bruta_equivalente": taxa_mensal_bruta_equivalente,
        "taxa_bruta_equivalente_fii": taxa_bruta_equivalente_fii,
    }
