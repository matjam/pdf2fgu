"""
defines enums used within the tool.
"""

from enum import Enum


class Style(Enum):
    """
    Enum type for all supported styles that we use for parsing the PDFs.
    """

    UNKNOWN = "unknown"
    EMPTY = "empty"
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


BODY_STYLES = {
    Style.BODY,
    Style.BODY_BOLD,
    Style.BODY_ITALIC,
    Style.BODY_BOLD_ITALIC,
}


class Position(Enum):
    """
    Enum type for supported position information.
    """

    LEFT_COLUMN_MARGIN = "left_column_margin"
    LEFT_COLUMN_INDENT = "left_column_indent"
    RIGHT_COLUMN_MARGIN = "right_column_margin"
    RIGHT_COLUMN_INDENT = "right_column_indent"
