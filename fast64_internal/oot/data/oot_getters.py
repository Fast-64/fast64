from xml.etree.ElementTree import parse as parseXML, Element
from .oot_data import OoT_BaseElement


def getXMLRoot(xmlPath: str) -> Element:
    """Parse an XML file and return its root element"""
    try:
        return parseXML(xmlPath).getroot()
    except:
        from ...utility import PluginError

        raise PluginError(f"ERROR: File '{xmlPath}' is missing or malformed.")


def getEnumList(dataList: list[OoT_BaseElement], customName: str):
    """Returns lists containing data for Blender's enum properties"""
    enumPropItems: list[tuple] = []
    legacyEnumPropItems: list[tuple] = []  # for older blends
    customObj = ("Custom", customName, "Custom")

    for elem in dataList:
        enumPropItems.append((elem.key, elem.name, elem.id))
        legacyEnumPropItems.append((elem.id, elem.name, elem.id))

    enumPropItems.insert(0, customObj)
    legacyEnumPropItems.insert(0, customObj)
    return enumPropItems, legacyEnumPropItems
