from .....utility import CData
from ....oot_level_classes import OOTRoom
from ...data import indent


def convertObjectList(outRoom: OOTRoom, layerIndex: int):
    """Returns the object list of the current header"""
    objListData = CData()
    objListLength = len(outRoom.objectIDList)
    objListName = f"s16 {outRoom.getObjectListName(layerIndex)}[{objListLength}]"

    # .h
    objListData.header = f"extern {objListName};\n"

    # .c
    objListData.source = (
        objListName + " = {\n" + ",\n".join([indent + objectID for objectID in outRoom.objectIDList]) + ",\n};\n\n"
    )

    return objListData
