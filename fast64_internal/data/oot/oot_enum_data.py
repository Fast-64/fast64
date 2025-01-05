from dataclasses import dataclass, field
from os import path
from .oot_getters import getXMLRoot
from .oot_data import OoT_BaseElement

# Note: "enumData" in this context refers to an OoT Object file (like ``gameplay_keep``)


@dataclass
class OoT_ItemElement(OoT_BaseElement):
    parentKey: str

    def __post_init__(self):
        # generate the name from the id

        if self.name is None:
            keyToPrefix = {
                "csCmd": "CS_CMD",
                "csMiscType": "CS_MISC",
                "csTextType": "CS_TEXT",
                "csFadeOutSeqPlayer": "CS_FADE_OUT",
                "csTransitionType": "CS_TRANS",
                "csDestination": "CS_DEST",
                "csPlayerCueId": "PLAYER_CUEID",
                "naviQuestHintType": "NAVI_QUEST_HINTS",
                "ocarinaSongActionId": "OCARINA_ACTION",
            }

            self.name = self.id.removeprefix(f"{keyToPrefix[self.parentKey]}_")

            if self.parentKey in ["csCmd", "csPlayerCueId"]:
                split = self.name.split("_")
                if self.parentKey == "csCmd" and "ACTOR_CUE" in self.id:
                    self.name = f"Actor Cue {split[-2]}_{split[-1]}"
                else:
                    self.name = f"Player Cue Id {split[-1]}"
            else:
                self.name = self.name.replace("_", " ").title()


@dataclass
class OoT_EnumElement(OoT_BaseElement):
    items: list[OoT_ItemElement]
    itemByKey: dict[str, OoT_ItemElement] = field(default_factory=dict)
    itemByIndex: dict[int, OoT_ItemElement] = field(default_factory=dict)
    itemById: dict[int, OoT_ItemElement] = field(default_factory=dict)

    def __post_init__(self):
        self.itemByKey = {item.key: item for item in self.items}
        self.itemByIndex = {item.index: item for item in self.items}
        self.itemById = {item.id: item for item in self.items}


class OoT_EnumData:
    """Cutscene and misc enum data"""

    def __init__(self):
        # general enumData list
        self.enumDataList: list[OoT_EnumElement] = []

        # Path to the ``EnumData.xml`` file
        enumDataXML = path.dirname(path.abspath(__file__)) + "/xml/EnumData.xml"
        enumDataRoot = getXMLRoot(enumDataXML)

        for enum in enumDataRoot.iterfind("Enum"):
            self.enumDataList.append(
                OoT_EnumElement(
                    enum.attrib["ID"],
                    enum.attrib["Key"],
                    None,
                    None,
                    [
                        OoT_ItemElement(
                            item.attrib["ID"],
                            item.attrib["Key"],
                            # note: the name sets automatically after the init if None
                            item.attrib["Name"] if enum.attrib["Key"] == "seqId" else None,
                            int(item.attrib["Index"]),
                            enum.attrib["Key"],
                        )
                        for item in enum
                    ],
                )
            )

        # create list of tuples used by Blender's enum properties
        self.deletedEntry = ("None", "(Deleted from the XML)", "None")

        self.ootEnumCsCmd: list[tuple[str, str, str]] = []
        self.ootEnumCsMiscType: list[tuple[str, str, str]] = []
        self.ootEnumCsTextType: list[tuple[str, str, str]] = []
        self.ootEnumCsFadeOutSeqPlayer: list[tuple[str, str, str]] = []
        self.ootEnumCsTransitionType: list[tuple[str, str, str]] = []
        self.ootEnumCsDestination: list[tuple[str, str, str]] = []
        self.ootEnumCsPlayerCueId: list[tuple[str, str, str]] = []
        self.ootEnumNaviQuestHintType: list[tuple[str, str, str]] = []
        self.ootEnumOcarinaSongActionId: list[tuple[str, str, str]] = []
        self.ootEnumSeqId: list[tuple[str, str, str]] = []

        self.enumByID = {enum.id: enum for enum in self.enumDataList}
        self.enumByKey = {enum.key: enum for enum in self.enumDataList}

        for key in self.enumByKey.keys():
            setattr(self, "ootEnum" + key[0].upper() + key[1:], self.getOoTEnumData(key))

    def getOoTEnumData(self, enumKey: str):
        enum = self.enumByKey[enumKey]
        firstIndex = min(1, *(item.index for item in enum.items))
        lastIndex = max(1, *(item.index for item in enum.items)) + 1
        enumData = [self.deletedEntry] * lastIndex
        custom = ("Custom", "Custom", "Custom")

        for item in enum.items:
            if item.index < lastIndex:
                identifier = item.key
                enumData[item.index] = (identifier, item.name, item.id)

        if firstIndex > 0:
            enumData[0] = custom
        else:
            enumData.insert(0, custom)

        return enumData
