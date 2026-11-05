"""Launch the desktop manager from a source checkout.

Use ``python main.py --cli ...`` for the JSON command-line interface.
Importing this module does not start Qt or read user configuration.
"""
from pathlib import Path
import sys


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    source = str(Path(__file__).resolve().parent / 'src')
    if source not in sys.path:
        sys.path.insert(0, source)
    if args and args[0] == '--cli':
        from antigravity_manager.cli import main as run
        return run(args[1:])
    from antigravity_manager.__main__ import main as run
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
