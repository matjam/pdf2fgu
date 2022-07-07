import click
import os
from fgu.pdfconverter import analyze
import pprint as pprinter
from fgu.formattedtext import *

pp = pprinter.PrettyPrinter(indent=4)
pprint = pp.pprint


@click.command()
@click.argument("pdf_path")
@click.argument("fgu_path")
def cli(pdf_path, fgu_path):
    files = os.listdir(pdf_path)
    for file in files:
        if not file.endswith(".pdf"):
            continue

        campaign_name = file.removesuffix(".pdf").replace("_", " ")

        page_data = analyze(pdf_path, file)
        page_data.parse()
        page_data.convert(
            f"{fgu_path}/campaigns/pdf2fgu - {campaign_name}",
            campaign_name,
        )
