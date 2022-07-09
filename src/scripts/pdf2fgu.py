"""
All of the pdf2fgu CLI entrypoints.
"""

import os
import pprint as pprinter

import click

from fgu.pdfconverter import analyze

pp = pprinter.PrettyPrinter(indent=4)
pprint = pp.pprint


@click.command()
@click.argument("pdf_path")
@click.argument("fgu_path")
def cli(pdf_path, fgu_path):
    """
    Performs an import for all .pdf files in PDF_PATH and updates/creates
    campaigns in FGU_PATH.
    """
    files = os.listdir(pdf_path)
    files.sort()
    for file in files:
        if not file.endswith(".pdf"):
            continue

        campaign_name = file.removesuffix(".pdf").replace("_", " ")

        print(f"converting file [{file}] campaign [{campaign_name}] ...")

        page_data = analyze(pdf_path, file)
        page_data.parse()
        page_data.convert(
            f"{fgu_path}/campaigns/pdf2fgu - {campaign_name}",
            campaign_name,
        )
