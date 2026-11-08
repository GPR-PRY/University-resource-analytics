# University Resource Analytics

Interactive analysis and prediction of water and energy consumption across universities.

## Objectives

- Analyze historical water and energy consumption.
- Explore trends and compare universities where the data allows.
- Develop and evaluate a predictive model.
- Provide an interactive dashboard for data exploration and predictions.

## Tech stack

- Python / Pandas and NumPy
- Prophet (predictive model)
- Flask + Plotly (server-side demo)
- Dash (comparative dashboard)

## Project structure

- `rawdata/`: original source files
- `data/`: combined monthly energy dataset (`datos_energia_combinado.xlsx`)
- `models/`: trained Prophet model (`modelo_prophet_energia.pkl`)
- `notebooks`: `AED_SerTemp_ConEnergUnis.ipynb`, `Modelo_predictivo_GPR.ipynb` (training), `dashboard.ipynb`
- `src/`: web app
  - `app.py`: Flask app (demo + serves the dashboard)
  - `predict.py`: data/model loading and prediction helpers
  - `dashboard.py`: Dash dashboard (extracted from `dashboard.ipynb`)
  - `templates/`, `static/`

## Getting started

1. Clone the repository.
2. Install dependencies with [uv](https://docs.astral.sh/uv/): `uv sync`
   (or `pip install -r requirements.txt`).
3. Make sure the data and model files exist (see contracts below).
4. Run `uv run python src/app.py` and open http://127.0.0.1:5000

## Data and model contracts

The web app does **not** treat data or train the model. It only loads two files:

**Data** — `data/datos_energia_combinado.xlsx`

- One row per university and year, with monthly columns (`Enero` … `Diciembre`) and
  `Total`, in kWh. Columns: `Uni`, `Año`, …
- The app uses the rows of `UPV` (`src/predict.py`, constant `UNIVERSIDAD`).

**Model** — `models/modelo_prophet_energia.pkl`

- A `prophet.Prophet` model pickled with `pickle.dump`, trained on the UPV monthly
  series (2012–2025, target `y` = kWh, column `ds` = first day of month).
- Prediction: `model.predict(df)` with a `ds` column; the app reads `yhat`,
  `yhat_lower` and `yhat_upper`.
- The scenario ("what-if") toy refits a new `Prophet` with the same
  hyperparameters (see `_HIPERPARAMETROS` in `src/predict.py`) on the history
  plus the invented months. If the model is retrained with different settings,
  update that tuple.

## Demo

Open http://127.0.0.1:5000:

- **Historical series and forecast**: real consumption, plus the base model
  forecast for the next 12 months with its 80% uncertainty band.
- **Prediction toy**: pick a month, type an invented consumption (kWh), and the
  model forecasts the next month conditioned on it (Prophet is refit). Chain
  forecasts by reusing the predicted value as the next input.
- **Dashboard ↗**: the comparative dashboard (`/dashboard/`) opens in another tab.

## Data sources

Document the source, license, collection period, units and limitations of each dataset here.

## Team

Add the project members and their responsibilities.

## Limitations

Predictions depend on the available data, its quality and the assumptions made during modeling.
