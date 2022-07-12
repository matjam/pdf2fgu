"""
Core logic for the conversion of AL PDFs into FGU campaigns.
"""
from typing import Any, Dict, Generator, List, Tuple

import fitz

import fgu.data as data
import fgu.enums as enums
from fgu2pdf.config import get_config
from fgu2pdf.logs import logger
from fgu.campaign import Campaign
from fgu.encounter import Encounter, Story
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


class PDFConverter:
    def __init__(
        self, pdf_path: str, module_file: str, module_name: str, fgu_path: str
    ):
        self._pdf_path = pdf_path
        self._campaign_path = f"{fgu_path}/campaigns/pdf2fgu - {module_name}"
        self._module_file = module_file
        self._module_code = module_file.split("_")[0]
        self._module_name = module_name
        self._config = get_config(self._module_code)
        self._pages = []  # type: Any
        self._output = None

        # maps the "style string" we compute from all the style data in the pdf
        # to a specific style we have defined in the config/enums.
        self._styles = {}  # type: Dict[str, enums.Style]

        # contains all preprocessed rows of data.
        self._data = []  # type: List[data.Row]
        self._data_row = self._parsed_spans()
        self._current_row = None  # type None|data.Row
        self._current_row_idx = 0

        # does a first pass, finding in the PDF all the styles and processing
        # it into the _data property.
        self._load_pdf()
        self._analyze()

    def _load_pdf(self):
        file_path = f"{self._pdf_path}/{self._module_file}"
        doc = fitz.open(file_path)

        for page in doc.pages():
            text_page = page.get_textpage()
            text_dict = text_page.extractDICT()
            self._pages.append(text_dict)

    def _find_style_string_for_text(self, text) -> str | None:
        """
        Inefficient search for a given string in the text to return it's style.

        Usually not so bad because we usually find most things close to
        the top.
        """
        for page in self._pages[1:]:
            for block in page["blocks"]:
                for line in block["lines"]:
                    for span in line["spans"]:
                        style_string = self._style_string_from_span(span)
                        if text in span["text"].strip().lstrip():
                            return style_string
        return None

    def _analyze(self):
        for style_id, text in self._config.style_patterns.styles.items():
            style_string = self._find_style_string_for_text(text)
            if not style_string:
                logger.warning(
                    f"could not find '{style_id}' using"
                    f" '{text}' in {self._module_file}."
                )
            self._styles[style_string] = style_id

    def convert(self):
        self._parse()

        self._data_row = self._parsed_spans()
        encounters = self._parse_encounter()
        campaign = Campaign(self._campaign_path, encounters)
        campaign.create()
        campaign.build()

    def add_parsed_span(
        self,
        text: str,
        style: data.Style,
        style_info: data.StyleInfo,
        origin: data.Origin,
        location: data.Location,
    ):
        """
        Function used to build the array that holds all the parsed page data.
        """
        row = data.Row(
            text,
            style,
            style_info,
            origin,
            location,
        )

        self._data.append(row)
        print(row.to_json(), file=self._output)

    def _page_spans(self):
        """
        generator that yields spans from the PDF page data.
        """
        # theoretically we now have all the style information we need. Now we
        # just iterate over the text and extract all the structures.
        for page_num, page in enumerate(self._pages):
            for block_num, block in enumerate(page["blocks"]):
                for line_num, line in enumerate(block["lines"]):
                    for span_num, span in enumerate(line["spans"]):
                        yield (
                            span,
                            data.Location(page_num, block_num, line_num, span_num),
                        )

    def _style_string_from_span(self, span) -> str:
        return f"{span['font']} {span['size']} {span['flags']} {span['color']}".lower()

    def _parse(self):
        with open(
            f"json/{self._module_name}.ndjson", "w", encoding="utf-8"
        ) as self._output:
            self._parse_spans()

    def _parse_spans(self):
        """
        performs the parsing on the spans to try and clean up the data a little
        and do the initial matching of fonts to styles.

        We then use this in the next phase to actually construct the
        stories.
        """

        previous_page = 0
        page_start = False
        previous_span = None
        for span, location in self._page_spans():
            skip_span = False
            # make sure we skip things we never want in the module.
            for skip_string in self._config.skip_strings:
                if skip_string in span["text"]:
                    skip_span = True
                    continue

            if skip_span:
                continue

            style_string = self._style_string_from_span(span)

            style_data = data.StyleInfo(
                span["font"],
                span["size"],
                span["flags"],
                span["color"],
                "bold" in span["font"].lower(),
                "italic" in span["font"].lower(),
            )

            origin = (data.Origin(int(span["origin"][0]), int(span["origin"][1])),)

            text = span["text"]  # type: str

            # Replace characters we find with more sensible ones.
            for old, new in self._config.replace_characters.items():
                if old in text:
                    text = text.replace(old, new)

            # check if we flipped to another page
            if previous_page != location.page:
                page_start = True

            style = enums.Style.UNKNOWN

            if location.page == 0:
                # we run different logic for the title page; the fonts used on this page are usually
                # completely different to the rest of the document. We don't try to figure out the
                # styles here; we just make everything "body" and then look at the font names
                # to determine if they are Italic or bold or bold/italic.

                if "italic" in style_string and not "bold" in style_string:
                    style = enums.Style.BODY_ITALIC
                elif "bold" in style_string and not "italic" in style_string:
                    style = enums.Style.BODY_BOLD
                elif "bold" in style_string and "italic" in style_string:
                    style = enums.Style.BODY_BOLD_ITALIC
                else:
                    style = enums.Style.BODY
            elif (
                len(text) == 1
                and text in self._config.style_patterns.character_override
            ):
                # some characters are just hardcoded always to be a thing.
                style = self._config.style_patterns.character_override[text]
            elif style_string in self._styles:
                style = self._styles[style_string]

            if style == enums.Style.UNKNOWN and len(text.lstrip().strip()) > 0:
                continue

            if (
                style == enums.Style.UNKNOWN
                and len(text.lstrip().strip()) == 0
                and page_start
            ):
                continue

            if previous_span is not None and previous_span["text"] == span["text"]:
                continue

            page_start = False
            self.add_parsed_span(text, style, style_data, origin, location)
            previous_span = span

    def _parsed_spans(self) -> Generator[Tuple[int, data.Row], None, None]:
        """
        generator that yields spans from the parsed page data.
        """

        for index, row in enumerate(self._data):
            yield (index, row)

    def _parse_title_story(self) -> Story:
        """
        iterates through the first page loading all the text into a story.
        """

        # first, skip until we see a big font, > 12 as that's the title
        for self._current_row_idx, row in self._data_row:
            if row.style_info.size > 12:
                logger.info(f"found the title: {row.text}")
                break

        styledtext = StyledText()
        para = FormattedParagraph(styledtext)
        content.append(para)
        first_paragraph = True
        segment = None  # type: None | StyledTextSegment
        for self._current_row_idx, row in self._data_row:
            if row.location.page != 0:
                break

            if row.text.strip() == "":
                if first_paragraph:
                    first_paragraph = False
                    continue

                segment = None
                styledtext = StyledText()
                para = FormattedParagraph(styledtext)
                content.append(para)
                continue

            if segment is not None and segment.is_bold() and row.style_info.italic:
                segment = StyledTextSegment(
                    "&#13;" + row.text,
                    bold=row.style_info.bold,
                    italic=row.style_info.italic,
                )
                styledtext.append(segment)
                continue

            if segment is not None and row.style_info.bold:
                segment = StyledTextSegment(
                    row.text, bold=row.style_info.bold, italic=row.style_info.italic
                )
                styledtext = StyledText(segment)
                para = FormattedParagraph(styledtext)
                content.append(para)
                continue

            if (
                segment is not None
                and segment.is_bold() == row.style_info.bold
                and segment.is_italic() == row.style_info.italic
            ):
                segment.append(row.text)
            else:
                segment = StyledTextSegment(
                    row.text, bold=row.style_info.bold, italic=row.style_info.italic
                )
                styledtext.append(segment)

        return story

    def _parse_story(self) -> Story:
        pass

    def _parse_encounter(self) -> Encounter:
        """
        start of our journey - we parse the encounter, which in turn parses
        stories, paragraphs, etc, recursively.
        """
        encounters = Encounter(self._module_name)
        encounters.append_story(self._parse_title_story())
        while self._current_row_idx <= len(self._data):
            story = self._parse_story()
            encounters.append_story(story)
        return encounters
