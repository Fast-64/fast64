def upgradeObjectList(objList, objData):
    """Transition from the old object system to the new one"""
    for obj in objList:
        if obj.objectID == "Custom":
            obj.objectKey = obj.objectID
        else:
            obj.objectKey = objData.objectsByID[obj.objectID].key

def upgradeRoomHeaders(roomObj, objData):
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
