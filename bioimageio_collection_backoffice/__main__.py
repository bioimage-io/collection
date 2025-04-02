import fire  # pyright: ignore[reportMissingTypeStubs]

from .cli import BackOffice


def main():
    fire.Fire(BackOffice)


if __name__ == "__main__":
    main()
