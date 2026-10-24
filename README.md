# PolarGuard project package and setup

## Package provenance

This is a cleaned distribution copy of the existing PolarGuard project, prepared on 24 October 2026 for transfer and setup. The project code, models, and evaluation work existed before this package was prepared; this date is the packaging date, not the project start date. Git metadata is intentionally omitted from this ZIP, so the archive does not contain commit history. Consult the source GitHub repository for the original commit record.

## Run the Streamlit app on Windows

From PowerShell, after extracting this folder to a drive with enough space:

```powershell
cd D:\PolarGuard_IIITD
New-Item -ItemType Directory -Force D:\PolarGuard_Runtime\temp | Out-Null
$env:TEMP = "D:\PolarGuard_Runtime\temp"
$env:TMP = "D:\PolarGuard_Runtime\temp"
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r .\requirements.txt
Copy-Item .\.streamlit\secrets.toml.example .\.streamlit\secrets.toml
# Edit secrets.toml and enter your own credentials; never commit or share it.
.\.venv\Scripts\python.exe -m streamlit run .\app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`. The app uses Hugging Face data access for historical SIC when the local dataset is absent. `TINYFISH_API_KEY` is only needed for the Polar Updates search feature. Keep real credentials in `.streamlit/secrets.toml`; that file is excluded from this package.

---

# PolarGuard — Antarctic Sea-Ice Forecasting Module

## 1. Overview

PolarGuard's Sea-Ice Forecasting Module predicts Antarctic sea-ice
concentration (SIC) at three forecast horizons:

- +24 hours
- +48 hours
- +72 hours

The system uses recent sea-ice observations, spatial information, and
seasonal information to generate full Antarctic SIC forecast grids.

A hybrid forecasting strategy combines:

1. Persistence forecasting for stable grid cells
2. HistGradientBoosting machine learning for dynamically changing cells

The module also provides spatial forecast-uncertainty estimates for each
forecast horizon.

---

## 2. Dataset

Dataset:

NOAA/NSIDC Climate Data Record of Passive Microwave Sea Ice
Concentration, Version 6 (G02202 V6)

Data used:

- 2019–2025
- Daily Antarctic sea-ice concentration
- 25 km grid
- NetCDF format

Grid dimensions:

332 × 316

Projection:

EPSG:3412

Sea-ice concentration is represented as a fraction:

0.0 = 0% sea-ice concentration

1.0 = 100% sea-ice concentration

NaN values represent invalid or masked grid cells and must not be
interpreted as open water.

---

## 3. Chronological Data Split

To avoid temporal leakage, the dataset was divided chronologically.

Training:

2019–2023

Validation:

2024

Held-out test:

2025

The 2025 test dataset was not used for model tuning.

---

## 4. Model Inputs

The forecasting service requires the latest four daily SIC maps.

For forecast initialization day t:

- SIC(t)
- SIC(t-1)
- SIC(t-2)
- SIC(t-3)

It also requires:

- X grid coordinates
- Y grid coordinates
- Forecast initialization date

Each SIC map has shape:

332 × 316

---

## 5. Machine-Learning Features

For every valid grid cell, eight features are generated:

1. SIC(t)
2. SIC(t-1)
3. SIC(t-2)
4. SIC(t-3)
5. Normalized X coordinate
6. Normalized Y coordinate
7. sin(day-of-year)
8. cos(day-of-year)

The sine and cosine features represent the Antarctic seasonal cycle.

---

## 6. Machine-Learning Model

Three separate models are trained:

- 24-hour model
- 48-hour model
- 72-hour model

Algorithm:

HistGradientBoostingRegressor

Training configuration:

- learning_rate = 0.08
- max_iter = 150
- max_leaf_nodes = 31
- min_samples_leaf = 50
- l2_regularization = 0.1
- random_state = 42

Approximately 1.5 million reproducibly sampled training examples were
used for model fitting.

---

## 7. Persistence Baseline

A persistence forecast assumes:

Future SIC = Current SIC

Persistence is a strong baseline for short-term sea-ice forecasting
because many Antarctic grid cells change only slowly over short periods.

All final model results are therefore compared against persistence.

---

## 8. Hybrid Forecasting Strategy

Analysis showed that persistence performs extremely well in stable
regions, while the machine-learning model is more useful in dynamically
changing regions.

PolarGuard therefore uses a hybrid strategy.

Recent change is calculated as:

recent_change = abs(SIC(t) - SIC(t-3))

The frozen switching threshold is:

0.002

Decision rule:

If recent_change < 0.002:

    Use persistence

Otherwise:

    Use HistGradientBoosting prediction

The threshold was selected using the 2024 validation dataset.

The 2025 held-out test set was not used to tune this threshold.

---

## 9. Forecast Outputs

The model produces:

- 24-hour SIC forecast
- 48-hour SIC forecast
- 72-hour SIC forecast

Each forecast is a:

332 × 316

Antarctic grid.

Forecast values are constrained to:

0.0 <= SIC <= 1.0

---

## 10. Forecast Uncertainty

PolarGuard also produces uncertainty maps for:

- 24 hours
- 48 hours
- 72 hours

The uncertainty estimate is based on historical per-grid-cell RMSE
calculated from 2024 validation residuals.

Mean validation-derived uncertainty:

| Horizon | Mean uncertainty |
|---|---:|
| 24h | 1.96 SIC percentage points |
| 48h | 2.75 SIC percentage points |
| 72h | 3.28 SIC percentage points |

These values are empirical historical forecast-error estimates.

They are NOT calibrated 95% confidence intervals.

---

## 11. Final Held-Out 2025 Performance

The following results are calculated on the held-out 2025 test set.

| Horizon | MAE | RMSE | Within ±5 SIC points | RMSE gain vs persistence |
|---|---:|---:|---:|---:|
| 24h | 0.008854 | 0.036288 | 94.87% | +4.56% |
| 48h | 0.012707 | 0.050063 | 93.18% | +5.73% |
| 72h | 0.015287 | 0.059311 | 92.33% | +7.04% |

Tolerance results:

### 24 hours

- Within ±1 SIC percentage point: 86.61%
- Within ±5 SIC percentage points: 94.87%
- Within ±10 SIC percentage points: 97.62%

### 48 hours

- Within ±1 SIC percentage point: 85.21%
- Within ±5 SIC percentage points: 93.18%
- Within ±10 SIC percentage points: 96.10%

### 72 hours

- Within ±1 SIC percentage point: 84.62%
- Within ±5 SIC percentage points: 92.33%
- Within ±10 SIC percentage points: 95.25%

---

## 12. Important Interpretation of Performance

The model should not be described as having "94.87% accuracy."

The correct interpretation is:

"94.87% of 24-hour grid-cell forecasts on the held-out 2025 test set
were within ±5 percentage points of observed sea-ice concentration."

The hybrid system reduced RMSE relative to persistence at all three
forecast horizons.

The 24-hour hybrid MAE was slightly worse than persistence, while
48-hour and 72-hour MAE improved.

Therefore, the model should not be claimed to outperform persistence
on every metric.

---

## 13. Historical Demo Forecast

A historical forecast was initialized on:

2025-12-28

Inputs:

- 2025-12-28 current SIC
- 2025-12-27 SIC
- 2025-12-26 SIC
- 2025-12-25 SIC

Targets:

- +24h → 2025-12-29
- +48h → 2025-12-30
- +72h → 2025-12-31

Results:

| Horizon | MAE | RMSE | Within ±5 SIC points | RMSE gain |
|---|---:|---:|---:|---:|
| 24h | 0.007903 | 0.034545 | 95.29% | +9.33% |
| 48h | 0.011327 | 0.047826 | 93.49% | +12.56% |
| 72h | 0.013551 | 0.057418 | 92.64% | +15.26% |

These are demo-case results and should not replace the full-year 2025
evaluation.

---

## 14. Seasonal / Multi-Date Testing

The forecasting service was additionally tested using initialization
dates from different parts of 2025:

- 2025-02-15
- 2025-05-15
- 2025-08-15
- 2025-11-15

All 12 tested date/horizon combinations produced lower RMSE than the
corresponding persistence forecast.

These tests are robustness checks and are not substitutes for the
full-year held-out evaluation.

---

## 15. Python Service

The primary integration interface is:

sea_ice_service.py

Import:

```python
from sea_ice_service import (
    predict_sea_ice,
    load_uncertainty
)
```

Forecast example:

```python
forecasts = predict_sea_ice(
    current=current,
    lag1=lag1,
    lag2=lag2,
    lag3=lag3,
    x_coords=x_coords,
    y_coords=y_coords,
    date=date
)
```

Returned structure:

```python
{
    "24h": forecast_24h,
    "48h": forecast_48h,
    "72h": forecast_72h
}
```

Each returned forecast has shape:

332 × 316

Load uncertainty:

```python
uncertainty = load_uncertainty()
```

Returned structure:

```python
{
    "24h": uncertainty_24h,
    "48h": uncertainty_48h,
    "72h": uncertainty_72h
}
```

---

## 16. Integration Package

The final integration export is located at:

```text
outputs/integration/
├── sea_ice_integration_package.nc
└── sea_ice_integration_metadata.json
```

The NetCDF package contains:

- current_sic
- forecast_24h
- uncertainty_24h
- forecast_48h
- uncertainty_48h
- forecast_72h
- uncertainty_72h
- X coordinates
- Y coordinates
- model and forecast metadata

The JSON file contains lightweight metadata describing the forecast
package and final model performance.

---

## 17. Important Integration Information

Grid:

332 × 316

Projection:

EPSG:3412

SIC units:

Fraction from 0.0 to 1.0

Examples:

0.15 = 15% sea-ice concentration

0.50 = 50% sea-ice concentration

0.90 = 90% sea-ice concentration

Invalid/masked cells:

NaN

Do not convert NaN cells to zero.

Zero is a valid observation representing open water.

---

## 18. Main Project Files

```text
PolarGuard_SeaIce/
│
├── data/
│   ├── aggregate/
│   └── processed/
│
├── models/
│   ├── sea_ice_model_24h.joblib
│   ├── sea_ice_model_48h.joblib
│   └── sea_ice_model_72h.joblib
│
├── outputs/
│   ├── final/
│   ├── integration/
│   └── maps/
│
├── preprocess.py
├── split_data.py
├── baseline.py
├── create_features.py
├── train.py
├── evaluate_validation.py
├── analyze_errors.py
├── tune_hybrid.py
├── evaluate_test.py
├── predict.py
├── uncertainty.py
├── export_forecast.py
├── forecast_accuracy.py
├── results_summary.py
├── sea_ice_service.py
├── test_service.py
├── test_forecast_accuracy.py
├── test_multiple_dates.py
├── integration_export.py
└── README.md
```

---

## 19. Testing the Service

Basic service test:

```bash
python test_service.py
```

Historical forecast test:

```bash
python test_forecast_accuracy.py
```

Multi-date robustness test:

```bash
python test_multiple_dates.py
```

Generate integration package:

```bash
python integration_export.py
```

---

## 20. System Role in PolarGuard

The Sea-Ice Forecasting Module provides future environmental conditions
to downstream PolarGuard components.

```text
Recent Antarctic SIC observations
              |
              v
      Sea-Ice Forecaster
              |
      +24h / +48h / +72h
              |
              v
       Uncertainty Maps
              |
              v
     Geospatial Risk Model
              |
              v
        Route Planning
              |
              v
    Navigation Decision Support
```

The Sea-Ice module does not predict iceberg trajectories or vessel
routes directly.

Its responsibility is to provide future sea-ice conditions that can be
used by those downstream modules.

---

## 21. Current Limitations

The current forecasting model uses:

- SIC history
- spatial position
- seasonal information

It does not currently use additional environmental forcing variables
such as:

- wind
- ocean currents
- sea-surface temperature
- air temperature

These variables could be incorporated in future versions.

---

## 22. Future Improvements

Possible future extensions include:

- wind-field integration
- ocean-current integration
- sea-surface-temperature features
- air-temperature features
- dedicated ice-edge forecasting
- probabilistic uncertainty calibration
- higher-resolution regional models
- longer forecast horizons

---

## 23. Final Summary

PolarGuard's Sea-Ice Forecasting Module provides operationally usable
24h, 48h, and 72h Antarctic sea-ice concentration forecasts.

The hybrid approach combines the strength of persistence in stable
regions with machine learning in dynamically changing regions.

On the held-out 2025 test set, 94.87%, 93.18%, and 92.33% of grid-cell
predictions were within ±5 SIC percentage points of observations at
24h, 48h, and 72h respectively.

RMSE was reduced relative to persistence by 4.56%, 5.73%, and 7.04%
at the three forecast horizons.

The final system exports forecast and uncertainty grids through a
reusable Python service and a NetCDF/JSON integration package for
downstream PolarGuard risk and navigation components.