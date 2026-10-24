import inspect

modules = [
    "iceberg.iceberg_service",
    "polarguard_pipeline",
    "current_iceberg_service",
    "environmental_data_service",
    "navigation_service",
]

for module_name in modules:
    print("\n" + "=" * 80)
    print(module_name)
    print("=" * 80)

    module = __import__(module_name, fromlist=["*"])

    for name, obj in inspect.getmembers(module):
        if name.startswith("_"):
            continue

        if inspect.isfunction(obj):
            try:
                print(f"{name}{inspect.signature(obj)}")
            except Exception:
                print(name)