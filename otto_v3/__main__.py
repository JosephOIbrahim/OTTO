"""Entry point: python -m otto"""


def main() -> None:
    from otto import __version__

    print(f"OTTO OS v{__version__}")


if __name__ == "__main__":
    main()
