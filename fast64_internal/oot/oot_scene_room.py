# import bpy
from bpy.types import UILayout
from ..utility import prop_split
from .oot_utility import drawAddButton, drawCollectionOps, drawEnumWithCustom, getSceneObj, getRoomObj
from .oot_cutscene import drawCSListProperty, drawCSAddButtons
from .oot_constants import ootData
from .scene.panel.properties import OOT_SearchMusicSeqEnumOperator
from .room.panel.properties import OOTObjectProperty, OOT_SearchObjectEnumOperator, OOTRoomHeaderProperty


def drawAlternateRoomHeaderProperty(layout, headerProp, objName):
    headerSetup = layout.column()
    # headerSetup.box().label(text = "Alternate Headers")
    headerSetupBox = headerSetup.column()

    headerSetupBox.row().prop(headerProp, "headerMenuTab", expand=True)
    if headerProp.headerMenuTab == "Child Night":
        drawRoomHeaderProperty(headerSetupBox, headerProp.childNightHeader, None, 1, objName)
    elif headerProp.headerMenuTab == "Adult Day":
        drawRoomHeaderProperty(headerSetupBox, headerProp.adultDayHeader, None, 2, objName)
    elif headerProp.headerMenuTab == "Adult Night":
        drawRoomHeaderProperty(headerSetupBox, headerProp.adultNightHeader, None, 3, objName)
    elif headerProp.headerMenuTab == "Cutscene":
        prop_split(headerSetup, headerProp, "currentCutsceneIndex", "Cutscene Index")
        drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), "Room", None, objName)
        index = headerProp.currentCutsceneIndex
        if index - 4 < len(headerProp.cutsceneHeaders):
            drawRoomHeaderProperty(headerSetup, headerProp.cutsceneHeaders[index - 4], None, index, objName)
        else:
            headerSetup.label(text="No cutscene header for this index.", icon="QUESTION")


def drawExitProperty(layout, exitProp, index, headerIndex, objName):
    box = layout.box()
    box.prop(
        exitProp, "expandTab", text="Exit " + str(index + 1), icon="TRIA_DOWN" if exitProp.expandTab else "TRIA_RIGHT"
    )
    if exitProp.expandTab:
        drawCollectionOps(box, index, "Exit", headerIndex, objName)
        drawEnumWithCustom(box, exitProp, "exitIndex", "Exit Index", "")
        if exitProp.exitIndex != "Custom":
            box.label(text='This is unfinished, use "Custom".')
            exitGroup = box.column()
            exitGroup.enabled = False
            drawEnumWithCustom(exitGroup, exitProp, "scene", "Scene", "")
            exitGroup.prop(exitProp, "continueBGM", text="Continue BGM")
            exitGroup.prop(exitProp, "displayTitleCard", text="Display Title Card")
            drawEnumWithCustom(exitGroup, exitProp, "fadeInAnim", "Fade In Animation", "")
            drawEnumWithCustom(exitGroup, exitProp, "fadeOutAnim", "Fade Out Animation", "")


def drawObjectProperty(
    layout: UILayout, objectProp: OOTObjectProperty, headerIndex: int, index: int, objName: str
):
    isLegacy = True if "objectID" in objectProp else False

    if isLegacy:
        objectName = ootData.objectData.ootEnumObjectIDLegacy[objectProp["objectID"]][1]
    elif objectProp.objectKey != "Custom":
        objectName = ootData.objectData.objectsByKey[objectProp.objectKey].name
    else:
        objectName = objectProp.objectIDCustom

    objItemBox = layout.column()
    row = objItemBox.row()
    row.label(text=f"{objectName}")
    buttons = row.row(align=True)
    objSearch = buttons.operator(OOT_SearchObjectEnumOperator.bl_idname, icon="VIEWZOOM", text="Select")
    drawCollectionOps(buttons, index, "Object", headerIndex, objName, compact=True)
    objSearch.objName = objName
    objSearch.headerIndex = headerIndex if headerIndex is not None else 0
    objSearch.index = index

    if objectProp.objectKey == "Custom":
        prop_split(objItemBox, objectProp, "objectIDCustom", "Object ID Custom")


def drawLightGroupProperty(layout, lightGroupProp):

    box = layout.column()
    box.row().prop(lightGroupProp, "menuTab", expand=True)
    if lightGroupProp.menuTab == "Dawn":
        drawLightProperty(box, lightGroupProp.dawn, "Dawn", False, None, None, None)
    if lightGroupProp.menuTab == "Day":
        drawLightProperty(box, lightGroupProp.day, "Day", False, None, None, None)
    if lightGroupProp.menuTab == "Dusk":
        drawLightProperty(box, lightGroupProp.dusk, "Dusk", False, None, None, None)
    if lightGroupProp.menuTab == "Night":
        drawLightProperty(box, lightGroupProp.night, "Night", False, None, None, None)


def drawLightProperty(layout, lightProp, name, showExpandTab, index, sceneHeaderIndex, objName):
    if showExpandTab:
        box = layout.box().column()
        box.prop(lightProp, "expandTab", text=name, icon="TRIA_DOWN" if lightProp.expandTab else "TRIA_RIGHT")
        expandTab = lightProp.expandTab
    else:
        box = layout
        expandTab = True

    if expandTab:
        if index is not None:
            drawCollectionOps(box, index, "Light", sceneHeaderIndex, objName)
        prop_split(box, lightProp, "ambient", "Ambient Color")

        if lightProp.useCustomDiffuse0:
            prop_split(box, lightProp, "diffuse0Custom", "Diffuse 0")
            box.label(text="Make sure light is not part of scene hierarchy.", icon="FILE_PARENT")
        else:
            prop_split(box, lightProp, "diffuse0", "Diffuse 0")
        box.prop(lightProp, "useCustomDiffuse0")

        if lightProp.useCustomDiffuse1:
            prop_split(box, lightProp, "diffuse1Custom", "Diffuse 1")
            box.label(text="Make sure light is not part of scene hierarchy.", icon="FILE_PARENT")
        else:
            prop_split(box, lightProp, "diffuse1", "Diffuse 1")
        box.prop(lightProp, "useCustomDiffuse1")

        prop_split(box, lightProp, "fogColor", "Fog Color")
        prop_split(box, lightProp, "fogNear", "Fog Near")
        prop_split(box, lightProp, "fogFar", "Fog Far")
        prop_split(box, lightProp, "transitionSpeed", "Transition Speed")


def drawSceneTableEntryProperty(layout, sceneTableEntryProp):
    drawEnumWithCustom(layout, sceneTableEntryProp, "drawConfig", "Draw Config", "")


def drawSceneHeaderProperty(layout, sceneProp, dropdownLabel, headerIndex, objName):
    if dropdownLabel is not None:
        layout.prop(
            sceneProp, "expandTab", text=dropdownLabel, icon="TRIA_DOWN" if sceneProp.expandTab else "TRIA_RIGHT"
        )
        if not sceneProp.expandTab:
            return
    if headerIndex is not None and headerIndex > 3:
        drawCollectionOps(layout, headerIndex - 4, "Scene", None, objName)

    if headerIndex is not None and headerIndex > 0 and headerIndex < 4:
        layout.prop(sceneProp, "usePreviousHeader", text="Use Previous Header")
        if sceneProp.usePreviousHeader:
            return

    if headerIndex is None or headerIndex == 0:
        layout.row().prop(sceneProp, "menuTab", expand=True)
        menuTab = sceneProp.menuTab
    else:
        layout.row().prop(sceneProp, "altMenuTab", expand=True)
        menuTab = sceneProp.altMenuTab

    if menuTab == "General":
        general = layout.column()
        general.box().label(text="General")
        drawEnumWithCustom(general, sceneProp, "globalObject", "Global Object", "")
        drawEnumWithCustom(general, sceneProp, "naviCup", "Navi Hints", "")
        if headerIndex is None or headerIndex == 0:
            drawSceneTableEntryProperty(general, sceneProp.sceneTableEntry)
        general.prop(sceneProp, "appendNullEntrance")

        skyboxAndSound = layout.column()
        skyboxAndSound.box().label(text="Skybox And Sound")
        drawEnumWithCustom(skyboxAndSound, sceneProp, "skyboxID", "Skybox", "")
        drawEnumWithCustom(skyboxAndSound, sceneProp, "skyboxCloudiness", "Cloudiness", "")
        drawEnumWithCustom(skyboxAndSound, sceneProp, "musicSeq", "Music Sequence", "")
        musicSearch = skyboxAndSound.operator(OOT_SearchMusicSeqEnumOperator.bl_idname, icon="VIEWZOOM")
        musicSearch.objName = objName
        musicSearch.headerIndex = headerIndex if headerIndex is not None else 0
        drawEnumWithCustom(skyboxAndSound, sceneProp, "nightSeq", "Nighttime SFX", "")
        drawEnumWithCustom(skyboxAndSound, sceneProp, "audioSessionPreset", "Audio Session Preset", "")

        cameraAndWorldMap = layout.column()
        cameraAndWorldMap.box().label(text="Camera And World Map")
        drawEnumWithCustom(cameraAndWorldMap, sceneProp, "mapLocation", "Map Location", "")
        drawEnumWithCustom(cameraAndWorldMap, sceneProp, "cameraMode", "Camera Mode", "")

    elif menuTab == "Lighting":
        lighting = layout.column()
        lighting.box().label(text="Lighting List")
        drawEnumWithCustom(lighting, sceneProp, "skyboxLighting", "Lighting Mode", "")
        if sceneProp.skyboxLighting == "false":  # Time of Day
            drawLightGroupProperty(lighting, sceneProp.timeOfDayLights)
        else:
            for i in range(len(sceneProp.lightList)):
                drawLightProperty(lighting, sceneProp.lightList[i], "Lighting " + str(i), True, i, headerIndex, objName)
            drawAddButton(lighting, len(sceneProp.lightList), "Light", headerIndex, objName)

    elif menuTab == "Cutscene":
        cutscene = layout.column()
        r = cutscene.row()
        r.prop(sceneProp, "writeCutscene", text="Write Cutscene")
        if sceneProp.writeCutscene:
            r.prop(sceneProp, "csWriteType", text="Data")
            if sceneProp.csWriteType == "Custom":
                cutscene.prop(sceneProp, "csWriteCustom")
            elif sceneProp.csWriteType == "Object":
                cutscene.prop(sceneProp, "csWriteObject")
            else:
                # This is the GUI setup / drawing for the properties for the
                # deprecated "Embedded" cutscene type. They have not been removed
                # as doing so would break any existing scenes made with this type
                # of cutscene data.
                cutscene.label(text='Embedded cutscenes are deprecated. Please use "Object" instead.')
                cutscene.prop(sceneProp, "csEndFrame", text="End Frame")
                cutscene.prop(sceneProp, "csWriteTerminator", text="Write Terminator (Code Execution)")
                if sceneProp.csWriteTerminator:
                    r = cutscene.row()
                    r.prop(sceneProp, "csTermIdx", text="Index")
                    r.prop(sceneProp, "csTermStart", text="Start Frm")
                    r.prop(sceneProp, "csTermEnd", text="End Frm")
                collectionType = "CSHdr." + str(0 if headerIndex is None else headerIndex)
                for i, p in enumerate(sceneProp.csLists):
                    drawCSListProperty(cutscene, p, i, objName, collectionType)
                drawCSAddButtons(cutscene, objName, collectionType)
        if headerIndex is None or headerIndex == 0:
            cutscene.label(text="Extra cutscenes (not in any header):")
            for i in range(len(sceneProp.extraCutscenes)):
                box = cutscene.box().column()
                drawCollectionOps(box, i, "extraCutscenes", None, objName, True)
                box.prop(sceneProp.extraCutscenes[i], "csObject", text="CS obj")
            if len(sceneProp.extraCutscenes) == 0:
                drawAddButton(cutscene, 0, "extraCutscenes", 0, objName)

    elif menuTab == "Exits":
        exitBox = layout.column()
        exitBox.box().label(text="Exit List")
        for i in range(len(sceneProp.exitList)):
            drawExitProperty(exitBox, sceneProp.exitList[i], i, headerIndex, objName)

        drawAddButton(exitBox, len(sceneProp.exitList), "Exit", headerIndex, objName)


def drawBGImageList(layout: UILayout, roomHeader: OOTRoomHeaderProperty, objName: str):
    box = layout.column()
    box.label(text="BG images do not work currently.", icon="ERROR")
    box.prop(roomHeader, "bgImageTab", text="BG Images", icon="TRIA_DOWN" if roomHeader.bgImageTab else "TRIA_RIGHT")
    if roomHeader.bgImageTab:
        box.label(text="Only one room allowed per scene.", icon="INFO")
        box.label(text="Must be framebuffer sized (320x240).", icon="INFO")
        box.label(text="Must be jpg file with file marker.", icon="INFO")
        box.label(text="Ex. MsPaint compatible, Photoshop not.")
        box.label(text="Can't use files generated in Blender.")
        imageCount = len(roomHeader.bgImageList)
        for i in range(imageCount):
            roomHeader.bgImageList[i].draw(box, i, objName, imageCount > 1)

        drawAddButton(box, len(roomHeader.bgImageList), "BgImage", None, objName)


def drawRoomHeaderProperty(layout: UILayout, roomProp, dropdownLabel, headerIndex, objName):
    from .oot_level import OOT_ManualUpgrade

    if dropdownLabel is not None:
        layout.prop(roomProp, "expandTab", text=dropdownLabel, icon="TRIA_DOWN" if roomProp.expandTab else "TRIA_RIGHT")
        if not roomProp.expandTab:
            return
    if headerIndex is not None and headerIndex > 3:
        drawCollectionOps(layout, headerIndex - 4, "Room", None, objName)

    if headerIndex is not None and headerIndex > 0 and headerIndex < 4:
        layout.prop(roomProp, "usePreviousHeader", text="Use Previous Header")
        if roomProp.usePreviousHeader:
            return

    if headerIndex is None or headerIndex == 0:
        layout.row().prop(roomProp, "menuTab", expand=True)
        menuTab = roomProp.menuTab
    else:
        layout.row().prop(roomProp, "altMenuTab", expand=True)
        menuTab = roomProp.altMenuTab

    if menuTab == "General":
        if headerIndex is None or headerIndex == 0:
            general = layout.column()
            general.box().label(text="General")
            prop_split(general, roomProp, "roomIndex", "Room Index")
            prop_split(general, roomProp, "roomShape", "Room Shape")
            if roomProp.roomShape == "ROOM_SHAPE_TYPE_IMAGE":
                drawBGImageList(general, roomProp, objName)
            if roomProp.roomShape == "ROOM_SHAPE_TYPE_CULLABLE":
                general.label(text="Cull regions are generated automatically.", icon="INFO")
                prop_split(general, roomProp, "defaultCullDistance", "Default Cull (Blender Units)")
        # Behaviour
        behaviourBox = layout.column()
        behaviourBox.box().label(text="Behaviour")
        drawEnumWithCustom(behaviourBox, roomProp, "roomBehaviour", "Room Behaviour", "")
        drawEnumWithCustom(behaviourBox, roomProp, "linkIdleMode", "Link Idle Mode", "")
        behaviourBox.prop(roomProp, "disableWarpSongs", text="Disable Warp Songs")
        behaviourBox.prop(roomProp, "showInvisibleActors", text="Show Invisible Actors")

        # Time
        skyboxAndTime = layout.column()
        skyboxAndTime.box().label(text="Skybox And Time")

        # Skybox
        skyboxAndTime.prop(roomProp, "disableSkybox", text="Disable Skybox")
        skyboxAndTime.prop(roomProp, "disableSunMoon", text="Disable Sun/Moon")
        skyboxAndTime.prop(roomProp, "leaveTimeUnchanged", text="Leave Time Unchanged")
        if not roomProp.leaveTimeUnchanged:
            skyboxAndTime.label(text="Time")
            timeRow = skyboxAndTime.row()
            timeRow.prop(roomProp, "timeHours", text="Hours")
            timeRow.prop(roomProp, "timeMinutes", text="Minutes")
            # prop_split(skyboxAndTime, roomProp, "timeValue", "Time Of Day")
        prop_split(skyboxAndTime, roomProp, "timeSpeed", "Time Speed")

        # Echo
        prop_split(skyboxAndTime, roomProp, "echo", "Echo")

        # Wind
        windBox = layout.column()
        windBox.box().label(text="Wind")
        windBox.prop(roomProp, "setWind", text="Set Wind")
        if roomProp.setWind:
            windBoxRow = windBox.row()
            windBoxRow.prop(roomProp, "windVector", text="")
            windBox.prop(roomProp, "windStrength", text="Strength")
            # prop_split(windBox, roomProp, "windVector", "Wind Vector")

    elif menuTab == "Objects":
        upgradeLayout = layout.column()
        objBox = layout.column()
        objBox.box().label(text="Objects")

        if len(roomProp.objectList) > 16:
            objBox.label(text="You are over the 16 object limit.", icon="ERROR")
            objBox.label(text="You must allocate more memory in code.")

        isLegacy = False
        for i, objProp in enumerate(roomProp.objectList):
            drawObjectProperty(objBox, objProp, headerIndex, i, objName)

            if "objectID" in objProp:
                isLegacy = True

        if isLegacy:
            upgradeLayout.label(text="Legacy data has not been upgraded!")
            upgradeLayout.operator(OOT_ManualUpgrade.bl_idname, text="Upgrade Data Now!")
        objBox.enabled = False if isLegacy else True

        drawAddButton(objBox, len(roomProp.objectList), "Object", headerIndex, objName)


def drawAlternateSceneHeaderProperty(layout, headerProp, objName):
    headerSetup = layout.column()
    # headerSetup.box().label(text = "Alternate Headers")
    headerSetupBox = headerSetup.column()

    headerSetupBox.row().prop(headerProp, "headerMenuTab", expand=True)
    if headerProp.headerMenuTab == "Child Night":
        drawSceneHeaderProperty(headerSetupBox, headerProp.childNightHeader, None, 1, objName)
    elif headerProp.headerMenuTab == "Adult Day":
        drawSceneHeaderProperty(headerSetupBox, headerProp.adultDayHeader, None, 2, objName)
    elif headerProp.headerMenuTab == "Adult Night":
        drawSceneHeaderProperty(headerSetupBox, headerProp.adultNightHeader, None, 3, objName)
    elif headerProp.headerMenuTab == "Cutscene":
        prop_split(headerSetup, headerProp, "currentCutsceneIndex", "Cutscene Index")
        drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), "Scene", None, objName)
        index = headerProp.currentCutsceneIndex
        if index - 4 < len(headerProp.cutsceneHeaders):
            drawSceneHeaderProperty(headerSetup, headerProp.cutsceneHeaders[index - 4], None, index, objName)
        else:
            headerSetup.label(text="No cutscene header for this index.", icon="QUESTION")


def drawParentSceneRoom(box, obj):
    sceneObj = getSceneObj(obj)
    roomObj = getRoomObj(obj)

    # box = layout.box().column()
    box.box().column().label(text="Parent Scene/Room Settings")
    box.row().prop(obj, "ootObjectMenu", expand=True)

    if obj.ootObjectMenu == "Scene":
        if sceneObj is not None:
            drawSceneHeaderProperty(box, sceneObj.ootSceneHeader, None, None, sceneObj.name)
            if sceneObj.ootSceneHeader.menuTab == "Alternate":
                drawAlternateSceneHeaderProperty(box, sceneObj.ootAlternateSceneHeaders, sceneObj.name)
        else:
            box.label(text="This object is not part of any Scene hierarchy.", icon="OUTLINER")

    elif obj.ootObjectMenu == "Room":
        if roomObj is not None:
            drawRoomHeaderProperty(box, roomObj.ootRoomHeader, None, None, roomObj.name)
            if roomObj.ootRoomHeader.menuTab == "Alternate":
                drawAlternateRoomHeaderProperty(box, roomObj.ootAlternateRoomHeaders, roomObj.name)
        else:
            box.label(text="This object is not part of any Room hierarchy.", icon="OUTLINER")
