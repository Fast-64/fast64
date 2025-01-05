from xml.etree.ElementTree import parse as parseXML, Element


def getXMLRoot(xmlPath: str) -> Element:
    """Parse an XML file and return its root element"""
    try:
        return parseXML(xmlPath).getroot()
    except:
        from ...utility import PluginError

        raise PluginError(f"ERROR: File '{xmlPath}' is missing or malformed.")
