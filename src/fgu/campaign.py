"""
This module implements classes for managing FGU Campaigns.
"""

import os
from xml.etree import ElementTree as ET

from .encounter import Encounter


class Campaign:
    """
    A class for creating and updating an FGU Campaign.
    """

    _campaign_registry = """
{
	["sidebarvisibility"] = 0,
	["setup"] = true,
	["OptDDCL-custom"] = "",
	["OptHRDD"] = "",
	["sidebarexpand"] = {
		[1] = "tool",
		[2] = "campaign",
		[3] = "player",
		[4] = "library",
		[5] = "create",
	},
	["sidebarversion"] = 2,
}
"""

    def __init__(self, path: str, encounter: Encounter):
        self.path = path
        self.encounter = encounter
        self.tree = None
        self.root = None

    def create(self):
        """
        will only overwrite files if they are missing.

        It actually doesn't seem you need to do anything other than drop
        a db.xml; FGU will try to do the right thing and make the other
        files you need. But we'll do this...
        """
        print(f"creating campaign at {self.path}")

        if not os.path.isdir(self.path):
            os.mkdir(self.path)

        if not os.path.isfile(f"{self.path}/campaign.xml"):
            campaign_xml_root = ET.Element("root")
            campaign_xml_root.set("version", "4.2")
            campaign_xml_root.set("dataversion", "20220411")
            ET.SubElement(campaign_xml_root, "ruleset").text = "5E"
            ET.SubElement(campaign_xml_root, "server").text = "personal"
            ET.SubElement(campaign_xml_root, "port").text = "1802"

            tree = ET.ElementTree(campaign_xml_root)
            with open(f"{self.path}/campaign.xml", "wb") as output:
                tree.write(output, encoding="utf-8", xml_declaration=True)

        if not os.path.isfile(f"{self.path}/db.xml"):
            db_xml_root = ET.Element("root")
            db_xml_root.set("version", "4.2")
            db_xml_root.set("dataversion", "20220411")
            db_xml_root.set("release", "8.1|CoreRPG:5")

            tree = ET.ElementTree(db_xml_root)
            ET.indent(db_xml_root, space="\t")

            with open(f"{self.path}/db.xml", "wb") as output:
                tree.write(output, encoding="utf-8", xml_declaration=True)

        if not os.path.isfile(f"{self.path}/CampaignRegistry.lua"):
            with open(
                f"{self.path}/CampaignRegistry.lua", "w", encoding="utf-8"
            ) as output:
                print(self._campaign_registry, file=output)

    def build(self):
        """
        Builds the campaign db.xml file by building the encounter structure
        under it. Note that we preserve all the other data in the db.xml
        currently; however all data under the.

        <encounter> section will be removed and replaced.
        """
        self.tree = ET.parse(f"{self.path}/db.xml")
        self.root = self.tree.getroot()

        # remove any existing story information
        for encounter in self.root.findall("encounter"):
            self.root.remove(encounter)

        builder = ET.TreeBuilder()
        self.encounter.build(builder)
        self.root.append(builder.close())

        ET.indent(self.tree, space="\t")
        with open(f"{self.path}/db.xml", "wb") as output:
            self.tree.write(output, encoding="utf-8", xml_declaration=True)

        # stupid hack to work around idiocy in the python etree implementation. Or
        # maybe it's idiocy in Fantasy Grounds? I don't care. It's idiocy because
        # it's XML. XML is stupid.
        with open(f"{self.path}/db.xml", "r", encoding="utf-8") as reader:
            xml_data = reader.read()

        xml_data = xml_data.replace("&amp;#13;", "&#13;")

        with open(f"{self.path}/db.xml", "w", encoding="utf-8") as writer:
            writer.write(xml_data)
