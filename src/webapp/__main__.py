#!/usr/bin/env python3
"""
Web Application Entry Point
============================

Allows the webapp to be launched with ``python -m webapp``.

Usage:
    python -m webapp
    python -m webapp --host 0.0.0.0 --port 5000 --debug
"""

import argparse
import sys


def _create_parser() -> argparse.ArgumentParser:
    """Create argument parser for the webapp entry point."""
    parser = argparse.ArgumentParser(
        description="TXR Automation Web Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to listen on (default: 5000)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode",
    )
    return parser


def main() -> None:
    """Application entry point."""
    from webapp.app import create_app

    parser = _create_parser()
    args = parser.parse_args()

    app = create_app("development" if args.debug else None)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
