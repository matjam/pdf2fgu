import xml.etree.ElementTree as ET
from .formattedtext import *
from typing import List


class Story:
    """
    A class used to generate XML used by Fantasy Grounds Unity for Stories.

    Generally speaking FGU stores multiple things in the <encounter /> block. This class handles
    generating stories as shown in the Story panel in FGU.

    You are expected to instantiate Story as many times as you need; it will keep track of how
    many stories you instantiate and increment that globally. For that reason, it is currently
    not designed to work with existing campaigns but rather as a way to completely replace all
    of the stories in a new (or existing) campaign.
    """

    currentID = 1

    def __init__(self, name, *, locked=False, text: FormattedText):
        self.id = Story.currentID
        Story.currentID = Story.currentID + 1
        self.name = name
        self.locked = locked
        self.text = text

    def build(self, builder):
        builder.start(f"id-{self.id:05d}", {})

        if self.locked:
            builder.start("locked", {"type": "number"})
            builder.data("1")
            builder.end("locked")

        builder.start("name", {"type": "string"})
        builder.data(self.name)
        builder.end("name")
        self.text.build(builder)
        builder.end(f"id-{self.id:05d}")

    def addPartyStrengthTable(self):
        partyStrengthTable = [
            ["3-4 characters, APL less than", "Very weak"],
            ["3-4 characters, APL equivalent", "Weak"],
            ["3-4 characters, APL greater than", "Average"],
            ["5 characters, APL less than", "Weak"],
            ["5 characters, APL equivalent", "Average"],
            ["5 characters, APL greater than", "Strong"],
            ["6-7 characters, APL less than", "Average"],
            ["6-7 characters, APL equivalent", "Strong"],
            ["6-7 characters, APL greater than", "Very strong"],
        ]


class Encounter:
    """
    Object to hold all of the encounter stories generated. You can mess around with the stories
    member variable as much as you like until you call build().
    """

    def __init__(self, group_name: str):
        self.group_name = group_name
        self.stories = []  # type: List[Story]

    def build(self, builder: ET.TreeBuilder):
        builder.start("encounter", {})
        builder.start("category", {"name": self.group_name})
        for story in self.stories:
            story.build(builder)
        builder.end("category")
        builder.end("encounter")

    def append_story(self, story: Story):
        self.stories.append(story)
