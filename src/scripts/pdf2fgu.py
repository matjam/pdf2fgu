import click
from fgu.pdfconverter import analyze


@click.command()
@click.argument("file")
def cli(file):
    print(f"analyzing {file}")
    analyze(file)
