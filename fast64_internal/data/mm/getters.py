from xml.etree.ElementTree import parse as parse_xml, Element
from pathlib import Path


def get_xml_root(xml_path: Path) -> Element:
    """Parse an XML file and return its root element"""
    try:
        return parse_xml(xml_path.resolve()).getroot()
    except:
        from ...utility import PluginError

        raise PluginError(f"ERROR: File '{xml_path}' is missing or malformed.")
