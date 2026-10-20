import multiprocessing
import sys


def main():
    multiprocessing.freeze_support()
    if len(sys.argv) > 1 and sys.argv[1] in ("search", "index", "--db"):
        from .cli import main as cli_main
        return cli_main()
    from .gui.main_window import run
    from .paths import default_db_path
    return run(default_db_path())


if __name__ == "__main__":
    sys.exit(main())
