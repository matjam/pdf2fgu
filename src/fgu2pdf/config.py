"""
Configuration file for pdf2fgu.

It is expected you will import only get_config and call that with the
module name. Some data is computed in that function.
"""

from dataclasses import dataclass, field
from typing import Dict, List

from dataclass_wizard import JSONSerializable
from dataclass_wizard.enums import LetterCase

from fgu2pdf.logs import logger
from fgu.enums import Position, Style


@dataclass
class SeasonConfig:
    # a dict of styles and the string to search to find that style in the PDF.
    styles: Dict[Style, str]

    # a dict of per-module style overrides; generally you should try to find a string
    # that will work for every module in a season but there's some cases where you need
    # to override the string to something else when the module is weird.
    styles_override: Dict[str, Dict[Style, str]]

    # a set of positions that we use for processing. For example, to work out what the
    # left column margin is.
    positions: Dict[Position, str]

    # per module positions as above.
    positions_override: Dict[str, Dict[Position, str]]


@dataclass
class StylePatterns:
    # a single character specified in this list will be given the associated style
    character_override: Dict[str, Style]

    # season specific configuration for search strings.
    seasons: Dict[str, SeasonConfig]

    # This field is computed at runtime after loading the config.
    styles: Dict[Style, str] = field(default_factory=dict)

    # This field is computed at runtime after loading the config.
    positions: Dict[str, str] = field(default_factory=dict)


@dataclass
class Config(JSONSerializable):
    style_patterns: StylePatterns
    skip_strings: List[str]

    class Meta(JSONSerializable.Meta):
        key_transform_with_load = LetterCase.SNAKE
        key_transform_with_dump = LetterCase.SNAKE
        debug_enabled = True


def get_config(module_name: str) -> Config:
    with open("config2.json", "r", encoding="utf-8") as config_file:
        config_json = config_file.read()

    season = module_name.split("-")[0]
    config = Config.from_json(config_json)
    # overlay the styles and positions dicts with what we get from the per adventure overrides.
    if season not in config.style_patterns.seasons:
        raise Exception(f"season code {season} does not exist in config.")

    # construct the config.style_patterns.styles and config.style_patterns.positions structures
    for style_name, style_text in config.style_patterns.seasons[season].styles.items():
        config.style_patterns.styles[style_name] = style_text

    # override the styles if the specific module exists
    if module_name in config.style_patterns.seasons[season].styles_override:
        for style_name, style_text in (
            config.style_patterns.seasons["DDAL04"].styles_override[module_name].items()
        ):
            config.style_patterns.styles[style_name] = style_text

    for name, text in config.style_patterns.styles.items():
        if text == "MUST_OVERRIDE":
            logger.warning(f"style {name} should be overwridden for {module_name}")

    # construct the config.style_patterns.positions and config.style_patterns.positions structures
    for name, text in config.style_patterns.seasons[season].positions.items():
        config.style_patterns.positions[name] = text

    # override the positions if the specific module exists
    if module_name in config.style_patterns.seasons[season].positions_override:
        for name, text in (
            config.style_patterns.seasons[season]
            .positions_override[module_name]
            .items()
        ):
            config.style_patterns.positions[name] = text

    return config
