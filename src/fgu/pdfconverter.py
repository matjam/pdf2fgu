import fitz
import pprint as pprinter


pp = pprinter.PrettyPrinter(indent=4)
pprint = pp.pprint


class Analysis:
    pass


def analyze(file: str):
    doc = fitz.open(file)
    pages = []
    for page in doc.pages():
        textpage = page.get_textpage()
        d = textpage.extractDICT()
        pages.append(d)

    print(f"loaded {len(pages)} pages")

    # loop over all the pages and make a catalogue of all the styles we find. We will use that
    # to determine what is a "heading" etc.
    # page 0 is the title page; we won't use that for our evaluations

    styles = {}

    for page_index, page in enumerate(pages[1:]):
        for block_index, block in enumerate(page["blocks"]):
            for line_index, line in enumerate(block["lines"]):
                for span_index, span in enumerate(line["spans"]):
                    style = f"{span['font']} {span['size']}"
                    if style in styles:
                        styles[style] = styles[style] + len(span)
                    else:
                        styles[style] = len(span)

                    if style == "Segoe UI Semibold,Bold 18.0":
                        print(f"{span['text']} - block {block_index}")

    pprint(styles)
