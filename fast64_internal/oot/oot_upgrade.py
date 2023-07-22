from bpy.types import Object, CollectionProperty
from .data import OoT_ObjectData


def upgradeObjectList(objList: CollectionProperty, objData: OoT_ObjectData):
    """Transition to the XML object system"""
    for obj in objList:
        # In order to check whether the data in the current blend needs to be updated,
        # we look for the ``objectID`` property, which has been removed in the current version.
        # If we find ``objectID`` it means that it's an old blend and needs be updated.
        # Finally, after the update we remove this property to tell Fast64 the object property is now up-to-date.
        if "objectID" in obj:
            # ``obj["objectID"]`` returns the index inside ``ootEnumObjectIDLegacy``
            # since Blender saves the index of the element of the EnumProperty
            objectID = objData.ootEnumObjectIDLegacy[obj["objectID"]][0]
            if objectID == "Custom":
                obj.objectKey = objectID
            else:
                obj.objectKey = objData.objectsByID[objectID].key

            del obj["objectID"]


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


def upgradeActors(actorObj: Object):
    actorProp = None
    if actorObj.ootEmptyType == "Actor":
        actorProp = actorObj.ootActorProperty
    elif actorObj.ootEmptyType == "Transition Actor":
        actorProp = actorObj.ootTransitionActorProperty.actor
    elif actorObj.ootEmptyType == "Entrance":
        actorProp = actorObj.ootEntranceProperty.actor

    if actorProp is not None:
        isCustom = False
        if actorObj.ootEmptyType == "Entrance":
            isCustom = actorObj.ootEntranceProperty.customActor
        else:
            isCustom = actorProp.actorID == "Custom"

        if not isCustom:
            actorProp.params = actorProp.actorParam
            actorProp.actorParam = "0x0000"

            if actorObj.ootEmptyType == "Actor" and actorProp.rotOverride:
                actorProp.rotX = actorProp.rotOverrideX
                actorProp.rotY = actorProp.rotOverrideY
                actorProp.rotZ = actorProp.rotOverrideZ
                actorProp.rotOverrideX = "0x0000"
                actorProp.rotOverrideY = "0x0000"
                actorProp.rotOverrideZ = "0x0000"
