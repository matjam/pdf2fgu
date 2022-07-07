import xml.etree.ElementTree as ET
from typing import List
from abc import ABC, abstractmethod


class FormattedTextObject(ABC):
    """
    FormattedTextObjects are top level objects that live at the root of a formattedtext
    xml section in a Fantasy Grounds object.
    """

    @abstractmethod
    def build(self, builder: ET.TreeBuilder):
        pass


class StyledTextSegment(FormattedTextObject):
    def __init__(self, text, *, bold=False, italic=False):
        self.text = text
        self.bold = bold
        self.italic = italic

    def build(self, builder: ET.TreeBuilder):
        if self.bold:
            builder.start("b", {})
        if self.italic:
            builder.start("i", {})

        builder.data(self.text)

        if self.italic:
            builder.end("i")
        if self.bold:
            builder.end("b")


class StyledText(FormattedTextObject):
    """
    StyledText contains multiple StyledTextSegments.
    """

    def __init__(self, data: List[StyledTextSegment]):
        self.data = data

    def build(self, builder: ET.TreeBuilder):
        for text in self.data:
            text.build(builder)

    def append(self, segment: StyledTextSegment):
        self.data.append(segment)

    def last_segment(self) -> str:
        return self.data[-1].text


class FormattedList(FormattedTextObject):
    def __init__(self, items: List[StyledText]):
        self.items = items

    def build(self, builder: ET.TreeBuilder):
        builder.start("list", {})
        for item in self.items:
            builder.start("li", {})
            item.build(builder)
            builder.end("li")
        builder.end("list")


class FormattedParagraph(FormattedTextObject):
    """
    represents a single paragraph.
    """

    def __init__(self, text: StyledText):
        self.text = text

    def build(self, builder: ET.TreeBuilder):
        builder.start("p", {})
        self.text.build(builder)
        builder.end("p")


class FormattedFrame(FormattedTextObject):
    """
    speech bubble thing in FGU. Does not support styling, but you can use newlines (&#13;)
    """

    def __init__(self, text: str):
        self.text = text

    def build(self, builder: ET.TreeBuilder):
        builder.start("frame", {})
        builder.data(self.text)
        builder.end("frame")


class FormattedTableRow(FormattedTextObject):
    def __init__(self, columns: List[StyledText]):
        self.columns = columns

    def build(self, builder: ET.TreeBuilder):
        builder.start("tr", {})
        for column in self.columns:
            builder.start("td", {})
            column.build(builder)
            builder.end("td")
        builder.end("tr")


class FormattedTable(FormattedTextObject):
    def __init__(self, rows: List[FormattedTableRow]):
        self.rows = rows

    def build(self, builder: ET.TreeBuilder):
        builder.start("table", {})
        for row in self.rows:
            row.build(builder)
        builder.end("table")


class FormattedLink(FormattedTextObject):
    def __init__(self, text: StyledText, *, cls: str = "", recordname: str = ""):
        self.text = text
        self.cls = cls
        self.recordname = recordname

    def build(self, builder: ET.TreeBuilder):
        builder.start("link", {"class": self.cls, "recordname": self.recordname})
        builder.data(self.text)
        builder.end("link")


class FormattedLinkList(FormattedTextObject):
    def __init__(self, links: List[FormattedLink]):
        self.links = links

    def build(self, builder: ET.TreeBuilder):
        builder.start("linklist", {})
        for link in self.links:
            link.build(builder)
        builder.end("linklist")


class FormattedHeading(FormattedTextObject):
    def __init__(self, text: str):
        self.text = text

    def build(self, builder: ET.TreeBuilder):
        builder.start("h", {})
        builder.data(self.text)
        builder.end("h")


class FormattedText:
    """
    This class is designed to allow you to freely construct a formattedtext document as
    used by Fantasy Grounds. Once you're finished feeding it structure, you can then
    grab the ElementTree data and stuff it into the campaign.
    """

    # These things are allowed at the top level of a formattedtext document.
    _allowed_toplevel_classes = (
        FormattedFrame,
        FormattedHeading,
        FormattedLinkList,
        FormattedList,
        FormattedParagraph,
        FormattedTable,
    )

    def __init__(self):
        self.document = []  # type: List[FormattedTextObject]

    def append(self, obj: FormattedTextObject):
        self.document.append(obj)

    def build(self, builder: ET.TreeBuilder):
        builder.start("text", {"type": "formattedtext"})
        for obj in self.document:
            obj.build(builder)
        builder.end("text")
