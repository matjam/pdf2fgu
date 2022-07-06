import enum
import fitz
import json
import pprint as pprinter


pp = pprinter.PrettyPrinter(indent=4)
pprint = pp.pprint


class PageData:
    def __init__(self, file: str, pages: dict):
        self.pages = pages
        self.module_name = file.replace("_", " ").removesuffix(".pdf")
        self.parsed = []

        # build our dictionaries for searching styles
        self.config = load_config()
        self.module_config = config_for_module(file.split("_")[0], self.config)

        self.styles = {}
        for style_name in self.module_config:
            self.styles[style_name] = self.find_style_for_text(
                self.module_config[style_name]
            )
            if not self.styles[style_name]:
                print(
                    f"warning: could not find '{style_name}' using '{self.module_config[style_name]}' in {file}. This is probably ok."
                )

        # make a dict we can use to look up the style_name from the style.
        self.style_names_from_style = {}
        for style in self.styles:
            self.style_names_from_style[self.styles[style]] = style

    def find_style_for_text(self, text):
        """
        Inefficient search for a given string in the text to return it's style.
        """
        for page in self.pages[1:]:
            for block in page["blocks"]:
                for line in block["lines"]:
                    for span in line["spans"]:
                        style = f"{span['font']} {span['size']} {span['flags']} {span['color']}"
                        if text in span["text"].strip().lstrip():
                            return style
        return None

    def parse(self):
        with open(f"{self.module_name}.txt", "w", encoding="utf-8") as f:
            # theoretically we now have all the style information we need. Now we just iterate over the text
            # and extract all the structure we need.
            for page_num, page in enumerate(self.pages):
                current_page_span = 0
                page_bullshit_start = True
                for block_num, block in enumerate(page["blocks"]):
                    for line_num, line in enumerate(block["lines"]):
                        for span_num, span in enumerate(line["spans"]):
                            style = f"{span['font']} {span['size']} {span['flags']} {span['color']}"
                            text = span["text"]
                            origin_x = span["origin"][0]
                            origin_y = span["origin"][1]
                            for stop_processing_text in self.config["stop_processing"]:
                                if text.lstrip().strip() == stop_processing_text:
                                    # fin
                                    return

                            skip_span = False
                            really_skip = False
                            if page != 1 and current_page_span == 0:
                                skip_span = True

                            # we could be in the bullshit part of the page at the start which we need to skip.
                            # this strategy is basically just keep skipping til we find a span that is both
                            # a recognized style AND it has some meaningful content. ' ' and '.' does not count.
                            if page_bullshit_start and page_num != 0:
                                if len(text.lstrip().strip()) == 0:
                                    # bullshit, skip
                                    skip_span = True
                                elif not style in self.style_names_from_style:
                                    # OOOOH BULLSHIT FUCKING SKIP
                                    skip_span = True

                            # make sure we skip things we never want int the module.
                            for never_string in self.config["never_allow_strings"]:
                                if never_string in span["text"]:
                                    # we don't want to run the bullshit tests after this
                                    skip_span = True
                                    really_skip = True

                            if really_skip or (
                                skip_span and page_num != 0
                            ):  # we don't handle skipping on the title page unless we really mean it
                                current_page_span = current_page_span + 1
                                continue

                            if page_num == 0:
                                # we run different logic for the title page; the fonts used on this page are usually
                                # completely different to the rest of the document. We don't try to figure out the
                                # styles here; we just make everything "body" and then look at the font names
                                # to determine if they are Italic or bold or bold/italic.

                                style_name = "body"

                                style = style.lower()
                                if "italic" in style:
                                    style_name = "body_italic"
                                elif "bold" in style:
                                    style_name = "body_bold"

                                print(
                                    f"{style_name} ({int(origin_x)},{int(origin_y)}): '{text}'",
                                    file=f,
                                )
                                self.parsed.append(
                                    {
                                        "style": style_name,
                                        "origin": {
                                            "x": int(origin_x),
                                            "y": int(origin_y),
                                        },
                                        "text": text,
                                    }
                                )
                            elif (
                                len(text) == 1
                                and text in self.config["patterns"]["char_override"]
                            ):
                                # some characters are just hardcoded always to be a thing.
                                style_name = self.config["patterns"]["char_override"][
                                    text
                                ]
                                print(f"{style_name}: '{text}'", file=f)
                                self.parsed.append(
                                    {
                                        "style": style_name,
                                        "origin": {
                                            "x": int(origin_x),
                                            "y": int(origin_y),
                                        },
                                        "text": text,
                                    }
                                )
                            elif not style in self.style_names_from_style:
                                # anything we don't have a style for, we could assume is body but that would
                                # pull in random shit that we don't want.
                                if len(text) == 1:
                                    ucode = format(ord(text), "04x")
                                    print(
                                        f"UNKNOWN ({style}): '{text}' unicode: {ucode}",
                                        file=f,
                                    )
                                else:
                                    print(f"UNKNOWN ({style}): '{text}'", file=f)

                                    self.parsed.append(
                                        {
                                            "style": "unknown",
                                            "origin": {
                                                "x": int(origin_x),
                                                "y": int(origin_y),
                                            },
                                            "text": text,
                                        }
                                    )
                            else:
                                style_name = self.style_names_from_style[style]
                                print(
                                    f"{style_name} ({int(origin_x)},{int(origin_y)}): '{text}'",
                                    file=f,
                                )
                                self.parsed.append(
                                    {
                                        "style": style_name,
                                        "origin": {
                                            "x": int(origin_x),
                                            "y": int(origin_y),
                                        },
                                        "text": text,
                                    }
                                )

                            current_page_span = current_page_span + 1

    def convert(self):
        pass


def load_config():
    with open("config.json", "r") as f:
        data = f.read()
    return json.loads(data)


def config_for_module(code, config):
    module_config = config["patterns"]["base"]
    if code in config["patterns"]["overrides"]:
        for style in config["patterns"]["overrides"][code]:
            module_config[style] = config["patterns"]["overrides"][code][style]
    return module_config


def analyze(path: str, file: str) -> PageData:
    file_path = f"{path}/{file}"
    doc = fitz.open(file_path)
    pages = []
    for page in doc.pages():
        textpage = page.get_textpage()
        d = textpage.extractDICT()
        pages.append(d)

    return PageData(file, pages)
