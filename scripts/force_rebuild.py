#!/usr/bin/env python3
"""Force full rebuild: wipes state DB and re-indexes everything from scratch."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from src.pipeline import KnowledgePipeline


def main():
    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "config" / "settings.yaml"
    config = yaml.safe_load(config_path.read_text())
    if config["workspace"]["root"] == "auto":
        config["workspace"]["root"] = str(project_root)
    root = Path(config["workspace"]["root"])

    # Wipe state DB to force full rescan
    state_db_path = root / config["workspace"]["state_db"]
    if state_db_path.exists():
        state_db_path.unlink()
        print(f"Removed state DB: {state_db_path}")

    # Run full pipeline
    pipeline = KnowledgePipeline(config)
    print("\n=== Knowledge OS Full Rebuild ===\n")
    result = pipeline.full_rebuild(verbose=True)

    print(f"\n=== Rebuild Complete ===")
    print(f"  Files scanned:    {result['files_scanned']}")
    print(f"  Objects compiled: {result['objects_compiled']}")
    print(f"  Objects indexed:  {result['objects_indexed']}")
    print(f"  Index failures:   {result['index_failures']}")
    print(f"  Time elapsed:     {result['elapsed_seconds']}s")


if __name__ == "__main__":
    main()
