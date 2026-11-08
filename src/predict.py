from __future__ import annotations

import logging
import pickle
from pathlib import Path

import pandas as pd
from prophet import Prophet

logging.getLogger("prophet").setLevel(logging.WARNING)
_cmdstan = logging.getLogger("cmdstanpy")
_cmdstan.setLevel(logging.WARNING)
_cmdstan.addHandler(logging.NullHandler())

BASE = Path(__file__).resolve().parent.parent
DATA_XLSX = BASE / "data" / "datos_energia_combinado.xlsx"
MODEL_PATH = BASE / "models" / "modelo_prophet_energia.pkl"
UNIVERSIDAD = "UPV"
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
COLUMNAS_MES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
HORIZONTE = 12

_HIPERPARAMETROS = (
    "growth", "changepoint_prior_scale", "changepoint_range",
    "seasonality_mode", "seasonality_prior_scale", "holidays_prior_scale",
    "yearly_seasonality", "weekly_seasonality", "daily_seasonality",
    "interval_width", "mcmc_samples", "holidays",
)


def cargar_serie() -> pd.Series:
    """Serie mensual de consumo (kWh) de la universidad, indexada por Period."""
    if not DATA_XLSX.exists():
        raise FileNotFoundError(f"No se encuentra {DATA_XLSX}")
    df = pd.read_excel(DATA_XLSX)
    df.columns = df.columns.str.strip()
    uni = df[df["Uni"] == UNIVERSIDAD]
    if uni.empty:
        raise ValueError(f"El Excel no contiene datos de {UNIVERSIDAD}")
    larga = pd.melt(uni, id_vars=["Año"], value_vars=COLUMNAS_MES,
                    var_name="Mes", value_name="consumo")
    larga["Mes"] = larga["Mes"].str.strip()
    orden = {m: i + 1 for i, m in enumerate(COLUMNAS_MES)}
    larga["fecha"] = [
        pd.Period(f"{int(a)}-{orden[m]:02d}", freq="M")
        for a, m in zip(larga["Año"], larga["Mes"])
    ]
    larga = larga.dropna(subset=["consumo"]).drop_duplicates("fecha", keep="last")
    larga = larga.sort_values("fecha")
    if larga.empty:
        raise ValueError("El Excel no contiene filas válidas")
    return pd.Series(
        larga["consumo"].astype(float).values, index=larga["fecha"], name="consumo"
    )


def cargar_modelo():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"No se encuentra {MODEL_PATH}")
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def _como_df(periodos) -> pd.DataFrame:
    return pd.DataFrame({"ds": [p.to_timestamp() for p in periodos]})


def _modelo_nuevo(base) -> Prophet:
    return Prophet(**{k: getattr(base, k) for k in _HIPERPARAMETROS})


def _salida(fechas, filas) -> pd.DataFrame:
    return pd.DataFrame({
        "fecha": fechas,
        "yhat": filas["yhat"].astype(float).values,
        "yhat_lower": filas["yhat_lower"].astype(float).values,
        "yhat_upper": filas["yhat_upper"].astype(float).values,
    })


def predecir_base(modelo, periodo: pd.Period) -> dict:
    fila = modelo.predict(_como_df([periodo])).iloc[0]
    return {
        "yhat": float(fila["yhat"]),
        "yhat_lower": float(fila["yhat_lower"]),
        "yhat_upper": float(fila["yhat_upper"]),
    }


def horizonte_base(modelo, periodos: list) -> pd.DataFrame:
    return _salida(periodos, modelo.predict(_como_df(periodos)))


def construir_escenario(serie: pd.Series, puntos: list) -> pd.Series:
    """Serie real con los meses inventados sobrescritos o añadidos."""
    esc = serie.copy()
    for p in puntos:
        esc[p["periodo"]] = p["valor"]
    return esc.sort_index()


def ajustar_escenario(base, escenario: pd.Series) -> Prophet:
    """Reentrena el modelo con la historia + meses inventados."""
    df = pd.DataFrame({
        "ds": [p.to_timestamp() for p in escenario.index],
        "y": escenario.values,
    }).dropna()
    modelo = _modelo_nuevo(base)
    modelo.fit(df)
    return modelo


def etiqueta_periodo(p: pd.Period) -> str:
    return f"{MESES[p.month - 1]} {p.year}"


def etiqueta_corta(p: pd.Period) -> str:
    return f"{p.year}-{p.month:02d}"


def formato(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")
