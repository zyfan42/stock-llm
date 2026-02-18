import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    try:
        from app.version import get_version
        from data import get_data_provider
        import app.paths
        import app.updater
        import data
        import llm
        import utils
    except Exception as exc:
        print(f"Import smoke test failed: {exc}")
        return 1

    try:
        version = get_version()
        provider = get_data_provider()
        print(f"Version: {version}")
        print(f"Provider: {type(provider).__name__}")
    except Exception as exc:
        print(f"Runtime smoke test failed: {exc}")
        return 1

    print("Import smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
