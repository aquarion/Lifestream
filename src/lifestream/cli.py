"""
Command-line interface for Lifestream importers.

Run a specific importer:
    lifestream-import <importer_name> [options]

List available importers:
    lifestream-import --list
"""

import argparse
import sys

from lifestream.importers import IMPORTERS


def main():
    """Main entry point for the lifestream-import command."""
    parser = argparse.ArgumentParser(
        description="Run Lifestream importers",
        prog="lifestream-import",
    )

    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available importers",
    )

    parser.add_argument(
        "importer",
        nargs="?",
        help="Name of the importer to run",
    )

    # Parse known args only, pass rest to importer
    args, remaining = parser.parse_known_args()

    if args.list:
        print("Available importers:")
        for name, cls in sorted(IMPORTERS.items()):
            print(f"  {name:15} - {cls.description}")
        return 0

    if not args.importer:
        parser.print_help()
        print("\nUse --list to see available importers")
        return 1

    importer_name = args.importer.lower()

    if importer_name not in IMPORTERS:
        print(f"Unknown importer: {importer_name}")
        print("Use --list to see available importers")
        return 1

    importer_cls = IMPORTERS[importer_name]
    return importer_cls.main(remaining)


if __name__ == "__main__":
    sys.exit(main())
