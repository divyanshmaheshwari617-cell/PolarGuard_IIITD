from pathlib import Path
import xarray as xr

DATA_DIR = Path("data/aggregate")

files = sorted(DATA_DIR.glob("*.nc"))

if not files:
    raise FileNotFoundError("No aggregate .nc files found.")

print("=" * 70)
print("POLARGUARD — AGGREGATE DATA VALIDATION")
print("=" * 70)

print(f"\nFiles found: {len(files)}")

total_days = 0
failed_files = []

for file_path in files:

    print("\n" + "-" * 70)
    print("File:", file_path.name)

    try:
        ds = xr.open_dataset(file_path)

        print("Dimensions:", dict(ds.sizes))
        print("Variables:", list(ds.data_vars))

        if "time" not in ds.dims:
            print("ERROR: No time dimension!")
            failed_files.append(file_path.name)
            ds.close()
            continue

        days = ds.sizes["time"]

        start_date = ds.time.values[0]
        end_date = ds.time.values[-1]

        print("Daily timesteps:", days)
        print("Start:", start_date)
        print("End  :", end_date)

        if "cdr_seaice_conc" in ds.data_vars:
            print("cdr_seaice_conc: FOUND ✅")
        else:
            print("cdr_seaice_conc: MISSING ❌")
            failed_files.append(file_path.name)

        total_days += days

        ds.close()

    except Exception as e:

        print("FAILED TO OPEN ❌")
        print("Reason:", e)

        failed_files.append(file_path.name)


print("\n" + "=" * 70)
print("VALIDATION SUMMARY")
print("=" * 70)

print("Yearly files :", len(files))
print("Total daily timesteps:", total_days)
print("Failed files :", len(failed_files))

if failed_files:
    print("\nProblem files:")
    for filename in failed_files:
        print(filename)
else:
    print("\nAll aggregate files validated successfully ✅")