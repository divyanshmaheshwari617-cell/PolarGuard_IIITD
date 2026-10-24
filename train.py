from pathlib import Path
import time
import joblib
import numpy as np

from sklearn.ensemble import HistGradientBoostingRegressor


# ============================================================
# PATHS
# ============================================================

FEATURE_FILE = Path(
    "data/processed/training_features.npz"
)

MODEL_DIR = Path("models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# SETTINGS
# ============================================================

MAX_TRAIN_SAMPLES = 1_500_000
RANDOM_SEED = 42


print("=" * 70)
print("POLARGUARD — SEA-ICE MODEL TRAINING")
print("=" * 70)


# ============================================================
# LOAD FEATURES
# ============================================================

print("\nLoading training features...")

data = np.load(FEATURE_FILE)

X = data["X"]
y24 = data["y24"]
y48 = data["y48"]
y72 = data["y72"]

print("\nFull dataset:")
print("X   :", X.shape)
print("y24 :", y24.shape)
print("y48 :", y48.shape)
print("y72 :", y72.shape)


# ============================================================
# SUBSAMPLE
# ============================================================

rng = np.random.default_rng(RANDOM_SEED)

total_samples = len(X)

sample_count = min(
    MAX_TRAIN_SAMPLES,
    total_samples
)

indices = rng.choice(
    total_samples,
    size=sample_count,
    replace=False
)

X_train = X[indices]

targets = {
    "24h": y24[indices],
    "48h": y48[indices],
    "72h": y72[indices]
}

print(
    f"\nTraining samples selected: "
    f"{sample_count:,}"
)

print(
    "Feature count:",
    X_train.shape[1]
)


# ============================================================
# MODEL CONFIGURATION
# ============================================================

def create_model():

    return HistGradientBoostingRegressor(

        learning_rate=0.08,

        max_iter=150,

        max_leaf_nodes=31,

        min_samples_leaf=50,

        l2_regularization=0.1,

        random_state=RANDOM_SEED,

        verbose=1
    )


# ============================================================
# TRAIN 3 FORECAST MODELS
# ============================================================

for horizon, target in targets.items():

    print("\n" + "=" * 70)
    print(f"TRAINING {horizon} FORECAST MODEL")
    print("=" * 70)

    model = create_model()

    start_time = time.time()

    model.fit(
        X_train,
        target
    )

    elapsed = time.time() - start_time

    model_file = (
        MODEL_DIR /
        f"sea_ice_model_{horizon}.joblib"
    )

    joblib.dump(
        model,
        model_file
    )

    print(
        f"\n{horizon} model trained successfully."
    )

    print(
        f"Training time: "
        f"{elapsed / 60:.2f} minutes"
    )

    print(
        "Saved:",
        model_file
    )


print("\n" + "=" * 70)
print("ALL MODELS TRAINED")
print("=" * 70)

print("\nModels created:")

print(
    MODEL_DIR /
    "sea_ice_model_24h.joblib"
)

print(
    MODEL_DIR /
    "sea_ice_model_48h.joblib"
)

print(
    MODEL_DIR /
    "sea_ice_model_72h.joblib"
)