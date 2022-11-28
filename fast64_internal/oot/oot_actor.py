from ..utility import prop_split, label_split
from .actor.panel.properties import OOT_SearchActorIDEnumOperator
from .oot_constants import ootData

from .oot_utility import (
    getRoomObj,
    getEnumName,
    drawAddButton,
    drawCollectionOps,
    drawEnumWithCustom,
)


def drawActorHeaderProperty(layout, headerProp, propUser, altProp, objName):
    headerSetup = layout.column()
    # headerSetup.box().label(text = "Alternate Headers")
    prop_split(headerSetup, headerProp, "sceneSetupPreset", "Scene Setup Preset")
    if headerProp.sceneSetupPreset == "Custom":
        headerSetupBox = headerSetup.column()
        headerSetupBox.prop(headerProp, "childDayHeader", text="Child Day")
        prevHeaderName = "childDayHeader"
        childNightRow = headerSetupBox.row()
        if altProp is None or altProp.childNightHeader.usePreviousHeader:
            # Draw previous header checkbox (so get previous state), but labeled
            # as current one and grayed out
            childNightRow.prop(headerProp, prevHeaderName, text="Child Night")
            childNightRow.enabled = False
        else:
            childNightRow.prop(headerProp, "childNightHeader", text="Child Night")
            prevHeaderName = "childNightHeader"
        adultDayRow = headerSetupBox.row()
        if altProp is None or altProp.adultDayHeader.usePreviousHeader:
            adultDayRow.prop(headerProp, prevHeaderName, text="Adult Day")
            adultDayRow.enabled = False
        else:
            adultDayRow.prop(headerProp, "adultDayHeader", text="Adult Day")
            prevHeaderName = "adultDayHeader"
        adultNightRow = headerSetupBox.row()
        if altProp is None or altProp.adultNightHeader.usePreviousHeader:
            adultNightRow.prop(headerProp, prevHeaderName, text="Adult Night")
            adultNightRow.enabled = False
        else:
            adultNightRow.prop(headerProp, "adultNightHeader", text="Adult Night")

        headerSetupBox.row().label(text="Cutscene headers to include this actor in:")
        for i in range(len(headerProp.cutsceneHeaders)):
            drawActorHeaderItemProperty(headerSetup, propUser, headerProp.cutsceneHeaders[i], i, altProp, objName)
        drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), propUser, None, objName)


def drawActorHeaderItemProperty(layout, propUser, headerItemProp, index, altProp, objName):
    box = layout.column()
    # box.prop(
    #    headerItemProp,
    #    "expandTab",
    #    text="Header " + str(headerItemProp.headerIndex),
    #    icon="TRIA_DOWN" if headerItemProp.expandTab else "TRIA_RIGHT",
    # )

    # if headerItemProp.expandTab:
    row = box.row()
    row.prop(headerItemProp, "headerIndex", text="")
    drawCollectionOps(row.row(align=True), index, propUser, None, objName, compact=True)
    if altProp is not None and headerItemProp.headerIndex >= len(altProp.cutsceneHeaders) + 4:
        box.label(text="Above header does not exist.", icon="QUESTION")


def drawActorProperty(layout, actorProp, altRoomProp, objName):
    # prop_split(layout, actorProp, 'actorID', 'Actor')
    actorIDBox = layout.column()
    # actorIDBox.box().label(text = "Settings")
    searchOp = actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon="VIEWZOOM")
    searchOp.actorUser = "Actor"
    searchOp.objName = objName

    split = actorIDBox.split(factor=0.5)

    if actorProp.actorID == "None":
        actorIDBox.box().label(text="This Actor was deleted from the XML file.")
        return

    split.label(text="Actor ID")
    split.label(text=getEnumName(ootData.actorData.ootEnumActorID, actorProp.actorID))

    if actorProp.actorID == "Custom":
        # actorIDBox.prop(actorProp, 'actorIDCustom', text = 'Actor ID')
        prop_split(actorIDBox, actorProp, "actorIDCustom", "")

    # layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
    prop_split(actorIDBox, actorProp, "actorParam", "Actor Parameter")

    actorIDBox.prop(actorProp, "rotOverride", text="Override Rotation (ignore Blender rot)")
    if actorProp.rotOverride:
        prop_split(actorIDBox, actorProp, "rotOverrideX", "Rot X")
        prop_split(actorIDBox, actorProp, "rotOverrideY", "Rot Y")
        prop_split(actorIDBox, actorProp, "rotOverrideZ", "Rot Z")

    drawActorHeaderProperty(actorIDBox, actorProp.headerSettings, "Actor", altRoomProp, objName)


def drawTransitionActorProperty(layout, transActorProp, altSceneProp, roomObj, objName):
    actorIDBox = layout.column()
    searchOp = actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon="VIEWZOOM")
    searchOp.actorUser = "Transition Actor"
    searchOp.objName = objName

    split = actorIDBox.split(factor=0.5)
    split.label(text="Actor ID")
    split.label(text=getEnumName(ootData.actorData.ootEnumActorID, transActorProp.actor.actorID))

    if transActorProp.actor.actorID == "Custom":
        prop_split(actorIDBox, transActorProp.actor, "actorIDCustom", "")

    # layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
    prop_split(actorIDBox, transActorProp.actor, "actorParam", "Actor Parameter")

    if roomObj is None:
        actorIDBox.label(text="This must be part of a Room empty's hierarchy.", icon="OUTLINER")
    else:
        actorIDBox.prop(transActorProp, "dontTransition")
        if not transActorProp.dontTransition:
            label_split(actorIDBox, "Room To Transition From", str(roomObj.ootRoomHeader.roomIndex))
            prop_split(actorIDBox, transActorProp, "roomIndex", "Room To Transition To")
    actorIDBox.label(text='Y+ side of door faces toward the "from" room.', icon="ORIENTATION_NORMAL")
    drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionFront", "Camera Transition Front", "")
    drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionBack", "Camera Transition Back", "")

    drawActorHeaderProperty(actorIDBox, transActorProp.actor.headerSettings, "Transition Actor", altSceneProp, objName)


def drawEntranceProperty(layout, obj, altSceneProp, objName):
    box = layout.column()
    # box.box().label(text = "Properties")
    roomObj = getRoomObj(obj)
    if roomObj is not None:
        split = box.split(factor=0.5)
        split.label(text="Room Index")
        split.label(text=str(roomObj.ootRoomHeader.roomIndex))
    else:
        box.label(text="This must be part of a Room empty's hierarchy.", icon="OUTLINER")

    entranceProp = obj.ootEntranceProperty
    prop_split(box, entranceProp, "spawnIndex", "Spawn Index")
    prop_split(box, entranceProp.actor, "actorParam", "Actor Param")
    box.prop(entranceProp, "customActor")
    if entranceProp.customActor:
        prop_split(box, entranceProp.actor, "actorIDCustom", "Actor ID Custom")

    drawActorHeaderProperty(box, entranceProp.actor.headerSettings, "Entrance", altSceneProp, objName)
