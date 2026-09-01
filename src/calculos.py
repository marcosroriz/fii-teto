#!/usr/bin/env python
# coding: utf-8

# Cálculos financeiros usados pelas ferramentas de análise

from __future__ import annotations

import pandas as pd

ALIQUOTA_IR = 22.5


def calcular_proventos(history) -> tuple[float, float]:
    """Retorna proventos de 12 meses e dos últimos 3 meses anualizados."""
    dividendos = history.get("Dividends")
    if dividendos is None or dividendos.empty:
        return 0.0, 0.0

    dividendos = dividendos.fillna(0)
    proventos_12m = float(dividendos.sum())
    inicio_3m = dividendos.index.max() - pd.DateOffset(months=3)
    proventos_3m_anualizados = float(dividendos.loc[dividendos.index >= inicio_3m].sum()) * 4
    return proventos_12m, proventos_3m_anualizados


def calcular_historico_trimestral(history: pd.DataFrame, data_inicio, data_fim) -> pd.DataFrame:
    """Calcula o DY anualizado com os três proventos mais recentes."""
    inicio = pd.Timestamp(data_inicio).normalize()
    fim = pd.Timestamp(data_fim).normalize()
    if inicio > fim:
        raise ValueError("A data inicial precisa ser anterior à data final.")
    if history.empty or "Close" not in history:
        raise ValueError("O histórico precisa conter cotações de fechamento.")

    historico = history.copy().sort_index()
    historico.index = pd.to_datetime(historico.index).tz_localize(None)
    dividendos = historico.get("Dividends", pd.Series(0.0, index=historico.index, dtype=float)).fillna(0)

    primeira_data = pd.offsets.QuarterEnd(startingMonth=12).rollforward(inicio)
    datas = list(pd.date_range(primeira_data, fim, freq=pd.offsets.QuarterEnd()))
    if not datas or datas[-1] != fim:
        datas.append(fim)

    pontos = []
    for data in datas:
        cotacoes = historico.loc[historico.index <= data, "Close"].dropna()
        if cotacoes.empty:
            continue
        preco = float(cotacoes.iloc[-1])
        if preco <= 0:
            continue
        proventos_recentes = dividendos.loc[
            (dividendos.index <= data) & (dividendos > 0)
        ].tail(3)
        quantidade_proventos = len(proventos_recentes)
        if quantidade_proventos < 3:
            continue
        proventos_trimestre = float(proventos_recentes.sum())
        pontos.append(
            {
                "data": data,
                "preco": preco,
                "proventos_trimestre": proventos_trimestre,
                "quantidade_proventos": quantidade_proventos,
                "dy_anualizado": proventos_trimestre * 4 / preco * 100,
            }
        )
    return pd.DataFrame(pontos)


def calcular_rendimentos_fii(preco: float, proventos_12m: float, aliquota_ir: float = ALIQUOTA_IR) -> dict[str, float]:
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
    taxa_bruta_equivalente_fii = ((1 + taxa_mensal_bruta_equivalente) ** 12 - 1) * 100
    return {
        "dy": dy_decimal * 100,
        "dy_mensal_decimal": dy_mensal_decimal,
        "retorno_fii": retorno_fii_decimal * 100,
        "taxa_mensal_bruta_equivalente": taxa_mensal_bruta_equivalente,
        "taxa_bruta_equivalente_fii": taxa_bruta_equivalente_fii,
    }


def calcular_simulacao_fii(
    preco: float,
    proventos: float,
    indice: float,
    premio: float,
    modo: str,
    investimento: float,
    aliquota_ir: float = ALIQUOTA_IR,
) -> dict[str, float | bool | None]:
    """Consolida os cálculos financeiros usados pela página principal."""
    if modo not in {"selic", "ipca"}:
        raise ValueError("O modo de cálculo deve ser SELIC ou IPCA.")

    fator_liquido_ir = 1 - aliquota_ir / 100
    taxa_referencia_bruta = indice + premio
    if taxa_referencia_bruta <= 0:
        raise ValueError("A taxa de referência bruta deve ser maior que zero.")

    taxa_referencia_mensal_bruta = None
    if modo == "selic":
        taxa_referencia_mensal_bruta = (1 + taxa_referencia_bruta / 100) ** (1 / 12) - 1
        taxa_mensal_liquida = taxa_referencia_mensal_bruta * fator_liquido_ir
        taxa_referencia_liquida = ((1 + taxa_mensal_liquida) ** 12 - 1) * 100
    else:
        taxa_referencia_liquida = taxa_referencia_bruta * fator_liquido_ir

    rendimentos = calcular_rendimentos_fii(preco, proventos, aliquota_ir)
    taxa_alvo_mensal = (1 + taxa_referencia_liquida / 100) ** (1 / 12) - 1
    preco_teto = proventos / (12 * taxa_alvo_mensal)
    valor_final_fii = investimento * (1 + rendimentos["retorno_fii"] / 100)
    valor_final_referencia = investimento * (1 + taxa_referencia_liquida / 100)

    return {
        **rendimentos,
        "taxa_referencia_bruta": taxa_referencia_bruta,
        "taxa_referencia_mensal_bruta": taxa_referencia_mensal_bruta,
        "taxa_referencia_liquida": taxa_referencia_liquida,
        "taxa_alvo_fii": taxa_referencia_liquida,
        "preco_teto": preco_teto,
        "valor_final_fii": valor_final_fii,
        "valor_final_referencia": valor_final_referencia,
        "lucro_fii": valor_final_fii - investimento,
        "lucro_referencia": valor_final_referencia - investimento,
        "margem_preco_teto": (preco_teto / preco - 1) * 100,
        "abaixo_preco_teto": preco <= preco_teto,
    }
