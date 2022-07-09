"""
Core logic for the conversion of AL PDFs into FGU campaigns.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import List

import fitz
from dataclass_wizard import JSONWizard

from fgu.formattedtext import (
    FormattedHeading,
    FormattedParagraph,
    FormattedTableRow,
    FormattedText,
    StyledText,
    StyledTextSegment,
)

from .campaign import Campaign
from .encounter import Encounter, Story


class Style(Enum):
    """
    Enum type for all supported styles that we use for parsing the PDFs.
    """

    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    TABLE_TITLE = "table_title"
    TABLE_HEADING = "table_heading"
    TABLE_TEXT = "table_text"
    TABLE_TEXT_ITALIC = "table_text_italic"
    BODY = "body"
    BODY_BOLD = "body_bold"
    BODY_ITALIC = "body_italic"
    BODY_BOLD_ITALIC = "body_bold_italic"
    BOX_HEADING = "box_heading"
    BOX_TEXT_BOLD = "box_text_bold"
    BOX_TEXT_ITALIC = "box_text_italic"
    BOX_TEXT_BOLD_ITALIC = "box_text_bold_italic"
    BOX_TEXT = "box_text"
    BULLET = "bullet"
    FRAME_BODY = "frame_body"


@dataclass
class OriginData:
    """
    Actual x & y co-ordinates on the page for a span.

    Useful when trying to figure out the relationship of spans.
    """

    x: int
    y: int


@dataclass
class StyleData:
    """
    Provides information about the style as extracted from the PDF.
    """

    font: str
    size: float
    flags: int
    color: str


@dataclass
class LocationData:
    """
    Provides the original location in the page, block, line and span of a
    specific span.
    """

    page: int
    block: int
    line: int
    span: int


@dataclass
class Data(JSONWizard):
    """
    Each parsed span of data from the PDF, with all of the information we used
    to make parsing decisions extracted from the PDF data.
    """

    style: Style
    style_data: StyleData
    origin: OriginData
    text: str
    location: LocationData


class PageData:
    """
    Contains all of the data for a PDF and the methods we use to do the actual
    conversion into FGU xml.
    """

    def __init__(self, file: str, pages: dict):
        self.pages = pages
        self.module_name = file.replace("_", " ").removesuffix(".pdf")

        # parsing state
        self.data = []  # type:List[Data]
        self.output = None  # output file when parsing
        self.stop_parsing = False
        self.current_page_span = 0
        self.page_bullshit_start = True  # hee hee

        self.page_num = 0
        self.block_num = 0
        self.line_num = 0
        self.span_num = 0

        # conversion state
        self.sections = [0, 0, 0]
        self.encounters = None
        self.previous_data = None  # type:Data
        self.current_heading_3 = None
        self.current_styledtext = None
        self.current_box = None
        self.paragraph = None
        self.current_story = None

        # build our dictionaries for searching styles
        self.config = _load_config()
        self.module_config = _config_for_module(file.split("_")[0], self.config)

        # parse out all the styles and store them for the parsing stage
        self.styles = {}
        for style_name in self.module_config:
            self.styles[style_name] = self.find_style_for_text(
                self.module_config[style_name]
            )
            if not self.styles[style_name]:
                print(
                    f"warning: could not find '{style_name}' using"
                    f" '{self.module_config[style_name]}' in {file}. This is"
                    " probably ok."
                )

        # make a dict we can use to look up the style_name from the style.
        self.style_names_from_style = {}
        for style_name, style_data in self.styles.items():
            self.style_names_from_style[style_data] = style_name

    def add_parsed_span(
        self,
        text: str,
        style: str,
        style_data: StyleData,
        origin: OriginData,
        page: int,
    ):
        """
        Function used to build the array that holds all the parsed page data.
        """
        data = Data(
            style,
            style_data,
            origin,
            text,
            page,
        )

        self.data.append(data)
        # could use JSON but this results in a tighter output
        print(
            f"{self.page_num} {style}"
            + f" style=[{style_data.font} {style_data.size} {style_data.color} {style_data.flags}]"
            + f" origin=[{origin.x},{origin.y}] '{text}'",
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
                        style = (
                            f"{span['font']} {span['size']} {span['flags']} {span['color']}"
                        )
                        if text in span["text"].strip().lstrip():
                            return style
        return None

    def parse(self):
        """
        runs the parsing logic which will construct the internal structures for
        all Stories.
        """
        with open(f"txt/{self.module_name}.txt", "w", encoding="utf-8") as self.output:
            # theoretically we now have all the style information we need. Now we
            # just iterate over the text and extract all the structure we need.
            for self.page_num, page in enumerate(self.pages):
                for self.block_num, block in enumerate(page["blocks"]):
                    for self.line_num, line in enumerate(block["lines"]):
                        for self.span_num, span in enumerate(line["spans"]):
                            self._parse_span(span)
                            if self.stop_parsing:
                                return

    def _parse_span(self, span):
        """
        performs the parsing on a given span.
        """
        style = f"{span['font']} {span['size']} {span['flags']} {span['color']}"
        style_data = StyleData(span["font"], span["size"], span["flags"], span["color"])
        text = span["text"]
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

        self.add_parsed_span(
            text,
            style_name,
            style_data,
            OriginData(int(span["origin"][0]), int(span["origin"][1])),
            LocationData(self.page_num, self.block_num, self.line_num, self.span_num),
        )
        self.current_page_span = self.current_page_span + 1

    def _section_text(self):
        """
        generates a string that is used as the prefix for new Story.
        """
        if self.sections[1] == 0 and self.sections[2] == 0:
            return f"{self.sections[0]:02}"
        if self.sections[2] == 0:
            return f"{self.sections[0]:02}.{self.sections[1]:02}"
        return f"{self.sections[0]:02}.{self.sections[1]:02}.{self.sections[2]:02}"

    def _increment_section(self, section: int):
        if section == 0:
            self.sections[0] = self.sections[0] + 1
            self.sections[1] = 0
            self.sections[2] = 0
        elif section == 1:
            self.sections[1] = self.sections[1] + 1
            self.sections[2] = 0
        else:
            self.sections[2] = self.sections[2] + 1

    def _new_story(self, name, level) -> Story:
        self._increment_section(level)
        return Story(f"{self._section_text()} {name}", text=FormattedText())

    def convert(self, campaign_path: str, campaign_name):
        """
        performs all conversion on the parsed data and outputs the campaign.
        """
        self.encounters = Encounter(campaign_name)

        self.previous_data = None
        self.current_heading_3 = None  # type:FormattedHeading
        self.current_styledtext = None  # type:StyledText
        self.current_box = None  # type:FormattedTableRow
        self.paragraph = None

        self.current_story = Story(f"00 ({campaign_name})", text=FormattedText())
        self.encounters.append_story(self.current_story)

        handlers = {
            "heading_1": self._convert_heading_1,
            "heading_2": self._convert_heading_2,
            "heading_3": self._convert_heading_3,
            "body": self._convert_body,
            "body_bold": self._convert_body,
            "body_italic": self._convert_body,
            "body_bold_italic": self._convert_body,
            "box_heading": self._convert_box_heading,
        }

        for data in self.data:
            if data.style in handlers:
                handlers[data.style](data)

            # just in case we need it to make decisions for the next loop
            self.previous_data = data

        campaign = Campaign(campaign_path, self.encounters)
        campaign.build()

    def _convert_heading_1(self, data: Data):
        if (
            self.previous_data is not None
            and self.previous_data.style == "heading_1"
            and data.location.page == self.previous_data.location.page
        ):
            # oops this was a heading that wrapped, append it to the current story title.
            # this is why we do all this shit in memory rather than trying to construct
            # the XML in one pass. SMRT SMART
            self.current_story.name = self.current_story.name + data.text
            return

        self.paragraph = None
        self.current_story = self._new_story(data.text, 0)
        self.encounters.append_story(self.current_story)

    def _convert_heading_2(self, data: Data):
        if (
            self.previous_data is not None
            and self.previous_data.style == "heading_2"
            and data.location.page == self.previous_data.location.page
        ):
            # oops this was a heading_2 that wrapped, append it to the current heading_2
            self.current_story.name = self.current_story.name + data.text
            return

        self.paragraph = None
        self.current_story = self._new_story(data.text, 1)
        self.encounters.append_story(self.current_story)

    def _convert_heading_3(self, data: Data):
        if (
            self.previous_data is not None
            and self.previous_data.style == "heading_3"
            and data.location.page == self.previous_data.location.page
        ):
            # oops this was a heading_3 that wrapped, append it to the current heading_3
            self.current_heading_3.text = self.current_heading_3.text + data.text
            return

        self.paragraph = None
        self.current_heading_3 = FormattedHeading(data.text)
        self.current_story.text.append(self.current_heading_3)

    def _convert_body(self, data: Data):
        bold = False
        italic = False
        if "bold" in data.style:
            bold = True
        if "italic" in data.style:
            italic = True

        segment = StyledTextSegment(data.text, bold=bold, italic=italic)
        if (
            self.previous_data is not None
            and "body" in self.previous_data.style
            and self.current_styledtext is not None
        ):
            # we probably add this to the current styledtext block, but we need to check if it
            # might be a new paragraph
            if self.current_styledtext.last_segment().strip().endswith(
                "."
            ) and data.text.startswith(" "):
                # probably a good bet it's a new paragraph. Not sure what else to go on.
                self.current_styledtext = StyledText([segment])
                self.paragraph = FormattedParagraph(self.current_styledtext)
                self.current_story.text.append(self.paragraph)
                return

            self.current_styledtext.append(segment)
            return

        self.current_styledtext = StyledText([segment])
        if self.paragraph is None:
            self.paragraph = FormattedParagraph(self.current_styledtext)
            self.current_story.text.append(self.paragraph)
        else:
            self.paragraph.text.append(self.current_styledtext)

    def _convert_box_heading(self, data: Data):
        pass
        # if self.current_box is not None:
        #     # Already in a box? ok
        #     box_heading = StyledTextSegment(f"{data.text}\n\n", bold=True)
        #     self.current_box.rows[0].columns[0].append(box_heading)
        # else:
        #     box_heading = StyledTextSegment(f"{data.text}\n\n", bold=True)
        #     row = FormattedTableRow([box_heading])
        #     self.current_box = FormattedTable([row])
        #     self.current_story.text.append(self.current_box)


def _load_config():
    with open("config.json", "r", encoding="utf-8") as in_file:
        data = in_file.read()
    return json.loads(data)


def _config_for_module(code, config):
    module_config = config["patterns"]["base"]
    if code in config["patterns"]["overrides"]:
        for style in config["patterns"]["overrides"][code]:
            module_config[style] = config["patterns"]["overrides"][code][style]
    return module_config


def analyze(path: str, file: str) -> PageData:
    """
    performs initial style analysis, and will flag any issues before you
    attempt to run the conversion.
    """
    file_path = f"{path}/{file}"
    doc = fitz.open(file_path)
    pages = []
    for page in doc.pages():
        text_page = page.get_textpage()
        text_dict = text_page.extractDICT()
        pages.append(text_dict)

    return PageData(file, pages)
