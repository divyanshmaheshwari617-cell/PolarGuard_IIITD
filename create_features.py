from pathlib import Path
import numpy as np
import xarray as xr

DATA_FILE = Path("data/processed/train_2019_2023.nc")
OUTPUT_FILE = Path("data/processed/training_features.npz")

# Number of grid-cell samples retained per day.
# Keeps training practical on a normal laptop.
SAMPLES_PER_DAY = 3000

RANDOM_SEED = 42
rng = np.random.default_rng(RANDOM_SEED)

print("=" * 70)
print("POLARGUARD — SEA-ICE FEATURE GENERATION")
print("=" * 70)

sic = xr.open_dataarray(DATA_FILE)

print("\nDataset shape:", sic.shape)

values = sic.values

times = sic.time.values

y_coords = sic.y.values
x_coords = sic.x.values

X_parts = []
y24_parts = []
y48_parts = []
y72_parts = []

# We need t-3 history and t+3 future.
for t in range(3, len(times) - 3):

    current = values[t]
    lag1 = values[t - 1]
    lag2 = values[t - 2]
    lag3 = values[t - 3]

    target24 = values[t + 1]
    target48 = values[t + 2]
    target72 = values[t + 3]

    # Valid only when all features and all targets exist.
    valid = (
        np.isfinite(current)
        & np.isfinite(lag1)
        & np.isfinite(lag2)
        & np.isfinite(lag3)
        & np.isfinite(target24)
        & np.isfinite(target48)
        & np.isfinite(target72)
    )

    rows, cols = np.where(valid)

    if len(rows) == 0:
        continue

    sample_count = min(
        SAMPLES_PER_DAY,
        len(rows)
    )

    selected = rng.choice(
        len(rows),
        size=sample_count,
        replace=False
    )

    rows = rows[selected]
    cols = cols[selected]

    # -------------------------------------------------------
    # SEASONAL FEATURES
    # -------------------------------------------------------

    date = np.datetime64(times[t], "D")

    year_start = date.astype("datetime64[Y]")

    day_of_year = int(
        (date - year_start)
        / np.timedelta64(1, "D")
    ) + 1

    seasonal_sin = np.sin(
        2 * np.pi * day_of_year / 365.25
    )

    seasonal_cos = np.cos(
        2 * np.pi * day_of_year / 365.25
    )

    # Normalize coordinates approximately to manageable scale.
    x_selected = x_coords[cols]
    y_selected = y_coords[rows]

    x_scale = np.max(np.abs(x_coords))
    y_scale = np.max(np.abs(y_coords))

    x_normalized = x_selected / x_scale
    y_normalized = y_selected / y_scale

    n = len(rows)

    features = np.column_stack([
        current[rows, cols],
        lag1[rows, cols],
        lag2[rows, cols],
        lag3[rows, cols],

        x_normalized,
        y_normalized,

        np.full(n, seasonal_sin),
        np.full(n, seasonal_cos),
    ])

    X_parts.append(
        features.astype(np.float32)
    )

    y24_parts.append(
        target24[rows, cols].astype(np.float32)
    )

    y48_parts.append(
        target48[rows, cols].astype(np.float32)
    )

    y72_parts.append(
        target72[rows, cols].astype(np.float32)
    )

    if t % 100 == 0:
        print(
            f"Processed day {t}/{len(times)}"
        )


print("\nCombining samples...")

X = np.concatenate(X_parts)

y24 = np.concatenate(y24_parts)
y48 = np.concatenate(y48_parts)
y72 = np.concatenate(y72_parts)

print("\n" + "=" * 70)
print("FEATURE DATASET")
print("=" * 70)

print("X shape   :", X.shape)
print("24h target:", y24.shape)
print("48h target:", y48.shape)
print("72h target:", y72.shape)

print("\nFeature order:")
print(
    "SIC(t), SIC(t-1), SIC(t-2), SIC(t-3), "
    "x, y, seasonal_sin, seasonal_cos"
)

print("\nSaving...")

np.savez_compressed(
    OUTPUT_FILE,
    X=X,
    y24=y24,
    y48=y48,
    y72=y72
)

print("\nSaved:", OUTPUT_FILE)

print("\n" + "=" * 70)
print("FEATURE GENERATION COMPLETE")
print("=" * 70)

sic.close()