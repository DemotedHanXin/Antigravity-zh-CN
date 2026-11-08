"""Run Antigravity 中文助手 from a source checkout or frozen Windows build."""


def main(argv=None):
    from app.main import main as run
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
