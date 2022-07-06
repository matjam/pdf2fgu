import click
import os
from fgu.pdfconverter import analyze
import pprint as pprinter


pp = pprinter.PrettyPrinter(indent=4)
pprint = pp.pprint


@click.command()
@click.argument("path")
def cli(path):
    files = os.listdir(path)
    for file in files:
        page_data = analyze(path, file)
        page_data.parse()
        page_data.convert()
