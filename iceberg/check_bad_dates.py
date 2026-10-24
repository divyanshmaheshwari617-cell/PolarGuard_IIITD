from pathlib import Path
import pandas as pd

folder = Path(r"iceberg/data/byu/consolidated_database_v8.0 (1)/updated7_consol")

bad = []

for f in folder.glob("*.csv"):
    try:
        df = pd.read_csv(f)

        for value in df["date"]:
            s = str(value).strip()

            try:
                # Expected format = YYYYDDD
                if len(s) != 7 or not s.isdigit():
                    bad.append((f.name, value, "bad format"))
                    continue

                year = int(s[:4])
                doy = int(s[4:])

                if year < 1970 or year > 2026:
                    bad.append((f.name, value, "bad year"))

                elif doy < 1 or doy > 366:
                    bad.append((f.name, value, "bad day-of-year"))

            except Exception as e:
                bad.append((f.name, value, str(e)))

    except Exception as e:
        print("FAILED:", f.name, e)

print("=" * 60)
print("BAD DATE RECORDS")
print("=" * 60)

print("Total bad dates:", len(bad))

for row in bad[:100]:
    print(row)

print("=" * 60)
