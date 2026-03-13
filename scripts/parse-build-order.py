#!/usr/bin/env python3
"""
Parse build-order.yml and output tier/package info for shell consumption.

Usage:
    parse-build-order.py build-order.yml                  # list all tiers
    parse-build-order.py build-order.yml --tier <name>    # list packages in tier
    parse-build-order.py build-order.yml --tiers          # list tier names only
"""

import argparse
import sys

import yaml


def main():
    parser = argparse.ArgumentParser(description="Parse build-order.yml")
    parser.add_argument("manifest", help="Path to build-order.yml")
    parser.add_argument("--tier", help="Print packages for a specific tier")
    parser.add_argument(
        "--tiers", action="store_true", help="Print tier names only"
    )
    args = parser.parse_args()

    with open(args.manifest) as f:
        data = yaml.safe_load(f)

    if args.tiers:
        for tier in data["tiers"]:
            print(tier["name"])
        return

    if args.tier:
        for tier in data["tiers"]:
            if tier["name"] == args.tier:
                for pkg in tier.get("packages", []):
                    spec = pkg.get("spec_override", "")
                    print(f"{pkg['path']}\t{spec}")
                return
        print(f"Error: tier '{args.tier}' not found", file=sys.stderr)
        sys.exit(1)

    # Default: print all tiers and their packages
    for tier in data["tiers"]:
        print(f"=== {tier['name']} ===")
        for pkg in tier.get("packages", []):
            spec = pkg.get("spec_override", "")
            line = pkg["path"]
            if spec:
                line += f"\t({spec})"
            print(f"  {line}")


if __name__ == "__main__":
    main()
