import re
from ..utility import *


class BlenderEnumItem:
    def __init__(self, key, name, description):
        self.key = key
        self.name = name
        self.description = description

    def toC(self):
        return (
            '\t("' + self.key + '", "' + self.name + '", "' + self.description + '"),\n'
        )


def createEnum(enumName, enumList):
    enumData = enumName + " = [\n"
    for item in enumList:
        enumData += item.toC()
    enumData += "]"
    return enumData


def parseEnumFile(data, enumName, enumPrefix, ignoreList, includeCustom):
    if includeCustom:
        enumList = [BlenderEnumItem("Custom", "Custom", "Custom")]
    else:
        enumList = []

    checkResult = re.search("typedef enum \{([^\}]*)\} " + enumName, data, re.DOTALL)
    if checkResult is None:
        raise ValueError("Cannot find enum by name: " + str(enumName))
    enumData = checkResult.group(1)

    for matchResult in re.finditer(enumPrefix + "\_(.*),*", enumData):
        oldName = matchResult.group(1)
        if oldName[:5] == "UNSET" or oldName in ignoreList:
            continue
        spacedName = oldName.replace("_", " ")
        words = spacedName.split(" ")
        capitalizedWords = [word.capitalize() for word in words]
        newName = " ".join(capitalizedWords)
        enumList.append(BlenderEnumItem(enumPrefix + "_" + oldName, newName, newName))

    return enumList


def parseObjectID():
    data = readFile("z64object.h")
    enumList = parseEnumFile(
        data,
        "ObjectID",
        "OBJECT",
        [
            "GAMEPLAY_KEEP",
            "GAMEPLAY_DANGEON_KEEP",
            "GAMEPLAY_FIELD_KEEP",
            "LINK_BOY",
            "LINK_CHILD",
        ],
        True,
    )
    pythonEnum = createEnum("ootEnumObjectID", enumList)
    writeFile("oot_obj_enum.py", pythonEnum)


def parseSceneID():
    data = readFile("z64scene.h")
    enumList = parseEnumFile(data, "SceneID", "SCENE", [], True)
    pythonEnum = createEnum("ootEnumSceneID", enumList)
    writeFile("oot_scene_enum.py", pythonEnum)
