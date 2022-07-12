"""
All of the pdf2fgu CLI entrypoints.
"""

import os
import pprint as pprinter

import click

from fgu2pdf.logs import logger
from fgu.pdfconverter import PDFConverter


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

        module_name = file.removesuffix(".pdf").replace("_", " ")

        logger.info(f"converting file [{file}] campaign [{module_name}] ...")
        pdf_converter = PDFConverter(pdf_path, file, module_name, fgu_path)
        pdf_converter.convert()
