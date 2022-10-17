from ....utility import CData
from ...oot_level_classes import OOTRoom
from ...oot_utility import indent


def ootObjectListToC(room: OOTRoom, headerIndex: int):
    """Returns the object list of the current header"""
    objListData = CData()
    objListLength = len(room.objectIDList)
    objListName = f"s16 {room.objectListName(headerIndex)}[{objListLength}]"

    # .h
    objListData.header = f"extern {objListName};\n"

    # .c
    objListData.source = (
        objListName + " = {\n" + ",\n".join([indent + objectID for objectID in room.objectIDList]) + ",\n};\n\n"
    )

    return objListData
