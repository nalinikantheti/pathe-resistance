"""Command-line entry points. Importing the package never starts a job."""

import argparse
import json
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="pathe-resistance", description="PathéResistance walking-graph engine"
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run a tiny synthetic example without network access")
    demo.add_argument("--output", type=Path, default=Path("demo"))
    demo.add_argument(
        "--map", action="store_true", help="Also write HTML; viewing tiles needs internet"
    )
    run = commands.add_parser("run", help="Run a JSON config with your graph and GeoAI rasters")
    run.add_argument("config", type=Path)
    run.add_argument("--overwrite", action="store_true", help="Replace known output artifacts")
    segment = commands.add_parser(
        "segment", help="Run optional explicit pretrained-model inference"
    )
    segment.add_argument("source", type=Path, help="Georeferenced uint8 RGB GeoTIFF")
    segment.add_argument("output", type=Path)
    segment.add_argument("--model", required=True, help="Local checkpoint or Hugging Face model ID")
    segment.add_argument(
        "--revision", help="Pinned model commit SHA; required for remote model IDs"
    )
    segment.add_argument("--tree-class", required=True, type=int)
    segment.add_argument("--threshold", type=float, default=0.5)
    segment.add_argument("--tile-size", type=int, default=512)
    segment.add_argument("--overlap", type=int, default=64)
    segment.add_argument("--device", choices=["cpu", "cuda", "mps"], default="cpu")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            from .demo import run_demo

            result = run_demo(args.output, include_map=args.map)
        elif args.command == "run":
            from .pipeline import run

            result = run(args.config, overwrite=args.overwrite)
        else:
            from .segmentation import segment_rgb

            result = segment_rgb(
                args.source,
                args.output,
                model=args.model,
                revision=args.revision,
                tree_class=args.tree_class,
                threshold=args.threshold,
                tile_size=args.tile_size,
                overlap=args.overlap,
                device=args.device,
            )
    except (ValueError, FileExistsError, FileNotFoundError, ImportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
