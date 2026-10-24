import earthaccess

print("=" * 70)
print("POLARGUARD EARTHDATA SEARCH DIAGNOSTIC")
print("=" * 70)

earthaccess.login()

print("\nTEST 1: Search G10016 without date/version filters")

results = earthaccess.search_data(
    short_name="G10016",
    count=10,
)

print("Results found:", len(results))

for i, result in enumerate(results[:10], start=1):
    print("\n" + "-" * 70)
    print("RESULT", i)
    print("-" * 70)

    try:
        print("Data links:")
        for link in result.data_links():
            print(" ", link)
    except Exception as exc:
        print("Could not read links:", exc)

print("\n" + "=" * 70)
print("DIAGNOSTIC FINISHED")
print("=" * 70)