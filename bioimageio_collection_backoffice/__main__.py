import fire

from ._backoffice import BackOffice


def main():
    fire.Fire(BackOffice)


if __name__ == "__main__":
    main()
