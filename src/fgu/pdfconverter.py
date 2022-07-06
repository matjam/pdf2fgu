import fitz
import json
import pprint as pprinter


pp = pprinter.PrettyPrinter(indent=4)
pprint = pp.pprint


class Origin:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y}


class StyleData:
    def __init__(self, font: str, size: float, flags: int, color: str):
        self.font = font
        self.size = size
        self.flags = flags
        self.color = color

    def to_dict(self) -> dict:
        return {
            "font": self.font,
            "size": self.size,
            "flags": self.flags,
            "color": self.color,
        }


class PageData:
    def __init__(self, file: str, pages: dict):
        self.pages = pages
        self.module_name = file.replace("_", " ").removesuffix(".pdf")

        # parsing state
        self.parsed = []
        self.output = None  # output file when parsing
        self.stop_parsing = False
        self.current_page_span = 0
        self.page_bullshit_start = True  # hee hee

        # build our dictionaries for searching styles
        self.config = load_config()
        self.module_config = config_for_module(file.split("_")[0], self.config)

        # parse out all the styles and store them for the parsing stage
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

    def add_parsed_span(
        self, text: str, style: str, style_data: StyleData, origin: Origin
    ):

        data = {
            "style": style,
            "style_data": style_data.to_dict(),
            "origin": origin.to_dict(),
            "text": text,
        }

        self.parsed.append(data)
        # could use JSON but this results in a tighter output
        print(
            f"{self.page_num} {style} style=[{style_data.font} {style_data.size} {style_data.color} {style_data.flags}] origin=[{origin.x},{origin.y}] '{text}'",
            file=self.output,
        )

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
        with open(f"txt/{self.module_name}.txt", "w", encoding="utf-8") as self.output:
            # theoretically we now have all the style information we need. Now we just iterate over the text
            # and extract all the structure we need.
            for self.page_num, page in enumerate(self.pages):
                for block in page["blocks"]:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            self.parse_span(span)
                            if self.stop_parsing:
                                return

    def parse_span(self, span):
        style = f"{span['font']} {span['size']} {span['flags']} {span['color']}"
        style_data = StyleData(span["font"], span["size"], span["flags"], span["color"])
        text = span["text"]
        origin = Origin(int(span["origin"][0]), int(span["origin"][1]))
        for stop_processing_text in self.config["stop_processing"]:
            if text.lstrip().strip() == stop_processing_text:
                self.stop_parsing = True
                return

        skip_span = False
        really_skip = False
        # if self.page_num != 1 and self.current_page_span == 0:
        #     skip_span = True

        # we could be in the bullshit part of the page at the start which we need to skip.
        # this strategy is basically just keep skipping til we find a span that is both
        # a recognized style AND it has some meaningful content. ' ' and '.' does not count.
        if self.page_bullshit_start and self.page_num != 0:
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
            skip_span and self.page_num != 0
        ):  # we don't handle skipping on the title page unless we really mean it
            self.current_page_span = self.current_page_span + 1
            return

        if self.page_num == 0:
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
        elif len(text) == 1 and text in self.config["patterns"]["char_override"]:
            # some characters are just hardcoded always to be a thing.
            style_name = self.config["patterns"]["char_override"][text]
        elif not style in self.style_names_from_style:
            # anything we don't have a style for, we could assume is body but that would
            # pull in random shit that we don't want.
            style_name = "unknown"
        else:
            style_name = self.style_names_from_style[style]

        self.add_parsed_span(text, style_name, style_data, origin)
        self.current_page_span = self.current_page_span + 1

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
