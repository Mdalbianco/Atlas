"""Compatibilità con il prototipo: `python main.py` equivale a `python -m atlas run`."""

import sys

from atlas.__main__ import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["run"]))
