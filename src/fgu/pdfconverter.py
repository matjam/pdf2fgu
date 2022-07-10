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
    FormattedList,
    FormattedParagraph,
    FormattedTable,
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


def segment_from_data(data: Data) -> StyledTextSegment:
    bold = False
    italic = False
    if "bold" in data.style:
        bold = True
    if "italic" in data.style:
        italic = True
    segment = StyledTextSegment(data.text, bold=bold, italic=italic)
    return segment


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
        self._current_page_span = 0
        self.page_bullshit_start = True  # hee hee

        self._page_num = 0
        self._block_num = 0
        self._line_num = 0
        self._span_num = 0

        # conversion state
        self.sections = [0, 0, 0]
        self.encounters = None
        self.previous_data = None  # type:Data
        self.current_heading_3 = None
        self.current_styledtext = None
        self.current_box = None
        self.current_box_text = None  # type: StyledText
        self.current_paragraph = None
        self.current_story = None
        self.current_bullet = None
        self.current_bullet_x = None
        self.current_table = None
        self.current_table_row = None
        self.current_table_heading_count = 0

        # build our dictionaries for searching styles
        self.config = _load_config()
        self.module_config = _style_config_for_module(file.split("_")[0], self.config)

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

        self._origins = {}
        self._position_config = _position_config_for_module(
            file.split("_")[0], self.config
        )

        for origin_name in self._position_config:
            self._origins[origin_name] = self.find_origin_for_text(
                self._position_config[origin_name]
            )
            if not self._origins[origin_name]:
                print(
                    f"ERROR: could not find '{origin_name}' using"
                    f" in {file}. This is probably not ok."
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
        # print(
        #     f"{data.location.page} {style}"
        #     + f" style=[{data.style_data.font} {data.style_data.size}"
        #     + f" {data.style_data.color} {data.style_data.flags}]"
        #     + f" origin=[{data.origin.x},{data.origin.y}] '{data.text}'",
        #     file=self.output,
        # )
        print(data.to_json(), file=self.output)

    def find_style_for_text(self, text):
        """
        Inefficient search for a given string in the text to return it's style.

        Usually not so bad because we usually find most things close to
        the top.
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

    def find_origin_for_text(self, text) -> OriginData:
        """
        Inefficient search for a given string in the text to return it's data.

        Usually not so bad because we usually find most things close to
        the top.
        """
        for page in self.pages:
            for block in page["blocks"]:
                for line in block["lines"]:
                    for span in line["spans"]:
                        if text in span["text"].strip().lstrip():
                            origin = OriginData(
                                int(span["origin"][0]), int(span["origin"][1])
                            )
                            return origin

        return None

    def parse(self):
        """
        runs the parsing logic which will construct the internal structures for
        all Stories.
        """
        with open(f"txt/{self.module_name}.json", "w", encoding="utf-8") as self.output:
            # theoretically we now have all the style information we need. Now we
            # just iterate over the text and extract all the structure we need.
            for self._page_num, page in enumerate(self.pages):
                for self._block_num, block in enumerate(page["blocks"]):
                    for self._line_num, line in enumerate(block["lines"]):
                        for self._span_num, span in enumerate(line["spans"]):
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
        # if self._page_num != 1 and self._current_page_span == 0:
        #     skip_span = True

        # we could be in the bullshit part of the page at the start which we need to skip.
        # this strategy is basically just keep skipping til we find a span that is both
        # a recognized style AND it has some meaningful content. ' ' and '.' does not count.
        if self.page_bullshit_start and self._page_num != 0:
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
            skip_span and self._page_num != 0
        ):  # we don't handle skipping on the title page unless we really mean it
            self._current_page_span = self._current_page_span + 1
            return

        if self._page_num == 0:
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
            LocationData(
                self._page_num, self._block_num, self._line_num, self._span_num
            ),
        )
        self._current_page_span = self._current_page_span + 1

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

    def _line_path(self, data: Data) -> str:
        return f"{data.location.page}.{data.location.block}.{data.location.line}"

    def _block_path(self, data: Data) -> str:
        return f"{data.location.page}.{data.location.block}"

    def convert(self, campaign_path: str, campaign_name):
        """
        performs all conversion on the parsed data and outputs the campaign.
        """
        self.encounters = Encounter(campaign_name)

        self.previous_data = None
        self.current_heading_3 = None  # type:FormattedHeading
        self.current_styledtext = None  # type:StyledText
        self.current_box = None  # type:FormattedTableRow
        self.current_paragraph = None

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
            "bullet": self._convert_bullet,
            "table_title": self._convert_table_title,
            "table_heading": self._convert_table_heading,
            "table_text": self._convert_table_text,
            "table_text_italic": self._convert_table_text,
        }

        for data in self.data:
            if data.style in handlers:
                self._page_num = data.location.page
                self._block_num = data.location.block
                self._line_num = data.location.block
                self._span_num = data.location.span
                handlers[data.style](data)

                # just in case we need it to make decisions for the next loop
                self.previous_data = data

        campaign = Campaign(campaign_path, self.encounters)
        campaign.create()
        campaign.build()

    def _reset_all_conversion_state(self):
        self.current_styledtext = None
        self.current_box = None
        self.current_paragraph = None
        self.current_story = None
        self.current_bullet = None
        self.current_bullet_x = None
        self.current_table = None
        self.current_table_row = None
        self.current_table_heading_count = 0

    def _reset_paragraph_conversion_state(self):
        self.current_styledtext = None
        self.current_box = None
        self.current_paragraph = None
        self.current_bullet = None
        self.current_bullet_x = None
        self.current_table = None
        self.current_table_row = None
        self.current_table_heading_count = 0

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
            self.current_bullet = None
            return

        self._reset_all_conversion_state()
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

        self._reset_all_conversion_state()
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

        self._reset_paragraph_conversion_state()
        self.current_heading_3 = FormattedHeading(data.text)
        self.current_story.text.append(self.current_heading_3)

    def _convert_body(self, data: Data):
        # a single period or comma at the start of a span, regardless of it's style,
        # should just be added to the previous segment. because it leads to weard spaces.
        if (
            len(data.text) > 1
            and (data.text.startswith(". ") or data.text.startswith(", "))
            and self.current_styledtext is not None
        ):
            if len(data.text) == 2:
                self.current_styledtext.last_segment().append(data.text)
                return

            self.current_styledtext.last_segment().append(data.text[0:1])

            # remove those first two characters
            data.text = data.text[2:]

        # create a segment out of the body we get. We'll use it.
        segment = segment_from_data(data)

        # if we're building bullets text and the next span we get is further to the left than
        # the first data we saw after starting a bullet then it's a good bet we're done with
        # building bullets.

        if self.current_bullet_x is not None and self.current_bullet_x > data.origin.x:
            self._reset_paragraph_conversion_state()
            self.current_styledtext = StyledText([segment])
            self.current_paragraph = FormattedParagraph(self.current_styledtext)
            self.current_story.text.append(self.current_paragraph)
            return

        # OK but what if it wraps and then starts a new paragraph instead of continuing the
        # bullets? Then the next best thing we can do is check to see if it is aligned to
        # what we think is the left and right margins.

        if self.current_bullet_x is not None and (
            data.origin.x == self._origins["left_column_margin"].x
            or data.origin.x == self._origins["right_column_margin"].x
        ):
            self._reset_paragraph_conversion_state()
            self.current_styledtext = StyledText([segment])
            self.current_paragraph = FormattedParagraph(self.current_styledtext)
            self.current_story.text.append(self.current_paragraph)
            return

        # check to see if this is the first text added to a bullet

        if self.current_bullet is not None and self.current_bullet.length() == 0:
            # it is so we need to handle that.
            self.current_bullet_x = data.origin.x

        # if our previous span was also a body and we have a styledtext to add to it, we do
        # that.

        if (
            self.previous_data is not None
            and "body" in self.previous_data.style
            and self.current_styledtext is not None
        ):
            # we probably add this to the current styledtext block, but we need to check if it
            # might be a new paragraph
            if (
                self.current_styledtext.last_segment().text().strip().endswith(".")
                or self.current_styledtext.last_segment().text().strip().endswith(":")
            ) and data.text.startswith(" "):
                # probably a good bet it's a new paragraph. Not sure what else to go on.
                self._reset_paragraph_conversion_state()
                self.current_styledtext = StyledText([segment])
                self.current_paragraph = FormattedParagraph(self.current_styledtext)
                self.current_story.text.append(self.current_paragraph)
                return

            self.current_styledtext.append(segment)
            return

        # handle bullet
        if self.current_bullet is not None:
            self.current_styledtext.append(segment)
            return

        self.current_styledtext = StyledText([segment])
        if self.current_paragraph is None:
            self.current_paragraph = FormattedParagraph(self.current_styledtext)
            self.current_story.text.append(self.current_paragraph)
        else:
            self.current_paragraph.append(segment)

    def _convert_bullet(self, data):  # pylint: disable=unused-argument
        self.current_paragraph = None
        if self.current_bullet is None:
            self._reset_paragraph_conversion_state()  # we don't know the x-value of the text yet
            self.current_styledtext = StyledText([])
            self.current_bullet = FormattedList([self.current_styledtext])
            self.current_story.text.append(self.current_bullet)
        else:
            # each new bullet gets a new styledtext.
            self.current_styledtext = StyledText([])
            self.current_bullet.append(self.current_styledtext)

    def _convert_box_heading(self, data: Data):
        return
        if self.current_box is not None:
            # Already in a box? ok
            box_heading = StyledTextSegment(f"{data.text}\n\n", bold=True)
            self.current_box.rows[0].columns[0].append(box_heading)
        else:
            box_heading = StyledTextSegment(f"{data.text}\n\n", bold=True)
            row = FormattedTableRow([box_heading])
            self.current_box = FormattedTable([row])
            self.current_story.text.append(self.current_box)

    def _convert_table_title(self, data: Data):
        self._reset_paragraph_conversion_state()
        segment = StyledTextSegment(data.text, bold=True)
        self.current_styledtext = StyledText([segment])

        # Add the text as a kind of heading... wish FGU had <h2>
        paragraph = FormattedParagraph(self.current_styledtext)
        self.current_story.text.append(paragraph)

        # make a table.
        self.current_table = FormattedTable()
        self.current_story.text.append(self.current_table)

    def _convert_table_heading(self, data: Data):
        if self.current_table is None:
            self.current_table = FormattedTable()
            self.current_story.text.append(self.current_table)

        if self.current_table_row is None:
            self.current_table_row = FormattedTableRow()
            self.current_table.append(self.current_table_row)

        self.current_table_heading_count = self.current_table_heading_count + 1
        self.current_table_row.append(
            StyledText([StyledTextSegment(data.text, bold=True)])
        )

    def _convert_table_text(self, data: Data):
        if self.current_table_heading_count == 0:
            # tables without headings make no sense yet.
            return

        if self.current_table is None:
            self.current_table = FormattedTable()
            self.current_story.text.append(self.current_table)

        if self.current_table_row is None:
            self.current_table_row = FormattedTableRow()
            self.current_table.append(self.current_table_row)

        if self.current_table_row.count() >= self.current_table_heading_count:
            self.current_table_row = FormattedTableRow()
            self.current_table.append(self.current_table_row)

        italic = False
        if "italic" in data.style:
            italic = True

        segment = StyledTextSegment(data.text, italic=italic)
        self.current_styledtext = StyledText([segment])
        self.current_table_row.append(self.current_styledtext)


def _load_config():
    with open("config.json", "r", encoding="utf-8") as in_file:
        data = in_file.read()
    return json.loads(data)


def _style_config_for_module(code, config):
    module_config = config["patterns"]["base"]
    if code in config["patterns"]["overrides"]:
        for style in config["patterns"]["overrides"][code]:
            module_config[style] = config["patterns"]["overrides"][code][style]
    return module_config


def _position_config_for_module(code, config):
    position_config = config["patterns"]["positions"]
    if code in config["patterns"]["positions_overrides"]:
        for position in config["patterns"]["positions_overrides"][code]:
            position_config[position] = config["patterns"]["overrides"][code][position]
    return position_config


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
