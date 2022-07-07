from xml.etree import ElementTree as ET
from .encounter import Encounter
import os


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


class Campaign:
    def __init__(self, path: str):
        self.path = path
        self.encounter = None

    def create(self):
        print(f"creating campaign at {self.path}")

        if not os.path.isdir(self.path):
            os.mkdir(self.path)

        campaignXMLroot = ET.Element("root")
        campaignXMLroot.set("version", "4.2")
        campaignXMLroot.set("dataversion", "20220411")
        ET.SubElement(campaignXMLroot, "ruleset").text = "5E"
        ET.SubElement(campaignXMLroot, "server").text = "personal"
        ET.SubElement(campaignXMLroot, "port").text = "1802"

        tree = ET.ElementTree(campaignXMLroot)
        with open(f"{self.path}/campaign.xml", "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)

        db_xml_root = ET.Element("root")
        db_xml_root.set("version", "4.2")
        db_xml_root.set("dataversion", "20220411")
        db_xml_root.set("release", "8.1|CoreRPG:5")

        tree = ET.ElementTree(db_xml_root)
        with open(f"{self.path}/db.xml", "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)

        with open(f"{self.path}/CampaignRegistry.lua", "w") as f:
            print(_campaign_registry, file=f)

    def add_encounter(self, encounter: Encounter):
        self.encounter = encounter

    def write(self):
        root = ET.Element("root")
        root.set("version", "4.2")
        root.set("dataversion", "20220411")
        root.set("release", "8.1|CoreRPG:5")
        root.append(self.encounter.encounter())
        tree = ET.ElementTree(root)
        ET.indent(tree, space="\t")

        with open(f"{self.path}/db.xml", "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)
