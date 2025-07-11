import sys

from pydantic import BaseModel
from pydantic.fields import Field
from pydantic_settings import BaseSettings, CliSubCommand

from .index import create_index
from .run_test import run_tests


class CmdBase(BaseModel, use_attribute_docstrings=True, cli_implicit_flags=True):
    pass


class IndexCmd(CmdBase):
    def run(self):
        """Index the bioimage.io collection"""
        _ = create_index()


class TestCmd(CmdBase):
    def run(self):
        """Test the bioimage.io collection with bioimageio.core"""
        _ = run_tests()


class SummarizeCmd(CmdBase):
    def run(self):
        """Conflate tool summaries"""


class Backoffice(
    BaseSettings,
    cli_implicit_flags=True,
    cli_parse_args=True,
    cli_kebab_case=True,
    cli_prog_name="backoffice",
    cli_use_class_docs_for_groups=True,
    use_attribute_docstrings=True,
):
    """backoffice - manage the bioimage.io collection"""

    index: CliSubCommand[IndexCmd]
    """index the bioimage.io collection"""

    test: CliSubCommand[TestCmd]
    """Test the bioimage.io collection with bioimageio.core"""

    summarize: CliSubCommand[SummarizeCmd]
    """conflate tool summaries"""

    def run(self):
        cmd = self.index or self.test or self.summarize
        if cmd is None:
            raise ValueError(
                "No command specified. Use 'backoffice --help' to see available commands."
            )
        else:
            sys.exit(cmd.run())
