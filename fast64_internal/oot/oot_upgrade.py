from bpy.types import Object, CollectionProperty
from .data import OoT_ObjectData
from .cutscene.motion.constants import ootEnumCSMotionCamMode


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


def upgradeCutsceneMotion(csMotionObj: Object):
    objName = csMotionObj.name

    if csMotionObj.type == "EMPTY":
        csMotionProp = csMotionObj.ootCSMotionProperty

        if "zc_alist" in csMotionObj and ("Preview." in objName or "ActionList." in objName):
            legacyData = csMotionObj["zc_alist"]

            if "actor_id" in legacyData:
                csMotionProp.actorCueListProp.actor_id = legacyData["actor_id"]
                del legacyData["actor_id"]

            del csMotionObj["zc_alist"]

        if "zc_apoint" in csMotionObj and "Point." in objName:
            legacyData = csMotionObj["zc_apoint"]

            if "start_frame" in legacyData:
                csMotionProp.actorCueProp.start_frame = legacyData["start_frame"]
                del legacyData["start_frame"]

            if "action_id" in legacyData:
                csMotionProp.actorCueProp.action_id = legacyData["action_id"]
                del legacyData["action_id"]

            del csMotionObj["zc_apoint"]

    if csMotionObj.type == "ARMATURE":
        camShotProp = csMotionObj.data.ootCamShotProp

        if "start_frame" in csMotionObj.data:
            camShotProp.start_frame = csMotionObj.data["start_frame"]
            del csMotionObj.data["start_frame"]
        
        if "cam_mode" in csMotionObj.data:
            camShotProp.cam_mode = ootEnumCSMotionCamMode[csMotionObj.data["cam_mode"]][0]
            del csMotionObj.data["cam_mode"]

        for bone in csMotionObj.data.bones:
            camShotPointProp = bone.ootCamShotPointProp

            if "frames" in bone:
                camShotPointProp.frames = bone["frames"]
                del bone["frames"]
                
            if "fov" in bone:
                camShotPointProp.fov = bone["fov"]
                del bone["fov"]
                
            if "camroll" in bone:
                camShotPointProp.camroll = bone["camroll"]
                del bone["camroll"]
