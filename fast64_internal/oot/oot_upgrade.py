from bpy.types import Object, CollectionProperty
from .data.oot_object_data import OoT_ObjectData


def upgradeObjectList(objList: CollectionProperty, objData: OoT_ObjectData):
    """Transition to the XML object system"""
    for obj in objList:
        if obj.objectID == "Custom":
            obj.objectKey = obj.objectID
        else:
            obj.objectKey = objData.objectsByID[obj.objectID].key


def upgradeRoomHeaders(roomObj: Object, objData: OoT_ObjectData):
    """Main upgrade logic for room headers"""
    altHeaders = roomObj.ootAlternateRoomHeaders
    for sceneLayer in [
        roomObj.ootRoomHeader,
        altHeaders.childNightHeader,
        altHeaders.adultDayHeader,
        altHeaders.adultNightHeader,
    ]:
        if sceneLayer is not None:
            upgradeObjectList(sceneLayer.objectList, objData)
    for i in range(len(altHeaders.cutsceneHeaders)):
        upgradeObjectList(altHeaders.cutsceneHeaders[i].objectList, objData)
