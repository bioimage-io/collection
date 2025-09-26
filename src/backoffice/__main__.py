try:
    from ._cli import Backoffice
except ImportError as e:
    raise ImportError(
        "Missing dependencies. Please install `backoffice[full]` to use backoffice CLI."
    ) from e


def main():
    cli = Backoffice()  # pyright: ignore[reportCallIssue]
    cli.run()


if __name__ == "__main__":
    main()
