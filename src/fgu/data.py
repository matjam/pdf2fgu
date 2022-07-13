"""
classes for storing data used during processing.
"""
from dataclasses import dataclass

from dataclass_wizard import JSONWizard

from .enums import Style


@dataclass
class Origin:
    """
    Actual x & y co-ordinates on the page for a span.

    Useful when trying to figure out the relationship of spans.
    """

    x: int
    y: int


@dataclass
class StyleInfo:
    """
    Provides information about the style as extracted from the PDF.
    """

    font: str
    size: float
    flags: int
    color: str
    bold: bool
    italic: bool


@dataclass
class Location:
    """
    Provides the original location in the page, block, line and span of a
    specific span.
    """

    page: int
    block: int
    line: int
    span: int


@dataclass
class Row(JSONWizard):
    """
    Each parsed span of data from the PDF, with all of the information we used
    to make parsing decisions extracted from the PDF data.
    """

    text: str
    style: Style
    style_info: StyleInfo
    position: Origin
    location: Location


@dataclass
class HeadingLocation:
    """
    data about the row start/end for each heading found in the document.
    """

    text: str
    htype: Style
    start: int
    length: int
