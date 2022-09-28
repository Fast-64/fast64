from xml.etree.ElementTree import parse as parseXML, Element
from .oot_data import OoT_BaseElement


def getXMLRoot(xmlPath: str) -> Element:
    """Parse an XML file and return its root element"""
    try:
        return parseXML(xmlPath).getroot()
    except:
        from ...utility import PluginError

        raise PluginError(f"ERROR: File '{xmlPath}' is missing or malformed.")


def getEnumList(dataList: list[OoT_BaseElement], customItemName: str):
    """Returns lists containing data for Blender's enum properties"""
    enumPropItems: list[tuple] = []
    legacyEnumPropItems: list[tuple] = []  # for older blends
    customItem = ("Custom", customItemName, "Custom")

    for elem in dataList:
        enumPropItems.append((elem.key, elem.name, elem.id))
        legacyEnumPropItems.append((elem.id, elem.name, elem.id))

    enumPropItems.insert(0, customItem)
    legacyEnumPropItems.insert(0, customItem)
    return enumPropItems, legacyEnumPropItems
