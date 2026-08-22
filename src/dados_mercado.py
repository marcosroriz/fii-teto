"""Consultas e tratamento dos dados de mercado usados pelas páginas."""

from __future__ import annotations

from functools import lru_cache
from math import prod
from typing import Any

import requests
import yfinance as yf

from calculos import calcular_proventos

FALLBACK_SELIC = 14.0
FALLBACK_IPCA = 5.0


def _safe_number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def obter_indices() -> tuple[float, float, str]:
    """Obtém Selic meta e IPCA acumulado em 12 meses no Banco Central."""
    try:
        url = (
            "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/"
            "ultimos/{n}?formato=json"
        )
        headers = {"User-Agent": "fii-teto/1.0"}
        selic_data = requests.get(
            url.format(serie=432, n=1), headers=headers, timeout=5
        ).json()
        ipca_data = requests.get(
            url.format(serie=433, n=12), headers=headers, timeout=5
        ).json()
        selic = float(selic_data[-1]["valor"].replace(",", "."))
        taxas_ipca = [float(item["valor"].replace(",", ".")) / 100 for item in ipca_data]
        ipca = (prod(1 + taxa for taxa in taxas_ipca) - 1) * 100
        return round(selic, 2), round(ipca, 2), "Banco Central do Brasil"
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        return FALLBACK_SELIC, FALLBACK_IPCA, "valores de contingência"


@lru_cache(maxsize=128)
def obter_fii(symbol: str) -> dict[str, Any]:
    """Consulta cotação e proventos do FII no Yahoo Finance."""
    ticker = yf.Ticker(symbol)
    history = ticker.history(period="1y", auto_adjust=False)
    if history.empty:
        raise ValueError("O Yahoo Finance não retornou cotações para esse código.")

    preco = _safe_number(history["Close"].dropna().iloc[-1])
    if preco is None:
        raise ValueError("Não foi possível identificar a cotação atual.")

    proventos_12m, proventos_3m_anualizados = calcular_proventos(history)
    try:
        info = ticker.get_info()
    except Exception:
        info = {}
    nome = info.get("longName") or info.get("shortName") or symbol.removesuffix(".SA")
    return {
        "symbol": symbol.removesuffix(".SA"),
        "nome": nome,
        "preco": preco,
        "proventos_12m": proventos_12m,
        "proventos_3m_anualizados": proventos_3m_anualizados,
    }
