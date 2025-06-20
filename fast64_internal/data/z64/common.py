from xml.etree.ElementTree import parse as parseXML, Element
from dataclasses import dataclass


@dataclass
class Z64_BaseElement:
    id: str
    key: str
    name: str
    index: int


def get_xml_root(xmlPath: str) -> Element:
    """Parse an XML file and return its root element"""
    try:
        return parseXML(xmlPath).getroot()
    except:
        from ...utility import PluginError

        raise PluginError(f"ERROR: File '{xmlPath}' is missing or malformed.")
