from __future__ import annotations

import sys

from pydantic import BaseModel
from pydantic_settings import BaseSettings, CliSubCommand

from ._summarize import summarize_reports, summarize_reports_parallel
from .index import create_index


class CmdBase(BaseModel, use_attribute_docstrings=True, cli_implicit_flags=True):
    pass


class IndexCmd(CmdBase):
    def run(self):
        """Index the bioimage.io collection"""
        _ = create_index()


class SummarizeCmd(CmdBase):
    max_workers: int | None = None
    """Maximum number of worker threads to use for parallel processing."""

    def run(self):
        """Conflate tool summaries"""
        if self.max_workers == 0:
            summarize_reports()
        else:
            summarize_reports_parallel(max_workers=self.max_workers)


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

    summarize: CliSubCommand[SummarizeCmd]
    """conflate tool summaries"""

    def run(self):
        cmd = self.index or self.summarize
        if cmd is None:
            raise ValueError(
                "No command specified. Use 'backoffice --help' to see available commands."
            )
        else:
            sys.exit(cmd.run())
