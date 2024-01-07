from bpy.types import Object, PropertyGroup, UILayout
from bpy.utils import register_class, unregister_class
from bpy.props import EnumProperty, StringProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty
from ...utility import prop_split, label_split
from ..oot_constants import ootData, ootEnumCamTransition
from ..oot_upgrade import upgradeActors
from ..scene.properties import OOTAlternateSceneHeaderProperty
from ..room.properties import OOTAlternateRoomHeaderProperty
from .operators import (
    OOT_SearchActorIDEnumOperator,
    OOT_SearchChestContentEnumOperator,
    OOT_SearchNaviMsgIDEnumOperator,
)

from ..oot_utility import (
    getRoomObj,
    getEnumName,
    drawAddButton,
    drawCollectionOps,
    drawEnumWithCustom,
    getEvalParams,
    getEvalParamsInt,
    getShiftFromMask,
    getFormattedParams,
)

ootEnumSceneSetupPreset = [
    ("Custom", "Custom", "Custom"),
    ("All Scene Setups", "All Scene Setups", "All Scene Setups"),
    ("All Non-Cutscene Scene Setups", "All Non-Cutscene Scene Setups", "All Non-Cutscene Scene Setups"),
]


def getObjName(actorKey: str, paramType: str, paramSubType: str, paramIndex: int):
    flagTypeToObjName = {"Chest": "chestFlag", "Collectible": "collectibleFlag", "Switch": "switchFlag"}
    paramTypeToObjName = {
        "Type": "type",
        "Property": "props",
        "Bool": "bool",
        "Enum": "enum",
        "ChestContent": "chestContent",
        "Collectible": "collectibleDrop",
        "Message": "naviMsg",
    }
    suffix = paramTypeToObjName[paramType] if paramType != "Flag" else flagTypeToObjName[paramSubType]
    return f"{actorKey}.{suffix}{paramIndex}"  # e.g.: ``en_test.props1``


def initOOTActorProperties():
    """This function is used to edit the OOTActorProperty class"""

    propAnnotations = getattr(OOTActorProperty, "__annotations__", None)
    if propAnnotations is None:
        OOTActorProperty.__annotations__ = propAnnotations = {}

    paramTypeToEnumItems = {
        "ChestContent": ootData.actorData.ootEnumChestContent,
        "Collectible": ootData.actorData.ootEnumCollectibleItems,
        "Message": ootData.actorData.ootEnumNaviMessageData,
    }

    for actor in ootData.actorData.actorList:
        for param in actor.params:
            objName = getObjName(actor.key, param.type, param.subType, param.index)
            enumItems = None

            if len(param.items) > 0:
                enumItems = [(f"0x{val:04X}", name, f"0x{val:04X}") for val, name in param.items]
            elif param.type in ["ChestContent", "Collectible", "Message"]:
                enumItems = paramTypeToEnumItems[param.type]

            if param.type in ["Property", "Flag"]:
                propAnnotations[objName] = StringProperty(name="", default="0x0")
            elif param.type == "Bool":
                propAnnotations[objName] = BoolProperty(name="", default=False)
            elif param.type in ["Type", "Enum", "ChestContent", "Collectible", "Message"] and enumItems is not None:
                propAnnotations[objName] = EnumProperty(name="", items=enumItems, default=enumItems[0][0])


class OOTActorHeaderItemProperty(PropertyGroup):
    headerIndex: IntProperty(name="Scene Setup", min=4, default=4)
    expandTab: BoolProperty(name="Expand Tab")

    def draw_props(
        self,
        layout: UILayout,
        propUser: str,
        index: int,
        altProp: OOTAlternateSceneHeaderProperty | OOTAlternateRoomHeaderProperty,
        objName: str,
    ):
        box = layout.column()
        row = box.row()
        row.prop(self, "headerIndex", text="")
        drawCollectionOps(row.row(align=True), index, propUser, None, objName, compact=True)
        if altProp is not None and self.headerIndex >= len(altProp.cutsceneHeaders) + 4:
            box.label(text="Above header does not exist.", icon="QUESTION")


class OOTActorHeaderProperty(PropertyGroup):
    sceneSetupPreset: EnumProperty(name="Scene Setup Preset", items=ootEnumSceneSetupPreset, default="All Scene Setups")
    childDayHeader: BoolProperty(name="Child Day Header", default=True)
    childNightHeader: BoolProperty(name="Child Night Header", default=True)
    adultDayHeader: BoolProperty(name="Adult Day Header", default=True)
    adultNightHeader: BoolProperty(name="Adult Night Header", default=True)
    cutsceneHeaders: CollectionProperty(type=OOTActorHeaderItemProperty)

    def checkHeader(self, index: int) -> bool:
        if index == 0:
            return self.childDayHeader
        elif index == 1:
            return self.childNightHeader
        elif index == 2:
            return self.adultDayHeader
        elif index == 3:
            return self.adultNightHeader
        else:
            return index in [value.headerIndex for value in self.cutsceneHeaders]

    def draw_props(
        self,
        layout: UILayout,
        propUser: str,
        altProp: OOTAlternateSceneHeaderProperty | OOTAlternateRoomHeaderProperty,
        objName: str,
    ):
        headerSetup = layout.column()
        # headerSetup.box().label(text = "Alternate Headers")
        prop_split(headerSetup, self, "sceneSetupPreset", "Scene Setup Preset")
        if self.sceneSetupPreset == "Custom":
            headerSetupBox = headerSetup.column()
            headerSetupBox.prop(self, "childDayHeader", text="Child Day")
            prevHeaderName = "childDayHeader"
            childNightRow = headerSetupBox.row()
            if altProp is None or altProp.childNightHeader.usePreviousHeader:
                # Draw previous header checkbox (so get previous state), but labeled
                # as current one and grayed out
                childNightRow.prop(self, prevHeaderName, text="Child Night")
                childNightRow.enabled = False
            else:
                childNightRow.prop(self, "childNightHeader", text="Child Night")
                prevHeaderName = "childNightHeader"
            adultDayRow = headerSetupBox.row()
            if altProp is None or altProp.adultDayHeader.usePreviousHeader:
                adultDayRow.prop(self, prevHeaderName, text="Adult Day")
                adultDayRow.enabled = False
            else:
                adultDayRow.prop(self, "adultDayHeader", text="Adult Day")
                prevHeaderName = "adultDayHeader"
            adultNightRow = headerSetupBox.row()
            if altProp is None or altProp.adultNightHeader.usePreviousHeader:
                adultNightRow.prop(self, prevHeaderName, text="Adult Night")
                adultNightRow.enabled = False
            else:
                adultNightRow.prop(self, "adultNightHeader", text="Adult Night")

            headerSetupBox.row().label(text="Cutscene headers to include this actor in:")
            for i in range(len(self.cutsceneHeaders)):
                headerItemProps: OOTActorHeaderItemProperty = self.cutsceneHeaders[i]
                headerItemProps.draw_props(headerSetup, propUser, i, altProp, objName)
            drawAddButton(headerSetup, len(self.cutsceneHeaders), propUser, None, objName)


class OOTActorProperty(PropertyGroup):
    actorID: EnumProperty(name="Actor", items=ootData.actorData.ootEnumActorID, default="ACTOR_PLAYER")
    actorIDCustom: StringProperty(name="Actor ID", default="ACTOR_PLAYER")

    # used for actors with the id "Custom"
    actorParam: StringProperty(name="Actor Parameter", default="0x0000")
    rotOverride: BoolProperty(name="Override Rotation", default=False)
    rotOverrideX: StringProperty(name="Rot X", default="0x0000")
    rotOverrideY: StringProperty(name="Rot Y", default="0x0000")
    rotOverrideZ: StringProperty(name="Rot Z", default="0x0000")

    # non-custom actors
    params: StringProperty(
        name="Actor Parameter",
        default="0x0000",
        get=lambda self: self.getParamValue("Params"),
        set=lambda self, value: self.setParamValue(value, "Params"),
    )

    rotX: StringProperty(
        name="Rot X",
        default="0",
        get=lambda self: self.getParamValue("XRot"),
        set=lambda self, value: self.setParamValue(value, "XRot"),
    )
    rotY: StringProperty(
        name="Rot Y",
        default="0",
        get=lambda self: self.getParamValue("YRot"),
        set=lambda self, value: self.setParamValue(value, "YRot"),
    )
    rotZ: StringProperty(
        name="Rot Z",
        default="0",
        get=lambda self: self.getParamValue("ZRot"),
        set=lambda self, value: self.setParamValue(value, "ZRot"),
    )

    # internal usage only
    isRotXUsedByActor: BoolProperty(name="", default=False, get=lambda self: self.isRotationUsedByActor("XRot"))
    isRotYUsedByActor: BoolProperty(name="", default=False, get=lambda self: self.isRotationUsedByActor("YRot"))
    isRotZUsedByActor: BoolProperty(name="", default=False, get=lambda self: self.isRotationUsedByActor("ZRot"))

    headerSettings: PointerProperty(type=OOTActorHeaderProperty)
    evalParams: BoolProperty(name="Eval Params", default=False)

    @staticmethod
    def upgrade_object(obj: Object):
        print(f"Processing '{obj.name}'...")
        upgradeActors(obj)

    def isRotationUsedByActor(self, target: str):
        actor = ootData.actorData.actorsByID[self.actorID]
        curType = None
        for param in actor.params:
            if param.type == "Type":
                objName = getObjName(actor.key, param.type, param.subType, param.index)
                curType = getEvalParamsInt(getattr(self, objName))

            if curType is not None and curType in param.tiedTypes or len(param.tiedTypes) == 0:
                if param.target != "Params" and target == param.target:
                    return True
        return False

    def isValueInRange(self, value: int, min: int, max: int):
        if min is not None and max is not None:
            return value >= min and value <= max
        return True

    def setParamValue(self, value: str | bool, target: str):
        actor = ootData.actorData.actorsByID[self.actorID]
        value = getEvalParamsInt(value)
        foundType = None
        for param in actor.params:
            if target == param.target:
                shift = getShiftFromMask(param.mask)
                if param.type != "Type":
                    shiftedVal = (value & param.mask) >> shift
                else:
                    shiftedVal = value & param.mask
                    foundType = shiftedVal

                if "Rot" in target:
                    foundType = getEvalParamsInt(getattr(self, getObjName(actor.key, "Type", None, 1)))

                isInRange = self.isValueInRange(shiftedVal, param.valueRange[0], param.valueRange[1])
                if isInRange and (foundType is not None and foundType in param.tiedTypes or len(param.tiedTypes) == 0):
                    objName = getObjName(actor.key, param.type, param.subType, param.index)
                    if param.type == "ChestContent":
                        val = ootData.actorData.chestItemByValue[shiftedVal].key
                    elif param.type == "Collectible":
                        val = ootData.actorData.collectibleItemsByValue[shiftedVal].key
                    elif param.type == "Message":
                        val = ootData.actorData.messageItemsByValue[shiftedVal].key
                    elif param.type == "Bool":
                        val = bool(shiftedVal)
                    else:
                        val = f"0x{shiftedVal:04X}"
                    setattr(self, objName, val)

    def getParamValue(self, target: str):
        actor = ootData.actorData.actorsByID[self.actorID]
        paramList = []
        typeValue = None
        for param in actor.params:
            if target == param.target:
                paramValue = None
                curPropValue = getattr(self, getObjName(actor.key, param.type, param.subType, param.index))

                if param.type not in ["Type", "ChestContent", "Collectible", "Message"]:
                    paramValue = getEvalParamsInt(
                        curPropValue if not param.type == "Bool" else "1" if curPropValue else "0"
                    )
                else:
                    if param.type == "Type":
                        typeValue = getEvalParamsInt(curPropValue)
                    else:
                        paramValue = 0
                        if param.type == "ChestContent":
                            paramValue = ootData.actorData.chestItemByKey[curPropValue].value
                        elif param.type == "Collectible":
                            paramValue = ootData.actorData.collectibleItemsByKey[curPropValue].value
                        elif param.type == "Message":
                            paramValue = ootData.actorData.messageItemsByKey[curPropValue].value

                if "Rot" in target:
                    typeValue = getEvalParamsInt(getattr(self, getObjName(actor.key, "Type", None, 1)))

                if typeValue is not None and typeValue in param.tiedTypes or len(param.tiedTypes) == 0:
                    val = ((paramValue if paramValue is not None else -1) & param.mask) >> getShiftFromMask(param.mask)
                    isInRange = self.isValueInRange(val, param.valueRange[0], param.valueRange[1])
                    if isInRange and param.type != "Type" and paramValue is not None:
                        value = getFormattedParams(param.mask, paramValue, param.type == "Bool")
                        if value is not None:
                            paramList.append(value)

        if len(paramList) > 0:
            paramString = " | ".join(val for val in paramList)
        else:
            paramString = "0x0"

        if "Rot" in target:
            typeValue = None

        evalTypeValue = typeValue if typeValue is not None else 0
        evalParamValue = getEvalParamsInt(paramString)

        if evalTypeValue and evalParamValue and typeValue is not None:
            paramString = f"(0x{typeValue:04X} | ({paramString}))"
        elif evalTypeValue and not evalParamValue and typeValue is not None:
            paramString = f"0x{typeValue:04X}"
        elif not evalTypeValue and evalParamValue:
            paramString = f"({paramString})"
        else:
            paramString = "0x0"

        return paramString if not self.evalParams else getEvalParams(paramString)

    def draw_params(self, layout: UILayout, objName: str):
        actor = ootData.actorData.actorsByID[self.actorID]
        curType = None
        for param in actor.params:
            propName = getObjName(actor.key, param.type, param.subType, param.index)

            if param.type == "Type":
                curType = getEvalParamsInt(getattr(self, propName))

            if curType is not None and curType in param.tiedTypes or param.type == "Type" or len(param.tiedTypes) == 0:
                searchOp = itemName = None
                labelName = ""
                if param.type == "ChestContent":
                    searchOp = layout.operator(OOT_SearchChestContentEnumOperator.bl_idname)
                    labelName = "Chest Content"
                    itemName = ootData.actorData.chestItemByKey[getattr(self, propName)].name
                elif param.type == "Message":
                    searchOp = layout.operator(OOT_SearchNaviMsgIDEnumOperator.bl_idname)
                    labelName = "Navi Message ID"
                    itemName = ootData.actorData.messageItemsByKey[getattr(self, propName)].name

                if param.type in ["ChestContent", "Message"] and searchOp is not None and itemName is not None:
                    searchOp.objName = objName
                    searchOp.propName = propName
                    split = layout.split(factor=0.5)
                    split.label(text=labelName)
                    split.label(text=itemName)
                else:
                    prop_split(layout, self, propName, param.name)

    def draw_props(self, layout: UILayout, altRoomProp: OOTAlternateRoomHeaderProperty, objName: str):
        actorIDBox = layout.column()
        searchOp = actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon="VIEWZOOM")
        searchOp.actorUser = "Actor"
        searchOp.objName = objName

        split = actorIDBox.split(factor=0.5)

        if self.actorID == "None":
            actorIDBox.box().label(text="This Actor was deleted from the XML file.")
            return

        split.label(text="Actor ID")
        split.label(text=getEnumName(ootData.actorData.ootEnumActorID, self.actorID))

        if self.actorID != "Custom":
            self.draw_params(actorIDBox, objName)
        else:
            prop_split(actorIDBox, self, "actorIDCustom", "")

        paramBox = actorIDBox.box()
        paramBox.label(text="Actor Parameter")

        if self.actorID != "Custom":
            paramBox.prop(self, "evalParams")
            paramBox.prop(self, "params", text="")
        else:
            paramBox.prop(self, "actorParam", text="")

        rotationsUsedByActor = []
        if self.rotOverride:
            rotationsUsedByActor = ["X", "Y", "Z"]
        elif self.actorID != "Custom":
            if self.isRotXUsedByActor:
                rotationsUsedByActor.append("X")
            if self.isRotYUsedByActor:
                rotationsUsedByActor.append("Y")
            if self.isRotZUsedByActor:
                rotationsUsedByActor.append("Z")

        if self.actorID == "Custom":
            paramBox.prop(self, "rotOverride", text="Override Rotation (ignore Blender rot)")

        for rot in rotationsUsedByActor:
            override = ""
            if self.actorID == "Custom":
                override = "Override"
            prop_split(paramBox, self, f"rot{override}{rot}", f"Rot {rot}")

        headerProp: OOTActorHeaderProperty = self.headerSettings
        headerProp.draw_props(actorIDBox, "Actor", altRoomProp, objName)


class OOTTransitionActorProperty(PropertyGroup):
    fromRoom: PointerProperty(type=Object, poll=lambda self, object: self.isRoomEmptyObject(object))
    toRoom: PointerProperty(type=Object, poll=lambda self, object: self.isRoomEmptyObject(object))
    cameraTransitionFront: EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionFrontCustom: StringProperty(default="0x00")
    cameraTransitionBack: EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionBackCustom: StringProperty(default="0x00")
    isRoomTransition: BoolProperty(name="Is Room Transition", default=True)

    actor: PointerProperty(type=OOTActorProperty)

    def isRoomEmptyObject(self, obj: Object):
        return obj.type == "EMPTY" and obj.ootEmptyType == "Room"

    def draw_props(
        self, layout: UILayout, altSceneProp: OOTAlternateSceneHeaderProperty, roomObj: Object, objName: str
    ):
        actorIDBox = layout.column()
        searchOp = actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon="VIEWZOOM")
        searchOp.actorUser = "Transition Actor"
        searchOp.objName = objName

        split = actorIDBox.split(factor=0.5)
        split.label(text="Actor ID")
        split.label(text=getEnumName(ootData.actorData.ootEnumActorID, self.actor.actorID))

        if self.actor.actorID == "Custom":
            prop_split(actorIDBox, self.actor, "actorIDCustom", "")
        else:
            self.actor.draw_params(actorIDBox, objName)

        paramBox = actorIDBox.box()
        paramBox.label(text="Actor Parameter")
        if self.actor.actorID != "Custom":
            paramBox.prop(self.actor, "evalParams")
            paramBox.prop(self.actor, "params", text="")
        else:
            paramBox.prop(self.actor, "actorParam", text="")

        if roomObj is None:
            actorIDBox.label(text="This must be part of a Room empty's hierarchy.", icon="OUTLINER")
        else:
            actorIDBox.prop(self, "isRoomTransition")
            if self.isRoomTransition:
                prop_split(actorIDBox, self, "fromRoom", "Room To Transition From")
                prop_split(actorIDBox, self, "toRoom", "Room To Transition To")
                if self.fromRoom == self.toRoom:
                    actorIDBox.label(text="Warning: You selected the same room!", icon="ERROR")
        actorIDBox.label(text='Y+ side of door faces toward the "from" room.', icon="ORIENTATION_NORMAL")
        drawEnumWithCustom(actorIDBox, self, "cameraTransitionFront", "Camera Transition Front", "")
        drawEnumWithCustom(actorIDBox, self, "cameraTransitionBack", "Camera Transition Back", "")

        headerProps: OOTActorHeaderProperty = self.actor.headerSettings
        headerProps.draw_props(actorIDBox, "Transition Actor", altSceneProp, objName)


class OOTEntranceProperty(PropertyGroup):
    # This is also used in entrance list.
    spawnIndex: IntProperty(min=0)
    customActor: BoolProperty(name="Use Custom Actor")
    actor: PointerProperty(type=OOTActorProperty)

    tiedRoom: PointerProperty(
        type=Object,
        poll=lambda self, object: self.isRoomEmptyObject(object),
        description="Used to set the room index",
    )

    def isRoomEmptyObject(self, obj: Object):
        return obj.type == "EMPTY" and obj.ootEmptyType == "Room"

    def draw_props(self, layout: UILayout, obj: Object, altSceneProp: OOTAlternateSceneHeaderProperty, objName: str):
        box = layout.column()
        roomObj = getRoomObj(obj)
        if roomObj is None:
            box.label(text="This must be part of a Room empty's hierarchy.", icon="OUTLINER")

        entranceProp = obj.ootEntranceProperty
        prop_split(box, entranceProp, "tiedRoom", "Room")
        prop_split(box, entranceProp, "spawnIndex", "Spawn Index")

        box.prop(entranceProp, "customActor")
        if entranceProp.customActor:
            prop_split(box, entranceProp.actor, "actorIDCustom", "Actor ID Custom")

        if not self.customActor:
            self.actor.draw_params(box, objName)

        paramBox = box.box()
        paramBox.label(text="Actor Parameter")
        if not self.customActor:
            paramBox.prop(self.actor, "evalParams")
            paramBox.prop(self.actor, "params", text="")
        else:
            paramBox.prop(self.actor, "actorParam", text="")

        headerProps: OOTActorHeaderProperty = entranceProp.actor.headerSettings
        headerProps.draw_props(box, "Entrance", altSceneProp, objName)


classes = (
    OOTActorHeaderItemProperty,
    OOTActorHeaderProperty,
    OOTActorProperty,
    OOTTransitionActorProperty,
    OOTEntranceProperty,
)


def actor_props_register():
    for cls in classes:
        register_class(cls)

    Object.ootActorProperty = PointerProperty(type=OOTActorProperty)
    Object.ootTransitionActorProperty = PointerProperty(type=OOTTransitionActorProperty)
    Object.ootEntranceProperty = PointerProperty(type=OOTEntranceProperty)


def actor_props_unregister():
    del Object.ootActorProperty
    del Object.ootTransitionActorProperty
    del Object.ootEntranceProperty

    for cls in reversed(classes):
        unregister_class(cls)
