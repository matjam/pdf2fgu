"""
classes for creating FGU 'formattedtext' XML structures.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import List, Optional


class FormattedTextObject(ABC):
    """
    FormattedTextObjects are top level objects that live at the root of a
    formattedtext xml section in a Fantasy Grounds object.
    """

    @abstractmethod
    def build(self, builder: ET.TreeBuilder):
        """
        build is implemented to construct recursively all XML for the objects
        contained by the class that inherits this abstract class.
        """

    def length(self) -> int:
        """
        returns the length of the text held by the object.

        For example, a StyledText object would have x number of
        StyledTextSegments. Calling .length() on a StyledText object
        would return a sum of all the .length() of all the
        StyledTextSegments.
        """

    def append(self, obj: str | FormattedTextObject):
        """
        appends the correct child type to the container.
        """


class StyledTextSegment(FormattedTextObject):
    """
    A single segment of text that has a single style.

    A StyledText is made up of multiple StyledTextSegments.
    """

    def __init__(self, text, *, bold=False, italic=False):
        self._text = text
        self._bold = bold
        self._italic = italic

    def build(self, builder: ET.TreeBuilder):
        if self._bold:
            builder.start("b", {})
        if self._italic:
            builder.start("i", {})

        builder.data(self._text)

        if self._italic:
            builder.end("i")
        if self._bold:
            builder.end("b")

    def length(self) -> int:
        return len(self._text)

    def append(self, obj: str | FormattedTextObject):
        if obj is None or not isinstance(obj, str):
            raise TypeError("must provide a str to append()")
        self._text = self._text + obj

    @property
    def text(self) -> str:
        """
        returns the text of the segment.
        """
        return self._text

    @property
    def bold(self) -> bool:
        return self._bold

    @property
    def italic(self) -> bool:
        return self._italic


class StyledText(FormattedTextObject):
    """
    StyledText contains multiple StyledTextSegments.
    """

    def __init__(self):
        self._segments = []  # type: List[StyledTextSegment]

    def build(self, builder: ET.TreeBuilder):
        for text in self._segments:
            text.build(builder)

    def length(self) -> int:
        total_length = 0
        for text in self._segments:
            total_length = total_length + text.length()
        return total_length

    def append(self, obj: str | FormattedTextObject):
        if obj is None or not isinstance(obj, StyledTextSegment):
            raise TypeError("must provide a StyledTextSegment to append()")

        self._segments.append(obj)

    @property
    def last_segment(self) -> StyledTextSegment:
        """
        returns the last segment.
        """
        return self._segments[-1]

    @property
    def segments(self):
        return self._segments


class FormattedList(FormattedTextObject):
    """
    Bullet point lists in FGU.
    """

    def __init__(self, items: List[StyledText]):
        self._items = items

    def build(self, builder: ET.TreeBuilder):
        builder.start("list", {})
        for item in self._items:
            if item.length() > 0:
                builder.start("li", {})
                item.build(builder)
                builder.end("li")
        builder.end("list")

    def length(self) -> int:
        total_length = 0
        for item in self._items:
            total_length = total_length + item.length()
        return total_length

    def append(self, obj: str | FormattedTextObject):
        if obj is None or not isinstance(obj, StyledText):
            raise TypeError("must provide a StyledText to append()")
        self._items.append(obj)


class FormattedParagraph(FormattedTextObject):
    """
    represents a single paragraph.
    """

    def __init__(self):
        self._styled_text = StyledText()

    def build(self, builder: ET.TreeBuilder):
        builder.start("p", {})
        self._styled_text.build(builder)
        builder.end("p")

    def length(self) -> int:
        return self._styled_text.length()

    def append(self, obj: str | FormattedTextObject):
        if obj is None or not isinstance(obj, StyledTextSegment):
            raise TypeError("must provide a StyledTextSegment to append()")
        self._styled_text.append(obj)

    @property
    def styled_text(self):
        return self._styled_text


class FormattedFrame(FormattedTextObject):
    """
    speech bubble thing in FGU.

    Does not support styling, but you can use newlines (&#13;)
    """

    def __init__(self, text: str):
        self._text = text

    def build(self, builder: ET.TreeBuilder):
        builder.start("frame", {})
        builder.data(self._text)
        builder.end("frame")

    def length(self) -> int:
        return len(self._text)

    def append(self, obj: str | FormattedTextObject):
        if obj is None or not isinstance(obj, str):
            raise TypeError("must provide a str to append()")

        self._text = self._text + obj


class FormattedTableRow(FormattedTextObject):
    """
    An FGU table row.
    """

    def __init__(self):
        self._columns = []  # type: List[StyledText]

    def build(self, builder: ET.TreeBuilder):
        builder.start("tr", {})
        for column in self._columns:
            builder.start("td", {})
            column.build(builder)
            builder.end("td")
        builder.end("tr")

    def length(self) -> int:
        total_length = 0
        for column in self._columns:
            total_length = total_length + column.length()
        return total_length

    def count(self) -> int:
        """
        returns a count of the columns.
        """
        return len(self._columns)

    def append(self, obj: str | FormattedTextObject):
        if obj is None or not isinstance(obj, StyledText):
            raise TypeError("must provide a StyledText to append()")
        self._columns.append(obj)


class FormattedTable(FormattedTextObject):
    """
    An FGU table.
    """

    def __init__(self):
        self._rows = []  # type: List[FormattedTableRow]

    def build(self, builder: ET.TreeBuilder):
        builder.start("table", {})
        for row in self._rows:
            row.build(builder)
        builder.end("table")

    def length(self) -> int:
        total_length = 0
        for row in self._rows:
            total_length = total_length + row.length()
        return total_length

    def append(self, obj: str | FormattedTextObject):
        if obj is None or not isinstance(obj, FormattedTableRow):
            raise TypeError("must provide a FormattedTableRow to append()")
        self._rows.append(obj)


class FormattedLink(FormattedTextObject):
    """
    an FGU link.
    """

    def __init__(self, text: StyledText, *, cls: str = "", recordname: str = ""):
        self._text = text
        self._cls = cls
        self._recordname = recordname

    def build(self, builder: ET.TreeBuilder):
        builder.start("link", {"class": self._cls, "recordname": self._recordname})
        self._text.build(builder)
        builder.end("link")

    def length(self) -> int:
        return self._text.length()

    def append(self, obj: str | FormattedTextObject):
        if obj is None or not isinstance(obj, StyledTextSegment):
            raise TypeError("must provide a StyledTextSegment to append()")
        self._text.append(obj)


class FormattedLinkList(FormattedTextObject):
    """
    A list of Links.
    """

    def __init__(self, links: List[FormattedLink]):
        self.links = links

    def build(self, builder: ET.TreeBuilder):
        builder.start("linklist", {})
        for link in self.links:
            link.build(builder)
        builder.end("linklist")

    def length(self) -> int:
        total_length = 0
        for link in self.links:
            total_length = total_length + link.length()
        return total_length

    def append(self, obj: str | FormattedTextObject):
        if obj is None or not isinstance(obj, FormattedLink):
            raise TypeError("must provide a FormattedLink to append()")


class FormattedHeading(FormattedTextObject):
    """
    An FGU Heading.
    """

    def __init__(self, text: str):
        self.text = text

    def build(self, builder: ET.TreeBuilder):
        builder.start("h", {})
        builder.data(self.text)
        builder.end("h")

    def length(self) -> int:
        return len(self.text)

    def append(self, obj: str | FormattedTextObject):
        if obj is None or not isinstance(obj, str):
            raise TypeError("must provide a str to append()")
        self.text = self.text + obj


class FormattedText:
    """
    This class is designed to allow you to freely construct a formattedtext
    document as used by Fantasy Grounds.

    Once you're finished feeding it structure, you can then grab the
    ElementTree data and stuff it into the campaign.
    """

    def __init__(self):
        self._document = []  # type: List[FormattedTextObject]

    def append(self, obj: FormattedTextObject):
        """
        Append a FormattedTextObject to the current FormattedText.
        """
        if obj is None or not isinstance(obj, FormattedTextObject):
            raise TypeError("must provide a FormattedTextObject to append()")
        self._document.append(obj)

    def build(self, builder: ET.TreeBuilder):
        """
        recursively build the FormattedText object using the
        ElementText.TreeBuilder.
        """
        builder.start("text", {"type": "formattedtext"})
        for obj in self._document:
            obj.build(builder)
        builder.end("text")

    def length(self) -> int:
        """
        gets the textual length of all of the text contained within this
        FormattedText object.
        """
        total_length = 0
        for obj in self._document:
            total_length = total_length + obj.length()
        return total_length
