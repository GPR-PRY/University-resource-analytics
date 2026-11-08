from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from flask import Flask, render_template, request, session

import predict

app = Flask(__name__)
app.secret_key = "demo-consumo-energetico"
app.add_template_filter(predict.formato, "kwh")

COLORES = {"real": "#2563eb", "base": "#94a3b8", "inventado": "#d97706", "escenario": "#16a34a"}


def _error_html(exc: Exception) -> str:
    return (
        "<div class='aviso'><h2>No se puede predecir todavía</h2>"
        f"<p>{exc}</p>"
        "<p>Hacen falta <code>data/datos_energia_combinado.xlsx</code> "
        "y <code>models/modelo_prophet_energia.pkl</code>.</p></div>"
    )


def _puntos_sesion() -> list:
    return [
        {**p, "periodo": pd.Period(p["fecha"], freq="M")}
        for p in session.get("puntos", [])
    ]


def _guardar_puntos(puntos: list) -> None:
    session["puntos"] = [
        {"fecha": p["fecha"], "valor": p["valor"], "tipo": p["tipo"]} for p in puntos
    ]


def _periodos(serie: pd.Series) -> list:
    """Meses seleccionables: histórico + horizonte de previsión base."""
    opciones = [predict.etiqueta_corta(p) for p in serie.index]
    for i in range(1, predict.HORIZONTE + 1):
        opciones.append(predict.etiqueta_corta(serie.index[-1] + i))
    return opciones


def _rango_escenario(serie: pd.Series, puntos: list) -> list:
    base_fin = serie.index[-1] + predict.HORIZONTE
    fin = max(base_fin, max(p["periodo"] for p in puntos))
    ini = min(p["periodo"] for p in puntos)
    return [ini + i for i in range((fin - ini).n + 1)]


def _figura(serie, base_h, esc_h, puntos, predicho) -> str:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[str(p) for p in serie.index], y=serie.values, mode="lines",
        name="Real", line=dict(color=COLORES["real"], width=2),
    ))
    if base_h is not None and len(base_h):
        x = [str(p) for p in base_h["fecha"]]
        fig.add_trace(go.Scatter(
            x=x, y=base_h["yhat_upper"], mode="lines", line=dict(width=0),
            showlegend=False, legendgroup="base", hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=x, y=base_h["yhat_lower"], mode="lines", line=dict(width=0),
            fill="tonexty", fillcolor="rgba(148,163,184,.25)",
            name="Incertidumbre 80%", legendgroup="base", hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=x, y=base_h["yhat"], mode="lines", name="Previsión modelo",
            line=dict(color=COLORES["base"], width=2, dash="dot"),
        ))
    if esc_h is not None and len(esc_h):
        fig.add_trace(go.Scatter(
            x=[str(p) for p in esc_h["fecha"]], y=esc_h["yhat"], mode="lines",
            name="Escenario", line=dict(color=COLORES["escenario"], width=2, dash="dash"),
        ))
    if puntos:
        fig.add_trace(go.Scatter(
            x=[p["fecha"] for p in puntos], y=[p["valor"] for p in puntos],
            mode="markers", name="Inventado",
            marker=dict(color=COLORES["inventado"], size=11),
        ))
    if predicho:
        fig.add_trace(go.Scatter(
            x=[predicho["fecha"]], y=[predicho["valor"]], mode="markers",
            name="Siguiente mes",
            marker=dict(color=COLORES["escenario"], size=13, symbol="diamond-open",
                        line=dict(color=COLORES["escenario"], width=2)),
        ))
    fig.update_layout(
        height=400, margin=dict(l=50, r=20, t=30, b=40),
        xaxis_title="Mes", yaxis_title="Consumo (kWh)",
        yaxis=dict(tickformat=",.0f"),
        legend=dict(orientation="h", y=1.08), hovermode="x unified",
    )
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": False})


def _error(exc, mensaje=""):
    return render_template(
        "index.html", error=_error_html(exc), mensaje=mensaje, grafica="",
        puntos=[], opciones=[], sel="", valor="", predicho=None, serie=None,
        horizonte=[],
    )


def _contexto():
    serie = predict.cargar_serie()
    base = predict.cargar_modelo()
    puntos = _puntos_sesion()
    predicho = session.get("predicho")

    opciones = _periodos(serie)
    if puntos:
        sig = max(p["periodo"] for p in puntos) + 1
        sig_s = predict.etiqueta_corta(sig)
        if sig_s not in opciones:
            opciones.append(sig_s)

    sel = request.values.get("mes") or opciones[-1]
    sel_p = pd.Period(sel, freq="M")

    esc = predict.construir_escenario(serie, puntos)
    existente = next((p for p in puntos if p["fecha"] == sel), None)
    if existente:
        valor = existente["valor"]
    elif predicho and predicho["fecha"] == sel:
        valor = predicho["valor"]
    elif sel_p in esc.index:
        valor = esc[sel_p]
    else:
        valor = ""

    base_h = predict.horizonte_base(
        base, [serie.index[-1] + 1 + i for i in range(predict.HORIZONTE)]
    )
    esc_h = None
    modelo_esc = base
    if puntos:
        modelo_esc = predict.ajustar_escenario(base, esc)
        esc_h = predict.horizonte_base(modelo_esc, _rango_escenario(serie, puntos))

    return serie, base, modelo_esc, puntos, predicho, opciones, sel, valor, base_h, esc_h


@app.route("/")
def index():
    try:
        serie, base, modelo_esc, puntos, predicho, opciones, sel, valor, base_h, esc_h = _contexto()
    except Exception as exc:
        return _error(exc)
    return render_template(
        "index.html", error="", mensaje="", grafica=_figura(serie, base_h, esc_h, puntos, predicho),
        puntos=puntos, opciones=opciones, sel=sel, valor=valor, predicho=predicho,
        serie=serie, horizonte=base_h,
    )


@app.route("/predecir", methods=["POST"])
def predecir_ruta():
    try:
        serie, base, modelo_esc, puntos, predicho, opciones, sel, _, base_h, esc_h = _contexto()
    except Exception as exc:
        return _error(exc)

    sel_p = pd.Period(sel, freq="M")
    bruto = (request.form.get("valor") or "").strip().replace(".", "").replace(",", ".")
    try:
        valor = float(bruto)
    except ValueError:
        return render_template(
            "index.html",
            error="<div class='aviso'><p>El consumo debe ser un número (kWh).</p></div>",
            mensaje="", grafica=_figura(serie, base_h, esc_h, puntos, predicho),
            puntos=puntos, opciones=opciones, sel=sel,
            valor=request.form.get("valor", ""), predicho=predicho,
            serie=serie, horizonte=base_h,
        )

    puntos = [p for p in puntos if p["fecha"] != sel]
    puntos.append({"fecha": sel, "periodo": sel_p, "valor": valor, "tipo": "inventado"})
    puntos.sort(key=lambda p: p["periodo"])

    esc = predict.construir_escenario(serie, puntos)
    objetivo = sel_p + 1
    try:
        modelo_esc = predict.ajustar_escenario(base, esc)
        pred = predict.predecir_base(modelo_esc, objetivo)
        ref_base = predict.predecir_base(base, objetivo)
    except Exception as exc:
        return _error(exc)

    predicho = {
        "fecha": predict.etiqueta_corta(objetivo),
        "valor": round(pred["yhat"], 2),
        "base": round(ref_base["yhat"], 2),
    }
    _guardar_puntos(puntos)
    session["predicho"] = predicho

    esc_h = predict.horizonte_base(modelo_esc, _rango_escenario(serie, puntos))
    sig_s = predicho["fecha"]
    opciones_nuevas = opciones if sig_s in opciones else opciones + [sig_s]

    return render_template(
        "index.html", error="", mensaje="",
        grafica=_figura(serie, base_h, esc_h, puntos, predicho),
        puntos=puntos, opciones=opciones_nuevas, sel=sig_s, valor=predicho["valor"],
        predicho=predicho, serie=serie, horizonte=base_h,
    )


@app.route("/reiniciar")
def reiniciar():
    session.clear()
    return index()


from dashboard import registrar_dash  # noqa: E402

registrar_dash(app)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
