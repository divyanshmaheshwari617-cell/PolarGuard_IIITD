# from pathlib import Path

# import numpy as np
# import pandas as pd
# import streamlit as st


# BASE = Path(__file__).resolve().parent

# VALIDATION_ROOT = (
#     BASE
#     / "iceberg"
#     / "outputs"
#     / "ais_route_validation"
#     / "ps146_2025_validation"
# )

# COMPARISON_FILE = (
#     VALIDATION_ROOT
#     / "stage4_route_comparison"
#     / "ps146_2025_route_comparison_summary.csv"
# )

# SUCCESS_FILE = (
#     VALIDATION_ROOT
#     / "stage4_route_comparison"
#     / "ps146_2025_successful_route_comparisons.csv"
# )

# FAILED_DIAGNOSTIC_FILE = (
#     VALIDATION_ROOT
#     / "start_cell_diagnostic"
#     / "ps146_2025_failed_start_cell_summary.csv"
# )

# FIGURE_DIR = (
#     VALIDATION_ROOT
#     / "final_validation_figures"
# )

# # ============================================================
# # FULL-YEAR 2025 MEMBER-1 SIC TESTING
# # ============================================================

# MODEL_TEST_ROOT = (
#     BASE
#     / "iceberg"
#     / "outputs"
#     / "model_testing_2025"
# )

# SIC_METRICS_FILE = (
#     MODEL_TEST_ROOT
#     / "sic_2025_metrics.csv"
# )

# SIC_DAILY_FILE = (
#     MODEL_TEST_ROOT
#     / "sic_2025_daily_metrics.csv"
# )

# SIC_MONTHLY_FILE = (
#     MODEL_TEST_ROOT
#     / "sic_2025_monthly_metrics.csv"
# )

# SIC_FIGURE_DIR = (
#     MODEL_TEST_ROOT
#     / "figures"
# )

# # ============================================================
# # FULL-YEAR 2025 SIC SAFETY CLASSIFICATION
# # ============================================================

# SAFETY_TEST_ROOT = (
#     MODEL_TEST_ROOT
#     / "safety_classification"
# )

# SAFETY_SUMMARY_FILE = (
#     SAFETY_TEST_ROOT
#     / "sic_safety_classification_summary.csv"
# )

# SAFETY_DAILY_FILE = (
#     SAFETY_TEST_ROOT
#     / "sic_safety_classification_daily.csv"
# )

# SAFETY_FIGURE_DIR = (
#     SAFETY_TEST_ROOT
#     / "figures"
# )


# @st.cache_data(show_spinner=False)
# def load_validation_data():

#     summary = pd.read_csv(
#         COMPARISON_FILE
#     )

#     successful = pd.read_csv(
#         SUCCESS_FILE
#     )

#     failed = pd.read_csv(
#         FAILED_DIAGNOSTIC_FILE
#     )

#     summary["routing_success"] = (
#         summary["routing_success"]
#         .astype(str)
#         .str.lower()
#         .map(
#             {
#                 "true": True,
#                 "false": False,
#             }
#         )
#         .fillna(False)
#     )

#     return (
#         summary,
#         successful,
#         failed,
#     )


# @st.cache_data(show_spinner=False)
# def load_sic_testing_data():
#     """
#     Load full-year 2025 Member-1 forecast testing outputs.
#     """

#     overall = pd.read_csv(
#         SIC_METRICS_FILE
#     )

#     daily = pd.read_csv(
#         SIC_DAILY_FILE
#     )

#     monthly = pd.read_csv(
#         SIC_MONTHLY_FILE
#     )

#     return (
#         overall,
#         daily,
#         monthly,
#     )


# def show_sic_image_if_exists(
#     filename,
#     caption=None,
# ):
#     """
#     Display a full-year 2025 SIC testing figure if it exists.
#     """

#     path = (
#         SIC_FIGURE_DIR
#         /
#         filename
#     )

#     if path.exists():

#         st.image(
#             str(path),
#             use_container_width=True,
#             caption=caption,
#         )

#     else:

#         st.warning(
#             f"SIC testing figure not found: {filename}"
#         )


# @st.cache_data(show_spinner=False)
# def load_safety_testing_data():
#     """
#     Load full-year 2025 dangerous-ice classification outputs.
#     """

#     summary = pd.read_csv(
#         SAFETY_SUMMARY_FILE
#     )

#     daily = pd.read_csv(
#         SAFETY_DAILY_FILE
#     )

#     return (
#         summary,
#         daily,
#     )


# def show_safety_image_if_exists(
#     filename,
#     caption=None,
# ):
#     """
#     Display a dangerous-ice classification figure if it exists.
#     """

#     path = (
#         SAFETY_FIGURE_DIR
#         /
#         filename
#     )

#     if path.exists():

#         st.image(
#             str(path),
#             use_container_width=True,
#             caption=caption,
#         )

#     else:

#         st.warning(
#             f"Safety testing figure not found: {filename}"
#         )


# def show_image_if_exists(
#     filename,
#     caption=None,
# ):

#     path = (
#         FIGURE_DIR
#         /
#         filename
#     )

#     if path.exists():

#         st.image(
#             str(path),
#             use_container_width=True,
#             caption=caption,
#         )

#     else:

#         st.warning(
#             f"Validation figure not found: {filename}"
#         )


# def render_validation_2025():

#     st.header(
#         "🧪 2025 Historical Validation"
#     )

#     st.markdown(
#         """
# PolarGuard was evaluated using **held-out 2025 sea-ice data**
# and the real **RV Polarstern PS146 vessel track**.

# The purpose of this page is to show the difference between:

# - **model input / prediction**
# - **real observed 2025 conditions**
# - **actual recorded Polarstern vessel route**
# - **PolarGuard recommended route**

# The routing experiment used frozen validation cases so results
# were not selected after seeing the routing outcome.
# """
#     )

#     try:

#         summary, successful, failed = (
#             load_validation_data()
#         )

#     except Exception as exc:

#         st.error(
#             "Could not load the PS146 2025 validation files."
#         )

#         st.exception(
#             exc
#         )

#         return

#     # ========================================================
#     # DATA SPLIT
#     # ========================================================

#     st.subheader(
#         "📚 Training vs Testing Data"
#     )

#     col1, col2, col3 = st.columns(3)

#     with col1:

#         st.metric(
#             "Model Training Period",
#             "2019–2023",
#         )

#         st.caption(
#             "Historical sea-ice data used for model development."
#         )

#     with col2:

#         st.metric(
#             "Held-Out Test Period",
#             "2025",
#         )

#         st.caption(
#             "2025 was kept separate for out-of-sample evaluation."
#         )

#     with col3:

#         st.metric(
#             "Real Vessel Dataset",
#             "Polarstern PS146",
#         )

#         st.caption(
#             "Actual GPS/AIS-style master-track positions from the 2025 expedition."
#         )

#     st.info(
#         "2025 observations are used as ground truth for this historical backtest."
#     )

#     # ========================================================
#     # MAIN METRICS
#     # ========================================================

#     st.subheader(
#         "📊 Final Validation Results"
#     )

#     total_cases = len(
#         summary
#     )

#     successful_cases = len(
#         successful
#     )

#     failed_cases = (
#         total_cases
#         -
#         successful_cases
#     )

#     mean_distance_reduction = float(
#         successful[
#             "distance_saved_pct"
#         ].mean()
#     )

#     median_distance_reduction = float(
#         successful[
#             "distance_saved_pct"
#         ].median()
#     )

#     mean_ais_sic = float(
#         successful[
#             "ais_actual_mean_sic_pct"
#         ].mean()
#     )

#     mean_pg_sic = float(
#         successful[
#             "pg_actual_mean_sic_pct"
#         ].mean()
#     )

#     relative_sic_reduction = (
#         (
#             mean_ais_sic
#             -
#             mean_pg_sic
#         )
#         /
#         mean_ais_sic
#         *
#         100.0
#         if mean_ais_sic > 0
#         else np.nan
#     )

#     mean_deviation = float(
#         successful[
#             "mean_ais_to_pg_km"
#         ].mean()
#     )

#     metric1, metric2, metric3, metric4 = (
#         st.columns(4)
#     )

#     metric1.metric(
#         "Frozen Test Cases",
#         total_cases,
#     )

#     metric2.metric(
#         "Feasible Routes",
#         f"{successful_cases}/{total_cases}",
#     )

#     metric3.metric(
#         "Mean Modeled Distance Reduction",
#         f"{mean_distance_reduction:.2f}%",
#     )

#     metric4.metric(
#         "Observed SIC Reduction",
#         f"{relative_sic_reduction:.2f}%",
#     )

#     metric5, metric6, metric7, metric8 = (
#         st.columns(4)
#     )

#     metric5.metric(
#         "Median Distance Reduction",
#         f"{median_distance_reduction:.2f}%",
#     )

#     metric6.metric(
#         "AIS Mean Observed SIC",
#         f"{mean_ais_sic:.2f}%",
#     )

#     metric7.metric(
#         "PolarGuard Mean Observed SIC",
#         f"{mean_pg_sic:.2f}%",
#     )

#     metric8.metric(
#         "Mean Route Deviation",
#         f"{mean_deviation:.2f} km",
#     )

#     st.caption(
#         "Distance metrics include the exact start → routing-grid connector "
#         "and routing-grid → exact destination connector."
#     )

#     # ========================================================
#     # VALIDATION PIPELINE
#     # ========================================================

#     st.subheader(
#         "🔬 How the Test Was Performed"
#     )

#     st.markdown(
#         """
# **1. Train / develop model**

# `2019–2023 historical SIC`

# ↓

# **2. Freeze the model**

# No retraining during the 2025 evaluation.

# ↓

# **3. Feed historical initialization conditions**

# PolarGuard receives the sea-ice state available at the beginning
# of each selected PS146 route window.

# ↓

# **4. Generate +24h / +48h / +72h forecasts**

# ↓

# **5. Generate PolarGuard route**

# The same real vessel start and destination are used.

# ↓

# **6. Compare against real 2025 observations**

# The generated route is evaluated using subsequently observed
# 2025 sea-ice conditions and the actual Polarstern track.
# """
#     )

#     # ========================================================
#     # FULL-YEAR 2025 SIC FORECAST TESTING
#     # ========================================================

#     st.subheader(
#         "🧠 Full-Year 2025 Sea-Ice Forecast Testing"
#     )

#     st.markdown(
#         """
# This section evaluates the **frozen Member-1 sea-ice model** on the
# held-out **2025 test year**.

# For each valid initialization date, PolarGuard used the current SIC map
# and the previous three daily SIC maps to generate **+24h, +48h and +72h**
# forecasts. Those forecasts were then compared with the corresponding
# observed 2025 SIC maps.

# The same test also compares PolarGuard with a **persistence baseline**:
# `future SIC = current SIC`.
# """
#     )

#     try:

#         sic_overall, sic_daily, sic_monthly = (
#             load_sic_testing_data()
#         )

#         sic_testing_available = True

#     except Exception as exc:

#         sic_testing_available = False

#         st.warning(
#             "Full-year 2025 SIC testing files could not be loaded."
#         )

#         st.caption(
#             str(exc)
#         )

#     if sic_testing_available:

#         sic_overall = (
#             sic_overall
#             .sort_values(
#                 "horizon_hours"
#             )
#             .reset_index(
#                 drop=True
#             )
#         )

#         # ----------------------------------------------------
#         # TEST COVERAGE
#         # ----------------------------------------------------

#         test_initializations = int(
#             sic_overall[
#                 "test_initializations"
#             ].max()
#         )

#         coverage_col1, coverage_col2, coverage_col3, coverage_col4 = (
#             st.columns(4)
#         )

#         coverage_col1.metric(
#             "Held-Out Test Year",
#             "2025",
#         )

#         coverage_col2.metric(
#             "Valid Initializations",
#             f"{test_initializations}",
#         )

#         coverage_col3.metric(
#             "Forecast Horizons",
#             "24h / 48h / 72h",
#         )

#         coverage_col4.metric(
#             "Evaluation Grid",
#             "332 × 316",
#         )

#         st.caption(
#             "The full-year test uses observed 2025 SIC as ground truth. "
#             "The model is evaluated without retraining."
#         )

#         # ----------------------------------------------------
#         # RMSE METRIC CARDS
#         # ----------------------------------------------------

#         st.markdown(
#             "#### Forecast Error by Horizon"
#         )

#         rmse_cols = st.columns(3)

#         for column, (_, row) in zip(
#             rmse_cols,
#             sic_overall.iterrows(),
#         ):

#             horizon_hours = int(
#                 row[
#                     "horizon_hours"
#                 ]
#             )

#             rmse_points = float(
#                 row[
#                     "rmse"
#                 ]
#                 *
#                 100.0
#             )

#             persistence_rmse_points = float(
#                 row[
#                     "persistence_rmse"
#                 ]
#                 *
#                 100.0
#             )

#             improvement = float(
#                 row[
#                     "rmse_improvement_vs_persistence_pct"
#                 ]
#             )

#             column.metric(
#                 f"+{horizon_hours}h RMSE",
#                 f"{rmse_points:.2f} SIC pts",
#                 delta=(
#                     f"{improvement:+.2f}% vs persistence"
#                 ),
#             )

#             column.caption(
#                 f"Persistence RMSE: "
#                 f"{persistence_rmse_points:.2f} SIC pts"
#             )

#         # ----------------------------------------------------
#         # R2 CARDS
#         # ----------------------------------------------------

#         r2_cols = st.columns(3)

#         for column, (_, row) in zip(
#             r2_cols,
#             sic_overall.iterrows(),
#         ):

#             horizon_hours = int(
#                 row[
#                     "horizon_hours"
#                 ]
#             )

#             column.metric(
#                 f"+{horizon_hours}h R²",
#                 f"{float(row['r2']):.4f}",
#             )

#         # ----------------------------------------------------
#         # ACTUAL VS PREDICTED METRICS TABLE
#         # ----------------------------------------------------

#         st.markdown(
#             "#### Actual vs Predicted SIC Metrics"
#         )

#         sic_table = sic_overall[
#             [
#                 "horizon_hours",
#                 "test_initializations",
#                 "actual_mean_sic",
#                 "predicted_mean_sic",
#                 "mae",
#                 "rmse",
#                 "bias",
#                 "r2",
#                 "persistence_mae",
#                 "persistence_rmse",
#                 "mae_improvement_vs_persistence_pct",
#                 "rmse_improvement_vs_persistence_pct",
#             ]
#         ].copy()

#         for column in [
#             "actual_mean_sic",
#             "predicted_mean_sic",
#             "mae",
#             "rmse",
#             "bias",
#             "persistence_mae",
#             "persistence_rmse",
#         ]:

#             sic_table[
#                 column
#             ] = (
#                 sic_table[
#                     column
#                 ]
#                 *
#                 100.0
#             )

#         sic_table = sic_table.rename(
#             columns={
#                 "horizon_hours":
#                     "Horizon (h)",

#                 "test_initializations":
#                     "Test Initializations",

#                 "actual_mean_sic":
#                     "Actual Mean SIC (%)",

#                 "predicted_mean_sic":
#                     "Predicted Mean SIC (%)",

#                 "mae":
#                     "MAE (SIC pts)",

#                 "rmse":
#                     "RMSE (SIC pts)",

#                 "bias":
#                     "Bias (SIC pts)",

#                 "r2":
#                     "R²",

#                 "persistence_mae":
#                     "Persistence MAE (SIC pts)",

#                 "persistence_rmse":
#                     "Persistence RMSE (SIC pts)",

#                 "mae_improvement_vs_persistence_pct":
#                     "MAE Improvement vs Persistence (%)",

#                 "rmse_improvement_vs_persistence_pct":
#                     "RMSE Improvement vs Persistence (%)",
#             }
#         )

#         st.dataframe(
#             sic_table.round(4),
#             use_container_width=True,
#             hide_index=True,
#         )

#         st.info(
#             "Interpretation: lower MAE/RMSE is better. Bias near zero is better. "
#             "R² closer to 1 indicates stronger agreement with observed spatial SIC. "
#             "Positive persistence-improvement values mean PolarGuard performs better "
#             "than simply assuming future SIC equals current SIC."
#         )

#         # ----------------------------------------------------
#         # CORE SIC TESTING FIGURES
#         # ----------------------------------------------------

#         st.markdown(
#             "#### PolarGuard Forecast Accuracy"
#         )

#         fig_col1, fig_col2 = st.columns(2)

#         with fig_col1:

#             show_sic_image_if_exists(
#                 "01_rmse_by_horizon.png",
#                 (
#                     "Full-year 2025 RMSE for +24h, +48h and +72h "
#                     "sea-ice forecasts."
#                 ),
#             )

#         with fig_col2:

#             show_sic_image_if_exists(
#                 "03_r2_by_horizon.png",
#                 (
#                     "Full-year 2025 R² by forecast horizon."
#                 ),
#             )

#         st.markdown(
#             "#### Actual SIC vs Predicted SIC"
#         )

#         show_sic_image_if_exists(
#             "04_actual_vs_predicted_mean_sic.png",
#             (
#                 "Observed 2025 mean SIC compared with PolarGuard "
#                 "predicted mean SIC at each forecast horizon."
#             ),
#         )

#         # ----------------------------------------------------
#         # PERSISTENCE BASELINE
#         # ----------------------------------------------------

#         st.markdown(
#             "#### PolarGuard vs Persistence Baseline"
#         )

#         baseline_col1, baseline_col2 = st.columns(2)

#         with baseline_col1:

#             show_sic_image_if_exists(
#                 "02_rmse_vs_persistence.png",
#                 (
#                     "PolarGuard RMSE compared with the persistence "
#                     "baseline at each forecast horizon."
#                 ),
#             )

#         with baseline_col2:

#             show_sic_image_if_exists(
#                 "09_rmse_improvement_vs_persistence.png",
#                 (
#                     "Positive values indicate lower RMSE than the "
#                     "persistence baseline."
#                 ),
#             )

#         st.caption(
#             "The 24h MAE is slightly worse than persistence, while RMSE "
#             "improves at all three horizons. This result is shown rather "
#             "than hidden because the dashboard reports the complete test."
#         )

#         # ----------------------------------------------------
#         # MONTHLY TESTING
#         # ----------------------------------------------------

#         st.markdown(
#             "#### Monthly Performance Across 2025"
#         )

#         monthly_col1, monthly_col2 = st.columns(2)

#         with monthly_col1:

#             show_sic_image_if_exists(
#                 "06_monthly_mae_2025.png",
#                 (
#                     "Monthly MAE across the held-out 2025 test year."
#                 ),
#             )

#         with monthly_col2:

#             show_sic_image_if_exists(
#                 "07_monthly_rmse_2025.png",
#                 (
#                     "Monthly RMSE across the held-out 2025 test year."
#                 ),
#             )

#         show_sic_image_if_exists(
#             "08_monthly_actual_vs_predicted_sic.png",
#             (
#                 "Monthly observed SIC compared with PolarGuard predicted "
#                 "SIC through the full 2025 test year."
#             ),
#         )

#         # ----------------------------------------------------
#         # BIAS
#         # ----------------------------------------------------

#         with st.expander(
#             "Forecast bias details"
#         ):

#             show_sic_image_if_exists(
#                 "05_bias_by_horizon.png",
#                 (
#                     "Negative values indicate slight average SIC "
#                     "underprediction."
#                 ),
#             )

#             bias_table = sic_overall[
#                 [
#                     "horizon_hours",
#                     "bias",
#                 ]
#             ].copy()

#             bias_table[
#                 "bias"
#             ] = (
#                 bias_table[
#                     "bias"
#                 ]
#                 *
#                 100.0
#             )

#             bias_table = bias_table.rename(
#                 columns={
#                     "horizon_hours":
#                         "Horizon (h)",

#                     "bias":
#                         "Bias (SIC percentage points)",
#                 }
#             )

#             st.dataframe(
#                 bias_table.round(4),
#                 use_container_width=True,
#                 hide_index=True,
#             )

#         st.success(
#             "Full-year SIC conclusion: PolarGuard maintained high spatial "
#             "agreement with observed 2025 SIC (R² > 0.96 at all horizons) "
#             "and reduced RMSE relative to persistence at +24h, +48h and +72h."
#         )

#         st.divider()

#     # ========================================================
#     # DANGEROUS-ICE SAFETY CLASSIFICATION
#     # ========================================================

#     st.subheader(
#         "🛡️ Dangerous-Ice Safety Classification"
#     )

#     st.markdown(
#         """
# For the safety test, a grid cell is treated as **unsafe** when
# observed sea-ice concentration is **80% or greater**.

# The positive class is therefore **UNSAFE ICE**.

# Because PolarGuard is intended as a safety-oriented decision-support
# system, the most important measures here are:

# - **Unsafe Recall** — how many truly unsafe cells were detected.
# - **Unsafe Precision** — how often an unsafe warning was correct.
# - **Unsafe F1** — balance between precision and recall.
# - **False-Safe Rate** — actual unsafe cells incorrectly predicted as safe.
# """
#     )

#     try:

#         safety_summary, safety_daily = (
#             load_safety_testing_data()
#         )

#         safety_testing_available = True

#     except Exception as exc:

#         safety_testing_available = False

#         st.warning(
#             "Dangerous-ice safety testing files could not be loaded."
#         )

#         st.caption(
#             str(exc)
#         )

#     if safety_testing_available:

#         safety_summary = (
#             safety_summary
#             .sort_values(
#                 "horizon_hours"
#             )
#             .reset_index(
#                 drop=True
#             )
#         )

#         st.info(
#             "Unsafe threshold used for this validation: SIC ≥ 80%. "
#             "Overall accuracy is shown, but unsafe recall and false-safe "
#             "rate are more important for navigation safety."
#         )

#         # ----------------------------------------------------
#         # HEADLINE SAFETY METRICS
#         # ----------------------------------------------------

#         recall_cols = st.columns(3)

#         for column, (_, row) in zip(
#             recall_cols,
#             safety_summary.iterrows(),
#         ):

#             horizon_hours = int(
#                 row[
#                     "horizon_hours"
#                 ]
#             )

#             recall_pct = float(
#                 row[
#                     "unsafe_recall"
#                 ]
#                 *
#                 100.0
#             )

#             false_safe_pct = float(
#                 row[
#                     "false_safe_rate"
#                 ]
#                 *
#                 100.0
#             )

#             column.metric(
#                 f"+{horizon_hours}h Unsafe Recall",
#                 f"{recall_pct:.2f}%",
#                 delta=(
#                     f"False-safe {false_safe_pct:.2f}%"
#                 ),
#                 delta_color="off",
#             )

#         precision_cols = st.columns(3)

#         for column, (_, row) in zip(
#             precision_cols,
#             safety_summary.iterrows(),
#         ):

#             horizon_hours = int(
#                 row[
#                     "horizon_hours"
#                 ]
#             )

#             precision_pct = float(
#                 row[
#                     "unsafe_precision"
#                 ]
#                 *
#                 100.0
#             )

#             f1_pct = float(
#                 row[
#                     "unsafe_f1"
#                 ]
#                 *
#                 100.0
#             )

#             column.metric(
#                 f"+{horizon_hours}h Unsafe Precision",
#                 f"{precision_pct:.2f}%",
#             )

#             column.caption(
#                 f"Unsafe F1: {f1_pct:.2f}%"
#             )

#         # ----------------------------------------------------
#         # SAFETY TABLE
#         # ----------------------------------------------------

#         st.markdown(
#             "#### Dangerous-Ice Classification Metrics"
#         )

#         safety_table = safety_summary[
#             [
#                 "horizon_hours",
#                 "test_initializations",
#                 "true_unsafe",
#                 "false_safe",
#                 "false_unsafe",
#                 "true_safe",
#                 "unsafe_precision",
#                 "unsafe_recall",
#                 "unsafe_f1",
#                 "false_safe_rate",
#                 "accuracy",
#             ]
#         ].copy()

#         for column in [
#             "unsafe_precision",
#             "unsafe_recall",
#             "unsafe_f1",
#             "false_safe_rate",
#             "accuracy",
#         ]:

#             safety_table[
#                 column
#             ] = (
#                 safety_table[
#                     column
#                 ]
#                 *
#                 100.0
#             )

#         safety_table = safety_table.rename(
#             columns={
#                 "horizon_hours":
#                     "Horizon (h)",

#                 "test_initializations":
#                     "Test Initializations",

#                 "true_unsafe":
#                     "True Unsafe",

#                 "false_safe":
#                     "False Safe",

#                 "false_unsafe":
#                     "False Unsafe",

#                 "true_safe":
#                     "True Safe",

#                 "unsafe_precision":
#                     "Unsafe Precision (%)",

#                 "unsafe_recall":
#                     "Unsafe Recall (%)",

#                 "unsafe_f1":
#                     "Unsafe F1 (%)",

#                 "false_safe_rate":
#                     "False-Safe Rate (%)",

#                 "accuracy":
#                     "Overall Accuracy (%)",
#             }
#         )

#         st.dataframe(
#             safety_table.round(3),
#             use_container_width=True,
#             hide_index=True,
#         )

#         # ----------------------------------------------------
#         # SAFETY FIGURES
#         # ----------------------------------------------------

#         st.markdown(
#             "#### Safety Performance by Forecast Horizon"
#         )

#         safety_fig_1, safety_fig_2 = st.columns(2)

#         with safety_fig_1:

#             show_safety_image_if_exists(
#                 "01_unsafe_precision_recall_f1.png",
#                 (
#                     "Unsafe precision, recall and F1 for the held-out "
#                     "2025 dangerous-ice classification test."
#                 ),
#             )

#         with safety_fig_2:

#             show_safety_image_if_exists(
#                 "02_false_safe_rate.png",
#                 (
#                     "Safety-critical false-safe rate: actual unsafe cells "
#                     "that PolarGuard classified as safe."
#                 ),
#             )

#         st.markdown(
#             "#### Confusion Matrices"
#         )

#         cm1, cm2, cm3 = st.columns(3)

#         with cm1:

#             show_safety_image_if_exists(
#                 "confusion_matrix_24h.png",
#                 "+24h dangerous-ice confusion matrix",
#             )

#         with cm2:

#             show_safety_image_if_exists(
#                 "confusion_matrix_48h.png",
#                 "+48h dangerous-ice confusion matrix",
#             )

#         with cm3:

#             show_safety_image_if_exists(
#                 "confusion_matrix_72h.png",
#                 "+72h dangerous-ice confusion matrix",
#             )

#         st.success(
#             "Safety conclusion: unsafe-ice recall remained above 95% "
#             "through +72h. The false-safe rate increased with forecast "
#             "horizon, from about 2.6% at +24h to about 4.8% at +72h, "
#             "so longer-horizon routing should be treated more cautiously."
#         )

#         st.divider()

#     # ========================================================
#     # ROUTE VALIDATION
#     # ========================================================

#     st.subheader(
#         "🚢 Historical Route Backtesting"
#     )

#     st.caption(
#         "The following section compares the actual recorded Polarstern PS146 "
#         "route windows with PolarGuard recommendations generated for the same "
#         "historical start and destination."
#     )

#     # ========================================================
#     # ACTUAL VS PREDICTED
#     # ========================================================

#     st.subheader(
#         "🌊 Actual Route vs PolarGuard Route"
#     )

#     show_image_if_exists(
#         "02_actual_sic_ais_vs_polarguard.png",
#         (
#             "Observed 2025 sea-ice concentration along the real AIS route "
#             "and the PolarGuard route."
#         ),
#     )

#     st.success(
#         f"Across the {successful_cases} feasible cases, observed mean SIC "
#         f"decreased from {mean_ais_sic:.2f}% on the actual AIS routes "
#         f"to {mean_pg_sic:.2f}% on PolarGuard routes — a "
#         f"{relative_sic_reduction:.2f}% relative reduction."
#     )

#     # ========================================================
#     # DISTANCE
#     # ========================================================

#     st.subheader(
#         "📏 Route Distance Comparison"
#     )

#     mean_actual_distance = float(
#         successful[
#             "ais_distance_km"
#         ].mean()
#     )

#     mean_polarguard_distance = float(
#         successful[
#             "polarguard_distance_km"
#         ].mean()
#     )

#     distance_metric_1, distance_metric_2, distance_metric_3 = (
#         st.columns(3)
#     )

#     distance_metric_1.metric(
#         "Mean Actual Polarstern Distance",
#         f"{mean_actual_distance:.2f} km",
#     )

#     distance_metric_2.metric(
#         "Mean PolarGuard Distance",
#         f"{mean_polarguard_distance:.2f} km",
#     )

#     distance_metric_3.metric(
#         "Mean Modeled Distance Reduction",
#         f"{mean_distance_reduction:.2f}%",
#     )

#     st.markdown(
#         "#### Actual Polarstern Route vs PolarGuard Route"
#     )

#     route_distance_chart = successful[
#         [
#             "case_id",
#             "ais_distance_km",
#             "polarguard_distance_km",
#         ]
#     ].copy()

#     route_distance_chart[
#         "case_id"
#     ] = (
#         route_distance_chart[
#             "case_id"
#         ]
#         .astype(str)
#         .str.replace(
#             "PS146_2025_",
#             "",
#             regex=False,
#         )
#     )

#     route_distance_chart = (
#         route_distance_chart
#         .rename(
#             columns={
#                 "case_id":
#                     "Validation Case",

#                 "ais_distance_km":
#                     "Actual Polarstern Route",

#                 "polarguard_distance_km":
#                     "PolarGuard Route",
#             }
#         )
#         .set_index(
#             "Validation Case"
#         )
#     )

#     st.bar_chart(
#         route_distance_chart,
#         use_container_width=True,
#     )

#     st.caption(
#         "Each test case uses the same historical start and destination. "
#         "The first series is the recorded Polarstern route-window distance; "
#         "the second is the corrected PolarGuard recommended-route distance."
#     )

#     st.markdown(
#         "#### Distance Reduction by Validation Case"
#     )

#     show_image_if_exists(
#         "01_distance_reduction_by_case.png",
#         (
#             "Positive values indicate a shorter PolarGuard route. "
#             "Negative values show cases where safety-oriented routing "
#             "produced a longer route."
#         ),
#     )

#     st.caption(
#         "PolarGuard is not designed to minimize distance alone. "
#         "Some cases trade extra distance for lower modeled environmental risk."
#     )

#     # ========================================================
#     # ROUTE OUTCOME SUMMARY
#     # ========================================================

#     st.subheader(
#         "📌 Route Outcome Summary"
#     )

#     total_route_cases = len(summary)
#     feasible_route_cases = int(summary["routing_success"].sum())
#     rejected_route_cases = total_route_cases - feasible_route_cases

#     successful_shorter = int((successful["distance_saved_pct"] > 0).sum())
#     successful_longer = int((successful["distance_saved_pct"] <= 0).sum())

#     route_outcome_col1, route_outcome_col2, route_outcome_col3, route_outcome_col4 = st.columns(4)

#     route_outcome_col1.metric("Frozen Route Cases", total_route_cases)
#     route_outcome_col2.metric("Feasible Routes", f"{feasible_route_cases}/{total_route_cases}")
#     route_outcome_col3.metric("Feasible Routes Shorter", f"{successful_shorter}/{feasible_route_cases}")
#     route_outcome_col4.metric("Safety-Rejected Starts", rejected_route_cases)

#     st.caption(
#         "Feasible means the routing engine successfully returned a route. "
#         "It does not automatically mean that the PolarGuard route was shorter."
#     )

#     route_outcome_rows = []

#     for _, row in summary.iterrows():
#         case_id = str(row["case_id"])
#         horizon_hours = int(row["horizon_hours"])
#         routing_success = bool(row["routing_success"])
#         case_display = case_id.replace("PS146_2025_", "")

#         if routing_success:
#             success_match = successful[successful["case_id"].astype(str) == case_id]

#             if not success_match.empty:
#                 success_row = success_match.iloc[0]
#                 distance_saved_pct = float(success_row["distance_saved_pct"])
#                 actual_distance = float(success_row["ais_distance_km"])
#                 pg_distance = float(success_row["polarguard_distance_km"])
#                 actual_sic = float(success_row["ais_actual_mean_sic_pct"])
#                 pg_sic = float(success_row["pg_actual_mean_sic_pct"])

#                 if distance_saved_pct > 0:
#                     outcome = "Feasible — Shorter"
#                     explanation = (
#                         f"Route generated; {distance_saved_pct:.2f}% shorter "
#                         f"than recorded Polarstern route."
#                     )
#                 else:
#                     outcome = "Feasible — Longer"
#                     explanation = (
#                         f"Route generated; {abs(distance_saved_pct):.2f}% longer. "
#                         f"Safety/risk trade-off."
#                     )

#                 route_outcome_rows.append({
#                     "Case": case_display,
#                     "Horizon (h)": horizon_hours,
#                     "Outcome": outcome,
#                     "Actual Distance (km)": actual_distance,
#                     "PolarGuard Distance (km)": pg_distance,
#                     "Distance Reduction (%)": distance_saved_pct,
#                     "Actual Route SIC (%)": actual_sic,
#                     "PolarGuard Route SIC (%)": pg_sic,
#                     "Explanation": explanation,
#                 })
#             else:
#                 route_outcome_rows.append({
#                     "Case": case_display,
#                     "Horizon (h)": horizon_hours,
#                     "Outcome": "Feasible",
#                     "Actual Distance (km)": np.nan,
#                     "PolarGuard Distance (km)": np.nan,
#                     "Distance Reduction (%)": np.nan,
#                     "Actual Route SIC (%)": np.nan,
#                     "PolarGuard Route SIC (%)": np.nan,
#                     "Explanation": "Route generated successfully.",
#                 })
#         else:
#             reason = str(row.get("reason", "Navigation constraint rejection"))
#             if reason == "nan" or reason.strip() == "":
#                 reason = "Navigation constraint rejection"

#             diagnostic_match = failed[failed["case_id"].astype(str) == case_id]
#             explanation = reason

#             if not diagnostic_match.empty:
#                 diagnostic_row = diagnostic_match.iloc[0]
#                 classification = str(diagnostic_row.get("classification", ""))
#                 predicted_start_sic = pd.to_numeric(diagnostic_row.get("predicted_start_sic_pct", np.nan), errors="coerce")
#                 observed_target_sic = pd.to_numeric(diagnostic_row.get("observed_target_sic_pct", np.nan), errors="coerce")
#                 grid_sensitive = diagnostic_row.get("grid_artifact_suspected", False)
#                 extra_parts = []

#                 if np.isfinite(predicted_start_sic):
#                     extra_parts.append(f"Predicted start SIC {float(predicted_start_sic):.2f}%")
#                 if np.isfinite(observed_target_sic):
#                     extra_parts.append(f"Observed target SIC {float(observed_target_sic):.2f}%")
#                 if classification and classification.lower() != "nan":
#                     extra_parts.append(classification)
#                 if bool(grid_sensitive):
#                     extra_parts.append("Grid-snap sensitivity detected")
#                 if extra_parts:
#                     explanation = reason + " | " + " | ".join(extra_parts)

#             route_outcome_rows.append({
#                 "Case": case_display,
#                 "Horizon (h)": horizon_hours,
#                 "Outcome": "Rejected",
#                 "Actual Distance (km)": pd.to_numeric(row.get("actual_ais_distance_km", np.nan), errors="coerce"),
#                 "PolarGuard Distance (km)": np.nan,
#                 "Distance Reduction (%)": np.nan,
#                 "Actual Route SIC (%)": np.nan,
#                 "PolarGuard Route SIC (%)": np.nan,
#                 "Explanation": explanation,
#             })

#     route_outcome_df = pd.DataFrame(route_outcome_rows)

#     for column in [
#         "Actual Distance (km)",
#         "PolarGuard Distance (km)",
#         "Distance Reduction (%)",
#         "Actual Route SIC (%)",
#         "PolarGuard Route SIC (%)",
#     ]:
#         if column in route_outcome_df.columns:
#             route_outcome_df[column] = pd.to_numeric(route_outcome_df[column], errors="coerce").round(2)

#     st.dataframe(route_outcome_df, use_container_width=True, hide_index=True)

#     st.markdown("#### Route Outcomes")

#     route_outcome_chart = pd.DataFrame({
#         "Outcome": ["Shorter Feasible", "Longer Feasible", "Safety Rejected"],
#         "Cases": [successful_shorter, successful_longer, rejected_route_cases],
#     }).set_index("Outcome")

#     st.bar_chart(route_outcome_chart, use_container_width=True)

#     st.info(
#         "Route-validation interpretation: "
#         f"PolarGuard produced feasible routes for {feasible_route_cases} of {total_route_cases} frozen cases. "
#         f"{successful_shorter} of those feasible routes were shorter than the corresponding recorded Polarstern route window."
#     )

#     st.warning(
#         "The rejected cases are not automatically algorithm crashes. "
#         "For these historical tests, routing was stopped because the mapped start grid cell violated the configured navigation constraints. "
#         "The diagnostic table below should be used to distinguish genuine high-ice rejection from grid-resolution sensitivity."
#     )

#     # ========================================================
#     # CASE TABLE
#     # ========================================================

#     st.subheader(
#         "📋 Successful Test Cases"
#     )

#     table_columns = [
#         "case_id",
#         "horizon_hours",
#         "ais_distance_km",
#         "polarguard_distance_km",
#         "distance_saved_pct",
#         "mean_ais_to_pg_km",
#         "ais_actual_mean_sic_pct",
#         "pg_actual_mean_sic_pct",
#         "ais_min_iceberg_distance_km",
#         "pg_min_iceberg_distance_km",
#     ]

#     available_columns = [
#         col
#         for col in table_columns
#         if col in successful.columns
#     ]

#     display_df = (
#         successful[
#             available_columns
#         ]
#         .copy()
#     )

#     rename_map = {
#         "case_id":
#             "Case",

#         "horizon_hours":
#             "Horizon (h)",

#         "ais_distance_km":
#             "Actual Polarstern Distance (km)",

#         "polarguard_distance_km":
#             "PolarGuard Distance (km)",

#         "distance_saved_pct":
#             "Distance Reduction (%)",

#         "mean_ais_to_pg_km":
#             "Mean Route Deviation (km)",

#         "ais_actual_mean_sic_pct":
#             "Actual Route Observed SIC (%)",

#         "pg_actual_mean_sic_pct":
#             "PG Observed SIC (%)",

#         "ais_min_iceberg_distance_km":
#             "Actual Route Min Iceberg Distance (km)",

#         "pg_min_iceberg_distance_km":
#             "PG Min Iceberg Distance (km)",
#     }

#     display_df = display_df.rename(
#         columns=rename_map
#     )

#     numeric_cols = (
#         display_df.select_dtypes(
#             include=[
#                 "float",
#                 "float64",
#                 "float32",
#             ]
#         ).columns
#     )

#     display_df[
#         numeric_cols
#     ] = (
#         display_df[
#             numeric_cols
#         ]
#         .round(2)
#     )

#     st.dataframe(
#         display_df,
#         use_container_width=True,
#         hide_index=True,
#     )

#     # ========================================================
#     # TEST CASE SELECTOR
#     # ========================================================

#     st.subheader(
#         "🗺️ Inspect an Individual Validation Case"
#     )

#     successful_case_ids = (
#         successful[
#             "case_id"
#         ]
#         .astype(str)
#         .tolist()
#     )

#     selected_case_id = st.selectbox(
#         "Select successful PS146 test case",
#         successful_case_ids,
#     )

#     selected = successful[
#         successful[
#             "case_id"
#         ].astype(str)
#         ==
#         selected_case_id
#     ].iloc[0]

#     case_col1, case_col2, case_col3 = (
#         st.columns(3)
#     )

#     case_col1.metric(
#         "Actual Polarstern Distance",
#         f"{float(selected['ais_distance_km']):.2f} km",
#     )

#     case_col2.metric(
#         "PolarGuard Distance",
#         f"{float(selected['polarguard_distance_km']):.2f} km",
#     )

#     case_col3.metric(
#         "Distance Reduction",
#         f"{float(selected['distance_saved_pct']):.2f}%",
#     )

#     case_col4, case_col5, case_col6 = (
#         st.columns(3)
#     )

#     case_col4.metric(
#         "Observed AIS SIC",
#         f"{float(selected['ais_actual_mean_sic_pct']):.2f}%",
#     )

#     case_col5.metric(
#         "Observed PG SIC",
#         f"{float(selected['pg_actual_mean_sic_pct']):.2f}%",
#     )

#     case_col6.metric(
#         "Route Deviation",
#         f"{float(selected['mean_ais_to_pg_km']):.2f} km",
#     )

#     case_map_file = (
#         f"route_map_{selected_case_id}.png"
#     )

#     case_map_path = (
#         FIGURE_DIR
#         /
#         case_map_file
#     )

#     if case_map_path.exists():

#         st.image(
#             str(
#                 case_map_path
#             ),
#             use_container_width=True,
#             caption=(
#                 f"{selected_case_id}: actual Polarstern track "
#                 "vs PolarGuard recommendation"
#             ),
#         )

#     else:

#         st.info(
#             "A dedicated route-map image was not generated for this case. "
#             "The numerical validation results are still available above."
#         )

#     # ========================================================
#     # FORECAST VS OBSERVED
#     # ========================================================

#     st.subheader(
#         "🎯 Predicted SIC vs Observed SIC"
#     )

#     show_image_if_exists(
#         "07_predicted_vs_observed_pg_sic.png",
#         (
#             "Mean predicted sea-ice concentration compared with "
#             "subsequently observed SIC along PolarGuard routes."
#         ),
#     )

#     st.warning(
#         "The forecast is not perfect. Some high-ice cases show SIC "
#         "underprediction. This limitation is retained in the validation "
#         "instead of being removed."
#     )

#     # ========================================================
#     # ICEBERG CLEARANCE
#     # ========================================================

#     st.subheader(
#         "🧊 Historical Iceberg Clearance"
#     )

#     show_image_if_exists(
#         "03_iceberg_clearance_comparison.png",
#         (
#             "Minimum historical iceberg distance along actual AIS "
#             "and PolarGuard routes."
#         ),
#     )

#     # ========================================================
#     # SAFETY REJECTIONS
#     # ========================================================

#     st.subheader(
#         "🛡️ Safety-Rejected Cases"
#     )

#     st.write(
#         f"{failed_cases} of {total_cases} frozen cases did not produce "
#         "a route under the configured HIGH_ICE_CAPABILITY vessel constraints."
#     )

#     if not failed.empty:

#         failed_columns = [
#             "case_id",
#             "horizon_hours",
#             "grid_snap_distance_km",
#             "predicted_start_sic_pct",
#             "observed_target_sic_pct",
#             "blocked_by_sic",
#             "nearest_feasible_distance_km",
#             "grid_artifact_suspected",
#             "classification",
#         ]

#         failed_columns = [
#             column
#             for column in failed_columns
#             if column in failed.columns
#         ]

#         failed_display = failed[
#             failed_columns
#         ].copy()

#         failed_display = failed_display.rename(
#             columns={
#                 "case_id":
#                     "Case",

#                 "horizon_hours":
#                     "Horizon (h)",

#                 "grid_snap_distance_km":
#                     "Grid Snap (km)",

#                 "predicted_start_sic_pct":
#                     "Predicted Start SIC (%)",

#                 "observed_target_sic_pct":
#                     "Observed Target SIC (%)",

#                 "blocked_by_sic":
#                     "Blocked by SIC",

#                 "nearest_feasible_distance_km":
#                     "Nearest Feasible Cell (km)",

#                 "grid_artifact_suspected":
#                     "Grid Sensitivity",

#                 "classification":
#                     "Diagnosis",
#             }
#         )

#         numeric_cols = (
#             failed_display.select_dtypes(
#                 include=[
#                     "float",
#                     "float64",
#                     "float32",
#                 ]
#             ).columns
#         )

#         failed_display[
#             numeric_cols
#         ] = (
#             failed_display[
#                 numeric_cols
#             ]
#             .round(2)
#         )

#         st.dataframe(
#             failed_display,
#             use_container_width=True,
#             hide_index=True,
#         )

#     show_image_if_exists(
#         "06_validation_outcomes.png",
#         "Feasible vs safety-rejected frozen PS146 validation cases.",
#     )

#     st.info(
#         "Diagnostic review found that four of the five rejected cases "
#         "were consistent with severe high-ice conditions. One 24h case "
#         "showed sensitivity to routing-grid snapping."
#     )

#     # ========================================================
#     # LIMITATIONS
#     # ========================================================

#     st.subheader(
#         "⚠️ Interpretation & Limitations"
#     )

#     st.markdown(
#         """
# - **7.99% is a modeled route-distance comparison**, not a claim that
#   Polarstern would have completed the voyage 7.99% faster.
# - Real research-vessel tracks may contain scientific stations,
#   operational instructions, weather decisions and other objectives
#   that PolarGuard does not model.
# - The routing grid is coarse, which creates angular routes and
#   endpoint snapping.
# - Sea-ice forecasts underpredict some high-ice cases.
# - One rejected case was sensitive to grid resolution.
# - PolarGuard remains a **prototype decision-support system**, not a
#   certified navigation product.
# """
#     )

#     st.success(
#         "Validation conclusion: the historical backtest provides evidence "
#         "that PolarGuard can identify alternative corridors with lower "
#         "observed sea-ice exposure while often reducing modeled route "
#         "distance, but additional operational validation is required."
#     )


from pathlib import Path
import json

import numpy as np
import pandas as pd
import streamlit as st


BASE = Path(__file__).resolve().parent

VALIDATION_ROOT = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps146_2025_validation"
)

COMPARISON_FILE = (
    VALIDATION_ROOT
    / "stage4_route_comparison"
    / "ps146_2025_route_comparison_summary.csv"
)

SUCCESS_FILE = (
    VALIDATION_ROOT
    / "stage4_route_comparison"
    / "ps146_2025_successful_route_comparisons.csv"
)

FAILED_DIAGNOSTIC_FILE = (
    VALIDATION_ROOT
    / "start_cell_diagnostic"
    / "ps146_2025_failed_start_cell_summary.csv"
)

FIGURE_DIR = (
    VALIDATION_ROOT
    / "final_validation_figures"
)

# ============================================================
# FULL-YEAR 2025 MEMBER-1 SIC TESTING
# ============================================================

MODEL_TEST_ROOT = (
    BASE
    / "iceberg"
    / "outputs"
    / "model_testing_2025"
)

SIC_METRICS_FILE = (
    MODEL_TEST_ROOT
    / "sic_2025_metrics.csv"
)

SIC_DAILY_FILE = (
    MODEL_TEST_ROOT
    / "sic_2025_daily_metrics.csv"
)

SIC_MONTHLY_FILE = (
    MODEL_TEST_ROOT
    / "sic_2025_monthly_metrics.csv"
)

SIC_FIGURE_DIR = (
    MODEL_TEST_ROOT
    / "figures"
)

# ============================================================
# FULL-YEAR 2025 SIC SAFETY CLASSIFICATION
# ============================================================

SAFETY_TEST_ROOT = (
    MODEL_TEST_ROOT
    / "safety_classification"
)

SAFETY_SUMMARY_FILE = (
    SAFETY_TEST_ROOT
    / "sic_safety_classification_summary.csv"
)

SAFETY_DAILY_FILE = (
    SAFETY_TEST_ROOT
    / "sic_safety_classification_daily.csv"
)

SAFETY_FIGURE_DIR = (
    SAFETY_TEST_ROOT
    / "figures"
)

# ============================================================
# MEMBER-2 FINAL 2025 ICEBERG TESTING
# ============================================================

MEMBER2_FINAL_ROOT = (
    BASE
    / "iceberg"
    / "outputs"
    / "member2_final_evidence"
)

MEMBER2_SUMMARY_FILE = (
    MEMBER2_FINAL_ROOT
    / "2025_test_summary.csv"
)

MEMBER2_FINAL_JSON = (
    BASE
    / "iceberg"
    / "outputs"
    / "iceberg_final_test_2025.json"
)

MEMBER2_PLOTS_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "plots"
)


@st.cache_data(show_spinner=False)
def load_member2_2025_testing_data():
    """Load final held-out 2025 Member-2 iceberg test evidence."""

    summary = pd.read_csv(
        MEMBER2_SUMMARY_FILE
    )

    with open(
        MEMBER2_FINAL_JSON,
        "r",
        encoding="utf-8",
    ) as file:
        details = json.load(file)

    return summary, details


def show_member2_plot_if_exists(
    filename,
    caption=None,
):
    path = MEMBER2_PLOTS_DIR / filename

    if path.exists():
        st.image(
            str(path),
            use_container_width=True,
            caption=caption,
        )
    else:
        st.warning(
            f"Member-2 figure not found: {filename}"
        )


@st.cache_data(show_spinner=False)
def load_validation_data():

    summary = pd.read_csv(
        COMPARISON_FILE
    )

    successful = pd.read_csv(
        SUCCESS_FILE
    )

    failed = pd.read_csv(
        FAILED_DIAGNOSTIC_FILE
    )

    summary["routing_success"] = (
        summary["routing_success"]
        .astype(str)
        .str.lower()
        .map(
            {
                "true": True,
                "false": False,
            }
        )
        .fillna(False)
    )

    return (
        summary,
        successful,
        failed,
    )


@st.cache_data(show_spinner=False)
def load_sic_testing_data():
    """
    Load full-year 2025 Member-1 forecast testing outputs.
    """

    overall = pd.read_csv(
        SIC_METRICS_FILE
    )

    daily = pd.read_csv(
        SIC_DAILY_FILE
    )

    monthly = pd.read_csv(
        SIC_MONTHLY_FILE
    )

    return (
        overall,
        daily,
        monthly,
    )


def show_sic_image_if_exists(
    filename,
    caption=None,
):
    """
    Display a full-year 2025 SIC testing figure if it exists.
    """

    path = (
        SIC_FIGURE_DIR
        /
        filename
    )

    if path.exists():

        st.image(
            str(path),
            use_container_width=True,
            caption=caption,
        )

    else:

        st.warning(
            f"SIC testing figure not found: {filename}"
        )


@st.cache_data(show_spinner=False)
def load_safety_testing_data():
    """
    Load full-year 2025 dangerous-ice classification outputs.
    """

    summary = pd.read_csv(
        SAFETY_SUMMARY_FILE
    )

    daily = pd.read_csv(
        SAFETY_DAILY_FILE
    )

    return (
        summary,
        daily,
    )


def show_safety_image_if_exists(
    filename,
    caption=None,
):
    """
    Display a dangerous-ice classification figure if it exists.
    """

    path = (
        SAFETY_FIGURE_DIR
        /
        filename
    )

    if path.exists():

        st.image(
            str(path),
            use_container_width=True,
            caption=caption,
        )

    else:

        st.warning(
            f"Safety testing figure not found: {filename}"
        )


def show_image_if_exists(
    filename,
    caption=None,
):

    path = (
        FIGURE_DIR
        /
        filename
    )

    if path.exists():

        st.image(
            str(path),
            use_container_width=True,
            caption=caption,
        )

    else:

        st.warning(
            f"Validation figure not found: {filename}"
        )


def render_validation_2025():

    st.header(
        "🧪 2025 Historical Validation"
    )

    st.markdown(
        """
PolarGuard was evaluated using **held-out 2025 sea-ice data**
and the real **RV Polarstern PS146 vessel track**.

The purpose of this page is to show the difference between:

- **model input / prediction**
- **real observed 2025 conditions**
- **actual recorded Polarstern vessel route**
- **PolarGuard recommended route**

The routing experiment used frozen validation cases so results
were not selected after seeing the routing outcome.
"""
    )

    try:

        summary, successful, failed = (
            load_validation_data()
        )

    except Exception as exc:

        st.error(
            "Could not load the PS146 2025 validation files."
        )

        st.exception(
            exc
        )

        return

    # ========================================================
    # DATA SPLIT
    # ========================================================

    st.subheader(
        "📚 Training vs Testing Data"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Model Training Period",
            "2019–2023",
        )

        st.caption(
            "Historical sea-ice data used for model development."
        )

    with col2:

        st.metric(
            "Held-Out Test Period",
            "2025",
        )

        st.caption(
            "2025 was kept separate for out-of-sample evaluation."
        )

    with col3:

        st.metric(
            "Real Vessel Dataset",
            "Polarstern PS146",
        )

        st.caption(
            "Actual GPS/AIS-style master-track positions from the 2025 expedition."
        )

    st.info(
        "2025 observations are used as ground truth for this historical backtest."
    )

    # ========================================================
    # MAIN METRICS
    # ========================================================

    st.subheader(
        "📊 Final Validation Results"
    )

    total_cases = len(
        summary
    )

    successful_cases = len(
        successful
    )

    failed_cases = (
        total_cases
        -
        successful_cases
    )

    mean_distance_reduction = float(
        successful[
            "distance_saved_pct"
        ].mean()
    )

    median_distance_reduction = float(
        successful[
            "distance_saved_pct"
        ].median()
    )

    mean_ais_sic = float(
        successful[
            "ais_actual_mean_sic_pct"
        ].mean()
    )

    mean_pg_sic = float(
        successful[
            "pg_actual_mean_sic_pct"
        ].mean()
    )

    relative_sic_reduction = (
        (
            mean_ais_sic
            -
            mean_pg_sic
        )
        /
        mean_ais_sic
        *
        100.0
        if mean_ais_sic > 0
        else np.nan
    )

    mean_deviation = float(
        successful[
            "mean_ais_to_pg_km"
        ].mean()
    )

    metric1, metric2, metric3, metric4 = (
        st.columns(4)
    )

    metric1.metric(
        "Frozen Test Cases",
        total_cases,
    )

    metric2.metric(
        "Feasible Routes",
        f"{successful_cases}/{total_cases}",
    )

    metric3.metric(
        "Mean Modeled Distance Reduction",
        f"{mean_distance_reduction:.2f}%",
    )

    metric4.metric(
        "Observed SIC Reduction",
        f"{relative_sic_reduction:.2f}%",
    )

    metric5, metric6, metric7, metric8 = (
        st.columns(4)
    )

    metric5.metric(
        "Median Distance Reduction",
        f"{median_distance_reduction:.2f}%",
    )

    metric6.metric(
        "AIS Mean Observed SIC",
        f"{mean_ais_sic:.2f}%",
    )

    metric7.metric(
        "PolarGuard Mean Observed SIC",
        f"{mean_pg_sic:.2f}%",
    )

    metric8.metric(
        "Mean Route Deviation",
        f"{mean_deviation:.2f} km",
    )

    st.caption(
        "Distance metrics include the exact start → routing-grid connector "
        "and routing-grid → exact destination connector."
    )

    # ========================================================
    # VALIDATION PIPELINE
    # ========================================================

    st.subheader(
        "🔬 How the Test Was Performed"
    )

    st.markdown(
        """
**1. Train / develop model**

`2019–2023 historical SIC`

↓

**2. Freeze the model**

No retraining during the 2025 evaluation.

↓

**3. Feed historical initialization conditions**

PolarGuard receives the sea-ice state available at the beginning
of each selected PS146 route window.

↓

**4. Generate +24h / +48h / +72h forecasts**

↓

**5. Generate PolarGuard route**

The same real vessel start and destination are used.

↓

**6. Compare against real 2025 observations**

The generated route is evaluated using subsequently observed
2025 sea-ice conditions and the actual Polarstern track.
"""
    )

    # ========================================================
    # FULL-YEAR 2025 SIC FORECAST TESTING
    # ========================================================

    st.subheader(
        "🧠 Full-Year 2025 Sea-Ice Forecast Testing"
    )

    st.markdown(
        """
This section evaluates the **frozen Member-1 sea-ice model** on the
held-out **2025 test year**.

For each valid initialization date, PolarGuard used the current SIC map
and the previous three daily SIC maps to generate **+24h, +48h and +72h**
forecasts. Those forecasts were then compared with the corresponding
observed 2025 SIC maps.

The same test also compares PolarGuard with a **persistence baseline**:
`future SIC = current SIC`.
"""
    )

    try:

        sic_overall, sic_daily, sic_monthly = (
            load_sic_testing_data()
        )

        sic_testing_available = True

    except Exception as exc:

        sic_testing_available = False

        st.warning(
            "Full-year 2025 SIC testing files could not be loaded."
        )

        st.caption(
            str(exc)
        )

    if sic_testing_available:

        sic_overall = (
            sic_overall
            .sort_values(
                "horizon_hours"
            )
            .reset_index(
                drop=True
            )
        )

        # ----------------------------------------------------
        # TEST COVERAGE
        # ----------------------------------------------------

        test_initializations = int(
            sic_overall[
                "test_initializations"
            ].max()
        )

        coverage_col1, coverage_col2, coverage_col3, coverage_col4 = (
            st.columns(4)
        )

        coverage_col1.metric(
            "Held-Out Test Year",
            "2025",
        )

        coverage_col2.metric(
            "Valid Initializations",
            f"{test_initializations}",
        )

        coverage_col3.metric(
            "Forecast Horizons",
            "24h / 48h / 72h",
        )

        coverage_col4.metric(
            "Evaluation Grid",
            "332 × 316",
        )

        st.caption(
            "The full-year test uses observed 2025 SIC as ground truth. "
            "The model is evaluated without retraining."
        )

        # ----------------------------------------------------
        # RMSE METRIC CARDS
        # ----------------------------------------------------

        st.markdown(
            "#### Forecast Error by Horizon"
        )

        rmse_cols = st.columns(3)

        for column, (_, row) in zip(
            rmse_cols,
            sic_overall.iterrows(),
        ):

            horizon_hours = int(
                row[
                    "horizon_hours"
                ]
            )

            rmse_points = float(
                row[
                    "rmse"
                ]
                *
                100.0
            )

            persistence_rmse_points = float(
                row[
                    "persistence_rmse"
                ]
                *
                100.0
            )

            improvement = float(
                row[
                    "rmse_improvement_vs_persistence_pct"
                ]
            )

            column.metric(
                f"+{horizon_hours}h RMSE",
                f"{rmse_points:.2f} SIC pts",
                delta=(
                    f"{improvement:+.2f}% vs persistence"
                ),
            )

            column.caption(
                f"Persistence RMSE: "
                f"{persistence_rmse_points:.2f} SIC pts"
            )

        # ----------------------------------------------------
        # R2 CARDS
        # ----------------------------------------------------

        r2_cols = st.columns(3)

        for column, (_, row) in zip(
            r2_cols,
            sic_overall.iterrows(),
        ):

            horizon_hours = int(
                row[
                    "horizon_hours"
                ]
            )

            column.metric(
                f"+{horizon_hours}h R²",
                f"{float(row['r2']):.4f}",
            )

        # ----------------------------------------------------
        # ACTUAL VS PREDICTED METRICS TABLE
        # ----------------------------------------------------

        st.markdown(
            "#### Actual vs Predicted SIC Metrics"
        )

        sic_table = sic_overall[
            [
                "horizon_hours",
                "test_initializations",
                "actual_mean_sic",
                "predicted_mean_sic",
                "mae",
                "rmse",
                "bias",
                "r2",
                "persistence_mae",
                "persistence_rmse",
                "mae_improvement_vs_persistence_pct",
                "rmse_improvement_vs_persistence_pct",
            ]
        ].copy()

        for column in [
            "actual_mean_sic",
            "predicted_mean_sic",
            "mae",
            "rmse",
            "bias",
            "persistence_mae",
            "persistence_rmse",
        ]:

            sic_table[
                column
            ] = (
                sic_table[
                    column
                ]
                *
                100.0
            )

        sic_table = sic_table.rename(
            columns={
                "horizon_hours":
                    "Horizon (h)",

                "test_initializations":
                    "Test Initializations",

                "actual_mean_sic":
                    "Actual Mean SIC (%)",

                "predicted_mean_sic":
                    "Predicted Mean SIC (%)",

                "mae":
                    "MAE (SIC pts)",

                "rmse":
                    "RMSE (SIC pts)",

                "bias":
                    "Bias (SIC pts)",

                "r2":
                    "R²",

                "persistence_mae":
                    "Persistence MAE (SIC pts)",

                "persistence_rmse":
                    "Persistence RMSE (SIC pts)",

                "mae_improvement_vs_persistence_pct":
                    "MAE Improvement vs Persistence (%)",

                "rmse_improvement_vs_persistence_pct":
                    "RMSE Improvement vs Persistence (%)",
            }
        )

        st.dataframe(
            sic_table.round(4),
            use_container_width=True,
            hide_index=True,
        )

        st.info(
            "Interpretation: lower MAE/RMSE is better. Bias near zero is better. "
            "R² closer to 1 indicates stronger agreement with observed spatial SIC. "
            "Positive persistence-improvement values mean PolarGuard performs better "
            "than simply assuming future SIC equals current SIC."
        )

        # ----------------------------------------------------
        # CORE SIC TESTING FIGURES
        # ----------------------------------------------------

        st.markdown(
            "#### PolarGuard Forecast Accuracy"
        )

        fig_col1, fig_col2 = st.columns(2)

        with fig_col1:

            show_sic_image_if_exists(
                "01_rmse_by_horizon.png",
                (
                    "Full-year 2025 RMSE for +24h, +48h and +72h "
                    "sea-ice forecasts."
                ),
            )

        with fig_col2:

            show_sic_image_if_exists(
                "03_r2_by_horizon.png",
                (
                    "Full-year 2025 R² by forecast horizon."
                ),
            )

        st.markdown(
            "#### Actual SIC vs Predicted SIC"
        )

        show_sic_image_if_exists(
            "04_actual_vs_predicted_mean_sic.png",
            (
                "Observed 2025 mean SIC compared with PolarGuard "
                "predicted mean SIC at each forecast horizon."
            ),
        )

        # ----------------------------------------------------
        # PERSISTENCE BASELINE
        # ----------------------------------------------------

        st.markdown(
            "#### PolarGuard vs Persistence Baseline"
        )

        baseline_col1, baseline_col2 = st.columns(2)

        with baseline_col1:

            show_sic_image_if_exists(
                "02_rmse_vs_persistence.png",
                (
                    "PolarGuard RMSE compared with the persistence "
                    "baseline at each forecast horizon."
                ),
            )

        with baseline_col2:

            show_sic_image_if_exists(
                "09_rmse_improvement_vs_persistence.png",
                (
                    "Positive values indicate lower RMSE than the "
                    "persistence baseline."
                ),
            )

        st.caption(
            "The 24h MAE is slightly worse than persistence, while RMSE "
            "improves at all three horizons. This result is shown rather "
            "than hidden because the dashboard reports the complete test."
        )

        # ----------------------------------------------------
        # MONTHLY TESTING
        # ----------------------------------------------------

        st.markdown(
            "#### Monthly Performance Across 2025"
        )

        monthly_col1, monthly_col2 = st.columns(2)

        with monthly_col1:

            show_sic_image_if_exists(
                "06_monthly_mae_2025.png",
                (
                    "Monthly MAE across the held-out 2025 test year."
                ),
            )

        with monthly_col2:

            show_sic_image_if_exists(
                "07_monthly_rmse_2025.png",
                (
                    "Monthly RMSE across the held-out 2025 test year."
                ),
            )

        show_sic_image_if_exists(
            "08_monthly_actual_vs_predicted_sic.png",
            (
                "Monthly observed SIC compared with PolarGuard predicted "
                "SIC through the full 2025 test year."
            ),
        )

        # ----------------------------------------------------
        # BIAS
        # ----------------------------------------------------

        with st.expander(
            "Forecast bias details"
        ):

            show_sic_image_if_exists(
                "05_bias_by_horizon.png",
                (
                    "Negative values indicate slight average SIC "
                    "underprediction."
                ),
            )

            bias_table = sic_overall[
                [
                    "horizon_hours",
                    "bias",
                ]
            ].copy()

            bias_table[
                "bias"
            ] = (
                bias_table[
                    "bias"
                ]
                *
                100.0
            )

            bias_table = bias_table.rename(
                columns={
                    "horizon_hours":
                        "Horizon (h)",

                    "bias":
                        "Bias (SIC percentage points)",
                }
            )

            st.dataframe(
                bias_table.round(4),
                use_container_width=True,
                hide_index=True,
            )

        st.success(
            "Full-year SIC conclusion: PolarGuard maintained high spatial "
            "agreement with observed 2025 SIC (R² > 0.96 at all horizons) "
            "and reduced RMSE relative to persistence at +24h, +48h and +72h."
        )

        st.divider()

    # ========================================================
    # DANGEROUS-ICE SAFETY CLASSIFICATION
    # ========================================================

    st.subheader(
        "🛡️ Dangerous-Ice Safety Classification"
    )

    st.markdown(
        """
For the safety test, a grid cell is treated as **unsafe** when
observed sea-ice concentration is **80% or greater**.

The positive class is therefore **UNSAFE ICE**.

Because PolarGuard is intended as a safety-oriented decision-support
system, the most important measures here are:

- **Unsafe Recall** — how many truly unsafe cells were detected.
- **Unsafe Precision** — how often an unsafe warning was correct.
- **Unsafe F1** — balance between precision and recall.
- **False-Safe Rate** — actual unsafe cells incorrectly predicted as safe.
"""
    )

    try:

        safety_summary, safety_daily = (
            load_safety_testing_data()
        )

        safety_testing_available = True

    except Exception as exc:

        safety_testing_available = False

        st.warning(
            "Dangerous-ice safety testing files could not be loaded."
        )

        st.caption(
            str(exc)
        )

    if safety_testing_available:

        safety_summary = (
            safety_summary
            .sort_values(
                "horizon_hours"
            )
            .reset_index(
                drop=True
            )
        )

        st.info(
            "Unsafe threshold used for this validation: SIC ≥ 80%. "
            "Overall accuracy is shown, but unsafe recall and false-safe "
            "rate are more important for navigation safety."
        )

        # ----------------------------------------------------
        # HEADLINE SAFETY METRICS
        # ----------------------------------------------------

        recall_cols = st.columns(3)

        for column, (_, row) in zip(
            recall_cols,
            safety_summary.iterrows(),
        ):

            horizon_hours = int(
                row[
                    "horizon_hours"
                ]
            )

            recall_pct = float(
                row[
                    "unsafe_recall"
                ]
                *
                100.0
            )

            false_safe_pct = float(
                row[
                    "false_safe_rate"
                ]
                *
                100.0
            )

            column.metric(
                f"+{horizon_hours}h Unsafe Recall",
                f"{recall_pct:.2f}%",
                delta=(
                    f"False-safe {false_safe_pct:.2f}%"
                ),
                delta_color="off",
            )

        precision_cols = st.columns(3)

        for column, (_, row) in zip(
            precision_cols,
            safety_summary.iterrows(),
        ):

            horizon_hours = int(
                row[
                    "horizon_hours"
                ]
            )

            precision_pct = float(
                row[
                    "unsafe_precision"
                ]
                *
                100.0
            )

            f1_pct = float(
                row[
                    "unsafe_f1"
                ]
                *
                100.0
            )

            column.metric(
                f"+{horizon_hours}h Unsafe Precision",
                f"{precision_pct:.2f}%",
            )

            column.caption(
                f"Unsafe F1: {f1_pct:.2f}%"
            )

        # ----------------------------------------------------
        # SAFETY TABLE
        # ----------------------------------------------------

        st.markdown(
            "#### Dangerous-Ice Classification Metrics"
        )

        safety_table = safety_summary[
            [
                "horizon_hours",
                "test_initializations",
                "true_unsafe",
                "false_safe",
                "false_unsafe",
                "true_safe",
                "unsafe_precision",
                "unsafe_recall",
                "unsafe_f1",
                "false_safe_rate",
                "accuracy",
            ]
        ].copy()

        for column in [
            "unsafe_precision",
            "unsafe_recall",
            "unsafe_f1",
            "false_safe_rate",
            "accuracy",
        ]:

            safety_table[
                column
            ] = (
                safety_table[
                    column
                ]
                *
                100.0
            )

        safety_table = safety_table.rename(
            columns={
                "horizon_hours":
                    "Horizon (h)",

                "test_initializations":
                    "Test Initializations",

                "true_unsafe":
                    "True Unsafe",

                "false_safe":
                    "False Safe",

                "false_unsafe":
                    "False Unsafe",

                "true_safe":
                    "True Safe",

                "unsafe_precision":
                    "Unsafe Precision (%)",

                "unsafe_recall":
                    "Unsafe Recall (%)",

                "unsafe_f1":
                    "Unsafe F1 (%)",

                "false_safe_rate":
                    "False-Safe Rate (%)",

                "accuracy":
                    "Overall Accuracy (%)",
            }
        )

        st.dataframe(
            safety_table.round(3),
            use_container_width=True,
            hide_index=True,
        )

        # ----------------------------------------------------
        # SAFETY FIGURES
        # ----------------------------------------------------

        st.markdown(
            "#### Safety Performance by Forecast Horizon"
        )

        safety_fig_1, safety_fig_2 = st.columns(2)

        with safety_fig_1:

            show_safety_image_if_exists(
                "01_unsafe_precision_recall_f1.png",
                (
                    "Unsafe precision, recall and F1 for the held-out "
                    "2025 dangerous-ice classification test."
                ),
            )

        with safety_fig_2:

            show_safety_image_if_exists(
                "02_false_safe_rate.png",
                (
                    "Safety-critical false-safe rate: actual unsafe cells "
                    "that PolarGuard classified as safe."
                ),
            )

        st.markdown(
            "#### Confusion Matrices"
        )

        cm1, cm2, cm3 = st.columns(3)

        with cm1:

            show_safety_image_if_exists(
                "confusion_matrix_24h.png",
                "+24h dangerous-ice confusion matrix",
            )

        with cm2:

            show_safety_image_if_exists(
                "confusion_matrix_48h.png",
                "+48h dangerous-ice confusion matrix",
            )

        with cm3:

            show_safety_image_if_exists(
                "confusion_matrix_72h.png",
                "+72h dangerous-ice confusion matrix",
            )

        st.success(
            "Safety conclusion: unsafe-ice recall remained above 95% "
            "through +72h. The false-safe rate increased with forecast "
            "horizon, from about 2.6% at +24h to about 4.8% at +72h, "
            "so longer-horizon routing should be treated more cautiously."
        )

        st.divider()

    # ========================================================
    # MEMBER-2 FINAL 2025 ICEBERG TESTING
    # ========================================================

    st.subheader(
        "🧊 2025 Iceberg Forecast Validation"
    )

    st.markdown(
        """
Member 2 was evaluated on the **locked 2025 test set** using historical
iceberg positions as ground truth. For every 24h, 48h and 72h forecast,
the predicted iceberg position is compared with the actual future position.

The table and charts below show **position error**, **safety-radius hit rates**,
and comparison with the best simple motion baseline.
"""
    )

    try:
        member2_summary, member2_details = (
            load_member2_2025_testing_data()
        )
        member2_available = True
    except Exception as exc:
        member2_available = False
        st.warning(
            "Member-2 2025 test evidence could not be loaded."
        )
        st.caption(str(exc))

    if member2_available:

        member2_summary = (
            member2_summary
            .sort_values("horizon_hours")
            .reset_index(drop=True)
        )

        st.info(
            "Strict split: training = 2019–2023, validation = 2024, "
            "final unseen test = 2025. Each horizon contains 14,694 "
            "held-out test samples in the current evidence file."
        )

        # ----------------------------------------------------
        # HEADLINE METRICS
        # ----------------------------------------------------

        rmse_cols = st.columns(3)

        for column, (_, row) in zip(
            rmse_cols,
            member2_summary.iterrows(),
        ):
            horizon = int(row["horizon_hours"])
            rmse = float(row["rmse_km"])
            improvement = float(
                row["improvement_vs_baseline_pct"]
            )

            column.metric(
                f"+{horizon}h Position RMSE",
                f"{rmse:.2f} km",
                delta=f"{improvement:.2f}% vs baseline",
            )

        accuracy_cols = st.columns(3)

        for column, (_, row) in zip(
            accuracy_cols,
            member2_summary.iterrows(),
        ):
            horizon = int(row["horizon_hours"])
            mean_error = float(row["mean_error_km"])
            within_10 = float(row["within_10km_pct"])

            column.metric(
                f"+{horizon}h Mean Error",
                f"{mean_error:.2f} km",
            )
            column.caption(
                f"{within_10:.2f}% within 10 km"
            )

        # ----------------------------------------------------
        # FINAL 2025 TABLE
        # ----------------------------------------------------

        st.markdown(
            "#### Actual vs Predicted Position-Error Summary"
        )

        member2_table = member2_summary[
            [
                "horizon_hours",
                "samples",
                "rmse_km",
                "mean_error_km",
                "median_error_km",
                "p95_error_km",
                "within_5km_pct",
                "within_10km_pct",
                "baseline_rmse_km",
                "improvement_vs_baseline_pct",
            ]
        ].copy()

        member2_table = member2_table.rename(
            columns={
                "horizon_hours": "Horizon (h)",
                "samples": "2025 Test Samples",
                "rmse_km": "Model RMSE (km)",
                "mean_error_km": "Mean Error (km)",
                "median_error_km": "Median Error (km)",
                "p95_error_km": "P95 Error (km)",
                "within_5km_pct": "Within 5 km (%)",
                "within_10km_pct": "Within 10 km (%)",
                "baseline_rmse_km": "Best Baseline RMSE (km)",
                "improvement_vs_baseline_pct": "RMSE Improvement (%)",
            }
        )

        st.dataframe(
            member2_table.round(2),
            use_container_width=True,
            hide_index=True,
        )

        # ----------------------------------------------------
        # MODEL VS BASELINE COMPARISON
        # ----------------------------------------------------

        st.markdown(
            "#### Model vs Best Motion Baseline"
        )

        rmse_compare = member2_summary[
            [
                "horizon_hours",
                "rmse_km",
                "baseline_rmse_km",
            ]
        ].copy()

        rmse_compare["Horizon"] = (
            "+"
            + rmse_compare["horizon_hours"].astype(int).astype(str)
            + "h"
        )

        rmse_compare = (
            rmse_compare
            .rename(
                columns={
                    "rmse_km": "PolarGuard",
                    "baseline_rmse_km": "Best Baseline",
                }
            )
            .set_index("Horizon")
            [["PolarGuard", "Best Baseline"]]
        )

        st.bar_chart(
            rmse_compare,
            use_container_width=True,
        )

        # ----------------------------------------------------
        # SAFETY-RADIUS / DISTANCE-BAND COMPARISON
        # ----------------------------------------------------

        st.markdown(
            "#### Prediction Distance Bands"
        )

        radius_compare = member2_summary[
            [
                "horizon_hours",
                "within_5km_pct",
                "within_10km_pct",
            ]
        ].copy()

        radius_compare["Horizon"] = (
            "+"
            + radius_compare["horizon_hours"].astype(int).astype(str)
            + "h"
        )

        radius_compare = (
            radius_compare
            .rename(
                columns={
                    "within_5km_pct": "Within 5 km",
                    "within_10km_pct": "Within 10 km",
                }
            )
            .set_index("Horizon")
            [["Within 5 km", "Within 10 km"]]
        )

        st.bar_chart(
            radius_compare,
            use_container_width=True,
        )

        st.caption(
            "Distance-band percentages are direct held-out 2025 position-error "
            "rates. They should not be described as collision probability."
        )

        # ----------------------------------------------------
        # TAIL ERROR / P95
        # ----------------------------------------------------

        st.markdown(
            "#### P95 Position Error"
        )

        p95_chart = member2_summary[
            [
                "horizon_hours",
                "p95_error_km",
            ]
        ].copy()

        p95_chart["Horizon"] = (
            "+"
            + p95_chart["horizon_hours"].astype(int).astype(str)
            + "h"
        )

        p95_chart = (
            p95_chart
            .rename(
                columns={
                    "p95_error_km": "P95 Error (km)"
                }
            )
            .set_index("Horizon")
            [["P95 Error (km)"]]
        )

        st.bar_chart(
            p95_chart,
            use_container_width=True,
        )

        # ----------------------------------------------------
        # OPTIONAL EXISTING TRAJECTORY FIGURES
        # ----------------------------------------------------

        st.markdown(
            "#### Example Iceberg Trajectory Comparisons"
        )

        trajectory_cols = st.columns(3)

        with trajectory_cols[0]:
            show_member2_plot_if_exists(
                "a23a_trajectory_24h.png",
                "24h trajectory example",
            )

        with trajectory_cols[1]:
            show_member2_plot_if_exists(
                "a23a_trajectory_48h.png",
                "48h trajectory example",
            )

        with trajectory_cols[2]:
            show_member2_plot_if_exists(
                "a23a_trajectory_72h.png",
                "72h trajectory example",
            )

        st.success(
            "Member-2 conclusion: on the locked 2025 test set, PolarGuard "
            "beats the best simple motion baseline at 24h, 48h and 72h. "
            "Error increases with forecast horizon, as expected, while the "
            "72h forecast still keeps 85.10% of predictions within 10 km."
        )

        st.divider()

    # ========================================================
    # ROUTE VALIDATION
    # ========================================================

    st.subheader(
        "🚢 Historical Route Backtesting"
    )

    st.caption(
        "The following section compares the actual recorded Polarstern PS146 "
        "route windows with PolarGuard recommendations generated for the same "
        "historical start and destination."
    )

    # ========================================================
    # ACTUAL VS PREDICTED
    # ========================================================

    st.subheader(
        "🌊 Actual Route vs PolarGuard Route"
    )

    show_image_if_exists(
        "02_actual_sic_ais_vs_polarguard.png",
        (
            "Observed 2025 sea-ice concentration along the real AIS route "
            "and the PolarGuard route."
        ),
    )

    st.success(
        f"Across the {successful_cases} feasible cases, observed mean SIC "
        f"decreased from {mean_ais_sic:.2f}% on the actual AIS routes "
        f"to {mean_pg_sic:.2f}% on PolarGuard routes — a "
        f"{relative_sic_reduction:.2f}% relative reduction."
    )

    # ========================================================
    # DISTANCE
    # ========================================================

    st.subheader(
        "📏 Route Distance Comparison"
    )

    mean_actual_distance = float(
        successful[
            "ais_distance_km"
        ].mean()
    )

    mean_polarguard_distance = float(
        successful[
            "polarguard_distance_km"
        ].mean()
    )

    distance_metric_1, distance_metric_2, distance_metric_3 = (
        st.columns(3)
    )

    distance_metric_1.metric(
        "Mean Actual Polarstern Distance",
        f"{mean_actual_distance:.2f} km",
    )

    distance_metric_2.metric(
        "Mean PolarGuard Distance",
        f"{mean_polarguard_distance:.2f} km",
    )

    distance_metric_3.metric(
        "Mean Modeled Distance Reduction",
        f"{mean_distance_reduction:.2f}%",
    )

    st.markdown(
        "#### Actual Polarstern Route vs PolarGuard Route"
    )

    route_distance_chart = successful[
        [
            "case_id",
            "ais_distance_km",
            "polarguard_distance_km",
        ]
    ].copy()

    route_distance_chart[
        "case_id"
    ] = (
        route_distance_chart[
            "case_id"
        ]
        .astype(str)
        .str.replace(
            "PS146_2025_",
            "",
            regex=False,
        )
    )

    route_distance_chart = (
        route_distance_chart
        .rename(
            columns={
                "case_id":
                    "Validation Case",

                "ais_distance_km":
                    "Actual Polarstern Route",

                "polarguard_distance_km":
                    "PolarGuard Route",
            }
        )
        .set_index(
            "Validation Case"
        )
    )

    st.bar_chart(
        route_distance_chart,
        use_container_width=True,
    )

    st.caption(
        "Each test case uses the same historical start and destination. "
        "The first series is the recorded Polarstern route-window distance; "
        "the second is the corrected PolarGuard recommended-route distance."
    )

    st.markdown(
        "#### Distance Reduction by Validation Case"
    )

    show_image_if_exists(
        "01_distance_reduction_by_case.png",
        (
            "Positive values indicate a shorter PolarGuard route. "
            "Negative values show cases where safety-oriented routing "
            "produced a longer route."
        ),
    )

    st.caption(
        "PolarGuard is not designed to minimize distance alone. "
        "Some cases trade extra distance for lower modeled environmental risk."
    )

    # ========================================================
    # ROUTE OUTCOME SUMMARY
    # ========================================================

    st.subheader(
        "📌 Route Outcome Summary"
    )

    total_route_cases = len(summary)
    feasible_route_cases = int(summary["routing_success"].sum())
    rejected_route_cases = total_route_cases - feasible_route_cases

    successful_shorter = int((successful["distance_saved_pct"] > 0).sum())
    successful_longer = int((successful["distance_saved_pct"] <= 0).sum())

    route_outcome_col1, route_outcome_col2, route_outcome_col3, route_outcome_col4 = st.columns(4)

    route_outcome_col1.metric("Frozen Route Cases", total_route_cases)
    route_outcome_col2.metric("Feasible Routes", f"{feasible_route_cases}/{total_route_cases}")
    route_outcome_col3.metric("Feasible Routes Shorter", f"{successful_shorter}/{feasible_route_cases}")
    route_outcome_col4.metric("Safety-Rejected Starts", rejected_route_cases)

    st.caption(
        "Feasible means the routing engine successfully returned a route. "
        "It does not automatically mean that the PolarGuard route was shorter."
    )

    route_outcome_rows = []

    for _, row in summary.iterrows():
        case_id = str(row["case_id"])
        horizon_hours = int(row["horizon_hours"])
        routing_success = bool(row["routing_success"])
        case_display = case_id.replace("PS146_2025_", "")

        if routing_success:
            success_match = successful[successful["case_id"].astype(str) == case_id]

            if not success_match.empty:
                success_row = success_match.iloc[0]
                distance_saved_pct = float(success_row["distance_saved_pct"])
                actual_distance = float(success_row["ais_distance_km"])
                pg_distance = float(success_row["polarguard_distance_km"])
                actual_sic = float(success_row["ais_actual_mean_sic_pct"])
                pg_sic = float(success_row["pg_actual_mean_sic_pct"])

                if distance_saved_pct > 0:
                    outcome = "Feasible — Shorter"
                    explanation = (
                        f"Route generated; {distance_saved_pct:.2f}% shorter "
                        f"than recorded Polarstern route."
                    )
                else:
                    outcome = "Feasible — Longer"
                    explanation = (
                        f"Route generated; {abs(distance_saved_pct):.2f}% longer. "
                        f"Safety/risk trade-off."
                    )

                route_outcome_rows.append({
                    "Case": case_display,
                    "Horizon (h)": horizon_hours,
                    "Outcome": outcome,
                    "Actual Distance (km)": actual_distance,
                    "PolarGuard Distance (km)": pg_distance,
                    "Distance Reduction (%)": distance_saved_pct,
                    "Actual Route SIC (%)": actual_sic,
                    "PolarGuard Route SIC (%)": pg_sic,
                    "Explanation": explanation,
                })
            else:
                route_outcome_rows.append({
                    "Case": case_display,
                    "Horizon (h)": horizon_hours,
                    "Outcome": "Feasible",
                    "Actual Distance (km)": np.nan,
                    "PolarGuard Distance (km)": np.nan,
                    "Distance Reduction (%)": np.nan,
                    "Actual Route SIC (%)": np.nan,
                    "PolarGuard Route SIC (%)": np.nan,
                    "Explanation": "Route generated successfully.",
                })
        else:
            reason = str(row.get("reason", "Navigation constraint rejection"))
            if reason == "nan" or reason.strip() == "":
                reason = "Navigation constraint rejection"

            diagnostic_match = failed[failed["case_id"].astype(str) == case_id]
            explanation = reason

            if not diagnostic_match.empty:
                diagnostic_row = diagnostic_match.iloc[0]
                classification = str(diagnostic_row.get("classification", ""))
                predicted_start_sic = pd.to_numeric(diagnostic_row.get("predicted_start_sic_pct", np.nan), errors="coerce")
                observed_target_sic = pd.to_numeric(diagnostic_row.get("observed_target_sic_pct", np.nan), errors="coerce")
                grid_sensitive = diagnostic_row.get("grid_artifact_suspected", False)
                extra_parts = []

                if np.isfinite(predicted_start_sic):
                    extra_parts.append(f"Predicted start SIC {float(predicted_start_sic):.2f}%")
                if np.isfinite(observed_target_sic):
                    extra_parts.append(f"Observed target SIC {float(observed_target_sic):.2f}%")
                if classification and classification.lower() != "nan":
                    extra_parts.append(classification)
                if bool(grid_sensitive):
                    extra_parts.append("Grid-snap sensitivity detected")
                if extra_parts:
                    explanation = reason + " | " + " | ".join(extra_parts)

            route_outcome_rows.append({
                "Case": case_display,
                "Horizon (h)": horizon_hours,
                "Outcome": "Rejected",
                "Actual Distance (km)": pd.to_numeric(row.get("actual_ais_distance_km", np.nan), errors="coerce"),
                "PolarGuard Distance (km)": np.nan,
                "Distance Reduction (%)": np.nan,
                "Actual Route SIC (%)": np.nan,
                "PolarGuard Route SIC (%)": np.nan,
                "Explanation": explanation,
            })

    route_outcome_df = pd.DataFrame(route_outcome_rows)

    for column in [
        "Actual Distance (km)",
        "PolarGuard Distance (km)",
        "Distance Reduction (%)",
        "Actual Route SIC (%)",
        "PolarGuard Route SIC (%)",
    ]:
        if column in route_outcome_df.columns:
            route_outcome_df[column] = pd.to_numeric(route_outcome_df[column], errors="coerce").round(2)

    st.dataframe(route_outcome_df, use_container_width=True, hide_index=True)

    st.markdown("#### Route Outcomes")

    route_outcome_chart = pd.DataFrame({
        "Outcome": ["Shorter Feasible", "Longer Feasible", "Safety Rejected"],
        "Cases": [successful_shorter, successful_longer, rejected_route_cases],
    }).set_index("Outcome")

    st.bar_chart(route_outcome_chart, use_container_width=True)

    st.info(
        "Route-validation interpretation: "
        f"PolarGuard produced feasible routes for {feasible_route_cases} of {total_route_cases} frozen cases. "
        f"{successful_shorter} of those feasible routes were shorter than the corresponding recorded Polarstern route window."
    )

    st.warning(
        "The rejected cases are not automatically algorithm crashes. "
        "For these historical tests, routing was stopped because the mapped start grid cell violated the configured navigation constraints. "
        "The diagnostic table below should be used to distinguish genuine high-ice rejection from grid-resolution sensitivity."
    )

    # ========================================================
    # CASE TABLE
    # ========================================================

    st.subheader(
        "📋 Successful Test Cases"
    )

    table_columns = [
        "case_id",
        "horizon_hours",
        "ais_distance_km",
        "polarguard_distance_km",
        "distance_saved_pct",
        "mean_ais_to_pg_km",
        "ais_actual_mean_sic_pct",
        "pg_actual_mean_sic_pct",
        "ais_min_iceberg_distance_km",
        "pg_min_iceberg_distance_km",
    ]

    available_columns = [
        col
        for col in table_columns
        if col in successful.columns
    ]

    display_df = (
        successful[
            available_columns
        ]
        .copy()
    )

    rename_map = {
        "case_id":
            "Case",

        "horizon_hours":
            "Horizon (h)",

        "ais_distance_km":
            "Actual Polarstern Distance (km)",

        "polarguard_distance_km":
            "PolarGuard Distance (km)",

        "distance_saved_pct":
            "Distance Reduction (%)",

        "mean_ais_to_pg_km":
            "Mean Route Deviation (km)",

        "ais_actual_mean_sic_pct":
            "Actual Route Observed SIC (%)",

        "pg_actual_mean_sic_pct":
            "PG Observed SIC (%)",

        "ais_min_iceberg_distance_km":
            "Actual Route Min Iceberg Distance (km)",

        "pg_min_iceberg_distance_km":
            "PG Min Iceberg Distance (km)",
    }

    display_df = display_df.rename(
        columns=rename_map
    )

    numeric_cols = (
        display_df.select_dtypes(
            include=[
                "float",
                "float64",
                "float32",
            ]
        ).columns
    )

    display_df[
        numeric_cols
    ] = (
        display_df[
            numeric_cols
        ]
        .round(2)
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    # ========================================================
    # TEST CASE SELECTOR
    # ========================================================

    st.subheader(
        "🗺️ Inspect an Individual Validation Case"
    )

    successful_case_ids = (
        successful[
            "case_id"
        ]
        .astype(str)
        .tolist()
    )

    selected_case_id = st.selectbox(
        "Select successful PS146 test case",
        successful_case_ids,
    )

    selected = successful[
        successful[
            "case_id"
        ].astype(str)
        ==
        selected_case_id
    ].iloc[0]

    case_col1, case_col2, case_col3 = (
        st.columns(3)
    )

    case_col1.metric(
        "Actual Polarstern Distance",
        f"{float(selected['ais_distance_km']):.2f} km",
    )

    case_col2.metric(
        "PolarGuard Distance",
        f"{float(selected['polarguard_distance_km']):.2f} km",
    )

    case_col3.metric(
        "Distance Reduction",
        f"{float(selected['distance_saved_pct']):.2f}%",
    )

    case_col4, case_col5, case_col6 = (
        st.columns(3)
    )

    case_col4.metric(
        "Observed AIS SIC",
        f"{float(selected['ais_actual_mean_sic_pct']):.2f}%",
    )

    case_col5.metric(
        "Observed PG SIC",
        f"{float(selected['pg_actual_mean_sic_pct']):.2f}%",
    )

    case_col6.metric(
        "Route Deviation",
        f"{float(selected['mean_ais_to_pg_km']):.2f} km",
    )

    case_map_file = (
        f"route_map_{selected_case_id}.png"
    )

    case_map_path = (
        FIGURE_DIR
        /
        case_map_file
    )

    if case_map_path.exists():

        st.image(
            str(
                case_map_path
            ),
            use_container_width=True,
            caption=(
                f"{selected_case_id}: actual Polarstern track "
                "vs PolarGuard recommendation"
            ),
        )

    else:

        st.info(
            "A dedicated route-map image was not generated for this case. "
            "The numerical validation results are still available above."
        )

    # ========================================================
    # FORECAST VS OBSERVED
    # ========================================================

    st.subheader(
        "🎯 Predicted SIC vs Observed SIC"
    )

    show_image_if_exists(
        "07_predicted_vs_observed_pg_sic.png",
        (
            "Mean predicted sea-ice concentration compared with "
            "subsequently observed SIC along PolarGuard routes."
        ),
    )

    st.warning(
        "The forecast is not perfect. Some high-ice cases show SIC "
        "underprediction. This limitation is retained in the validation "
        "instead of being removed."
    )

    # ========================================================
    # ICEBERG CLEARANCE
    # ========================================================

    st.subheader(
        "🧊 Historical Iceberg Clearance"
    )

    show_image_if_exists(
        "03_iceberg_clearance_comparison.png",
        (
            "Minimum historical iceberg distance along actual AIS "
            "and PolarGuard routes."
        ),
    )

    # ========================================================
    # SAFETY REJECTIONS
    # ========================================================

    st.subheader(
        "🛡️ Safety-Rejected Cases"
    )

    st.write(
        f"{failed_cases} of {total_cases} frozen cases did not produce "
        "a route under the configured HIGH_ICE_CAPABILITY vessel constraints."
    )

    if not failed.empty:

        failed_columns = [
            "case_id",
            "horizon_hours",
            "grid_snap_distance_km",
            "predicted_start_sic_pct",
            "observed_target_sic_pct",
            "blocked_by_sic",
            "nearest_feasible_distance_km",
            "grid_artifact_suspected",
            "classification",
        ]

        failed_columns = [
            column
            for column in failed_columns
            if column in failed.columns
        ]

        failed_display = failed[
            failed_columns
        ].copy()

        failed_display = failed_display.rename(
            columns={
                "case_id":
                    "Case",

                "horizon_hours":
                    "Horizon (h)",

                "grid_snap_distance_km":
                    "Grid Snap (km)",

                "predicted_start_sic_pct":
                    "Predicted Start SIC (%)",

                "observed_target_sic_pct":
                    "Observed Target SIC (%)",

                "blocked_by_sic":
                    "Blocked by SIC",

                "nearest_feasible_distance_km":
                    "Nearest Feasible Cell (km)",

                "grid_artifact_suspected":
                    "Grid Sensitivity",

                "classification":
                    "Diagnosis",
            }
        )

        numeric_cols = (
            failed_display.select_dtypes(
                include=[
                    "float",
                    "float64",
                    "float32",
                ]
            ).columns
        )

        failed_display[
            numeric_cols
        ] = (
            failed_display[
                numeric_cols
            ]
            .round(2)
        )

        st.dataframe(
            failed_display,
            use_container_width=True,
            hide_index=True,
        )

    show_image_if_exists(
        "06_validation_outcomes.png",
        "Feasible vs safety-rejected frozen PS146 validation cases.",
    )

    st.info(
        "Diagnostic review found that four of the five rejected cases "
        "were consistent with severe high-ice conditions. One 24h case "
        "showed sensitivity to routing-grid snapping."
    )

    # ========================================================
    # LIMITATIONS
    # ========================================================

    st.subheader(
        "⚠️ Interpretation & Limitations"
    )

    st.markdown(
        """
- **7.99% is a modeled route-distance comparison**, not a claim that
  Polarstern would have completed the voyage 7.99% faster.
- Real research-vessel tracks may contain scientific stations,
  operational instructions, weather decisions and other objectives
  that PolarGuard does not model.
- The routing grid is coarse, which creates angular routes and
  endpoint snapping.
- Sea-ice forecasts underpredict some high-ice cases.
- One rejected case was sensitive to grid resolution.
- PolarGuard remains a **prototype decision-support system**, not a
  certified navigation product.
"""
    )

    st.success(
        "Validation conclusion: the historical backtest provides evidence "
        "that PolarGuard can identify alternative corridors with lower "
        "observed sea-ice exposure while often reducing modeled route "
        "distance, but additional operational validation is required."
    )