from ._cli import Backoffice


def main():
    cli = Backoffice()  # pyright: ignore[reportCallIssue]
    cli.run()


if __name__ == "__main__":
    main()
