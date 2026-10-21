import multiprocessing
import sys


def main():
    multiprocessing.freeze_support()
    args = sys.argv[1:]
    if args and args[0] == "--version":
        from . import __version__
        print(__version__)
        return 0
    if args and args[0] == "--selftest":
        from .selftest import run as selftest
        return selftest(args[1:])
    if args and args[0] in ("search", "index", "--db"):
        from .cli import main as cli_main
        return cli_main()
    from .gui.main_window import run
    from .paths import default_db_path
    return run(default_db_path())


if __name__ == "__main__":
    sys.exit(main())
