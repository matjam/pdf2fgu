import json
import fitz
from operator import itemgetter
from itertools import groupby

doc = fitz.open("DDAL04-09_The_Tempter.pdf")
pages = []
for page in doc.pages():
    textpage = page.get_textpage()
    d = textpage.extractDICT()
    pages.append(d)

print(f"loaded {len(pages)} pages into memory")