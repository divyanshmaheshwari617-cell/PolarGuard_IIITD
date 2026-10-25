from pathlib import Path
import xarray as xr
import matplotlib.pyplot as plt

FORECAST_FILE = Path("outputs/sea_ice_forecast_demo.nc")
OUTPUT_DIR = Path("outputs/maps")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("POLARGUARD — FORECAST VISUALIZATION")
print("=" * 70)

ds = xr.open_dataset(FORECAST_FILE)

# ------------------------------------------------------------
# CURRENT SIC
# ------------------------------------------------------------

plt.figure(figsize=(8, 8))

ds["current_sic"].plot(
    vmin=0,
    vmax=1
)

plt.title(
    "PolarGuard — Current Antarctic Sea-Ice Concentration\n"
    "Initialization: 2025-12-28"
)

plt.xlabel("x")
plt.ylabel("y")

plt.tight_layout()

file = OUTPUT_DIR / "current_sic.png"

plt.savefig(
    file,
    dpi=200
)

plt.close()

print("Saved:", file)


# ------------------------------------------------------------
# FORECASTS
# ------------------------------------------------------------

for horizon in ["24h", "48h", "72h"]:

    # ========================================================
    # FORECAST
    # ========================================================

    plt.figure(figsize=(8, 8))

    ds[
        f"forecast_{horizon}"
    ].plot(
        vmin=0,
        vmax=1
    )

    plt.title(
        f"PolarGuard — {horizon} Sea-Ice Forecast"
    )

    plt.xlabel("x")
    plt.ylabel("y")

    plt.tight_layout()

    file = (
        OUTPUT_DIR /
        f"forecast_{horizon}.png"
    )

    plt.savefig(
        file,
        dpi=200
    )

    plt.close()

    print("Saved:", file)


    # ========================================================
    # ACTUAL
    # ========================================================

    plt.figure(figsize=(8, 8))

    ds[
        f"actual_{horizon}"
    ].plot(
        vmin=0,
        vmax=1
    )

    plt.title(
        f"Observed Sea-Ice Concentration — {horizon}"
    )

    plt.xlabel("x")
    plt.ylabel("y")

    plt.tight_layout()

    file = (
        OUTPUT_DIR /
        f"actual_{horizon}.png"
    )

    plt.savefig(
        file,
        dpi=200
    )

    plt.close()

    print("Saved:", file)


    # ========================================================
    # ABSOLUTE ERROR
    # ========================================================

    plt.figure(figsize=(8, 8))

    ds[
        f"absolute_error_{horizon}"
    ].plot(
        vmin=0
    )

    plt.title(
        f"PolarGuard — {horizon} Absolute Forecast Error"
    )

    plt.xlabel("x")
    plt.ylabel("y")

    plt.tight_layout()

    file = (
        OUTPUT_DIR /
        f"error_{horizon}.png"
    )

    plt.savefig(
        file,
        dpi=200
    )

    plt.close()

    print("Saved:", file)


ds.close()

print("\n" + "=" * 70)
print("VISUALIZATION COMPLETE")
print("=" * 70)

print(
    "Maps saved in:",
    OUTPUT_DIR
)
