from pathlib import Path

import dash
import pandas as pd
import plotly.express as px
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output

BASE = Path(__file__).resolve().parent.parent
EXCEL = BASE / "data" / "datos_energia_combinado.xlsx"
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0, "left": 0, "bottom": 0,
    "width": "20rem", "padding": "2rem 1.5rem",
    "background-color": "#1e293b", "color": "#f8fafc",
    "boxShadow": "4px 0 10px rgba(0,0,0,0.1)",
    "overflowY": "auto"
}

CONTENT_STYLE = {
    "margin-left": "21rem", "margin-right": "2rem",
    "padding": "2rem 1rem", "background-color": "#f8fafc",
    "minHeight": "100vh"
}


def _cargar_datos() -> pd.DataFrame:
    if not EXCEL.exists():
        raise FileNotFoundError(f"No se encuentra {EXCEL}")
    df = pd.read_excel(EXCEL)
    df.columns = df.columns.str.strip()
    return df


def crear_dash(flask_app=None):
    df = _cargar_datos()
    if flask_app is not None:
        dash_app = dash.Dash(
            __name__, server=flask_app, url_base_pathname="/dashboard/",
            title="Dashboard Energético Universitario",
        )
    else:
        dash_app = dash.Dash(__name__, title="Dashboard Energético Universitario")

    dash_app.layout = html.Div([
        html.Div([
            html.H2("EnergyDash", style={"color": "#38bdf8", "fontWeight": "bold"}),
            html.P("Panel de Control Energético", style={"color": "#94a3b8", "fontSize": "0.9rem"}),
            html.Hr(style={"borderColor": "#334155"}),

            html.Label("Universidades:", style={"fontWeight": "bold", "color": "#e2e8f0"}),
            dcc.Dropdown(
                id='dropdown-unis',
                options=[{'label': u, 'value': u} for u in df['Uni'].unique()],
                value=list(df['Uni'].unique()),
                multi=True,
                style={"color": "#0f172a", "marginBottom": "1.5rem"}
            ),

            html.Label("Rango de Años:", style={"fontWeight": "bold", "color": "#e2e8f0"}),
            dcc.RangeSlider(
                id='slider-anios',
                min=int(df['Año'].min()),
                max=int(df['Año'].max()),
                step=1,
                value=[int(df['Año'].min()), int(df['Año'].max())],
                marks={int(a): str(a) for a in sorted(df['Año'].unique())
                       if a % 2 == 0 or a == df['Año'].max()}
            ),
            html.Div(style={"marginBottom": "2rem"}),

            html.Label("Unidad de Medida:", style={"fontWeight": "bold", "color": "#e2e8f0"}),
            dcc.RadioItems(
                id='radio-unidad',
                options=[
                    {'label': ' Gigavatios-hora (GWh)', 'value': 'GWh'},
                    {'label': ' Kilovatios-hora (kWh)', 'value': 'kWh'}
                ],
                value='GWh',
                labelStyle={'display': 'block', 'margin-top': '8px', 'color': '#cbd5e1'}
            ),
        ], style=SIDEBAR_STYLE),

        html.Div([
            html.Div([
                html.H1("Comparativa de Consumo Eléctrico Universitario",
                        style={"color": "#0f172a", "fontWeight": "bold"}),
                html.P("Análisis multianual de consumo energético en UPM, UPV y UV",
                       style={"color": "#64748b"})
            ], style={"marginBottom": "2rem"}),

            html.Div(id='kpi-cards', style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(220px, 1fr))",
                "gap": "1.5rem", "marginBottom": "2rem"
            }),

            dcc.Tabs([
                dcc.Tab(label='Evolución Anual', children=[
                    dcc.Graph(id='graph-evolucion', style={"marginTop": "1.5rem"})
                ]),
                dcc.Tab(label='Perfil Estacional Mensual', children=[
                    dcc.Graph(id='graph-estacional', style={"marginTop": "1.5rem"})
                ]),
                dcc.Tab(label='Comparativa Directa', children=[
                    dcc.Graph(id='graph-comparativa', style={"marginTop": "1.5rem"})
                ]),
                dcc.Tab(label='Tabla de Datos', children=[
                    html.Div(id='tabla-container', style={"marginTop": "1.5rem"})
                ]),
            ])
        ], style=CONTENT_STYLE)
    ])

    @dash_app.callback(
        [Output('kpi-cards', 'children'),
         Output('graph-evolucion', 'figure'),
         Output('graph-estacional', 'figure'),
         Output('graph-comparativa', 'figure'),
         Output('tabla-container', 'children')],
        [Input('dropdown-unis', 'value'),
         Input('slider-anios', 'value'),
         Input('radio-unidad', 'value')]
    )
    def update_dashboard(selected_unis, year_range, unit):
        if not selected_unis:
            selected_unis = list(df['Uni'].unique())

        dff = df[(df['Uni'].isin(selected_unis)) &
                 (df['Año'] >= year_range[0]) &
                 (df['Año'] <= year_range[1])].copy()

        factor = 1e6 if unit == 'GWh' else 1
        dff_unit = dff.copy()
        dff_unit['Total_Val'] = dff_unit['Total'] / factor
        for m in MESES:
            dff_unit[m] = dff_unit[m] / factor

        total_consumo = dff_unit['Total_Val'].sum()
        promedio_anual = dff_unit['Total_Val'].mean() if len(dff_unit) > 0 else 0
        top_uni = dff_unit.groupby('Uni')['Total_Val'].mean().idxmax() if len(dff_unit) > 0 else "-"

        kpis = [
            html.Div([
                html.H4("Consumo Acumulado", style={"color": "#64748b", "fontSize": "0.9rem"}),
                html.H2(f"{total_consumo:,.2f} {unit}", style={"color": "#0284c7", "fontWeight": "bold"})
            ], style={"background": "white", "padding": "1.2rem", "borderRadius": "12px",
                      "boxShadow": "0 2px 4px rgba(0,0,0,0.05)"}),

            html.Div([
                html.H4("Promedio por Registro", style={"color": "#64748b", "fontSize": "0.9rem"}),
                html.H2(f"{promedio_anual:,.2f} {unit}", style={"color": "#16a34a", "fontWeight": "bold"})
            ], style={"background": "white", "padding": "1.2rem", "borderRadius": "12px",
                      "boxShadow": "0 2px 4px rgba(0,0,0,0.05)"}),

            html.Div([
                html.H4("Mayor Consumo Medio", style={"color": "#64748b", "fontSize": "0.9rem"}),
                html.H2(top_uni, style={"color": "#ea580c", "fontWeight": "bold"})
            ], style={"background": "white", "padding": "1.2rem", "borderRadius": "12px",
                      "boxShadow": "0 2px 4px rgba(0,0,0,0.05)"}),
        ]

        fig_evol = px.line(
            dff_unit.sort_values('Año'), x='Año', y='Total_Val', color='Uni', markers=True,
            title=f"Evolución del Consumo Anual ({unit})",
            labels={'Total_Val': f'Consumo ({unit})', 'Uni': 'Universidad', 'Año': 'Año'}
        )
        fig_evol.update_layout(template="plotly_white", hovermode="x unified")

        estacional_df = dff_unit.groupby('Uni')[MESES].mean().reset_index()
        estacional_melted = estacional_df.melt(
            id_vars=['Uni'], value_vars=MESES, var_name='Mes', value_name='Consumo'
        )
        fig_est = px.line(
            estacional_melted, x='Mes', y='Consumo', color='Uni', markers=True,
            title=f"Perfil Estacional Promedio Mensual ({unit})",
            labels={'Consumo': f'Consumo Promedio ({unit})', 'Mes': 'Mes'}
        )
        fig_est.update_layout(template="plotly_white")

        fig_comp = px.bar(
            dff_unit, x='Año', y='Total_Val', color='Uni', barmode='group',
            title=f"Comparativa Directa de Consumo por Año ({unit})",
            labels={'Total_Val': f'Consumo ({unit})', 'Uni': 'Universidad', 'Año': 'Año'}
        )
        fig_comp.update_layout(template="plotly_white")

        dff_display = dff_unit[['Uni', 'Año'] + MESES + ['Total_Val']].copy()
        dff_display.rename(columns={'Total_Val': f'Total ({unit})'}, inplace=True)
        table = dash_table.DataTable(
            data=dff_display.to_dict('records'),
            columns=[{"name": i, "id": i} for i in dff_display.columns],
            page_size=10,
            sort_action="native",
            filter_action="native",
            style_table={'overflowX': 'auto'},
            style_header={'backgroundColor': '#1e293b', 'color': 'white', 'fontWeight': 'bold'},
            style_cell={'textAlign': 'center', 'padding': '10px'}
        )

        return kpis, fig_evol, fig_est, fig_comp, table

    return dash_app


def registrar_dash(flask_app):
    return crear_dash(flask_app)


if __name__ == "__main__":
    print("Dashboard independiente: http://127.0.0.1:8050/")
    crear_dash().run(debug=True, port=8050)
