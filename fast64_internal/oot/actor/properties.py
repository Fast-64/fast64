from bpy.types import Object, PropertyGroup, UILayout
from bpy.utils import register_class, unregister_class
from bpy.props import EnumProperty, StringProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty
from ...utility import PluginError, prop_split, label_split
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


def get_prop_name(actor_key: str, param_type: str, param_subtype: str, param_index: int):
    flag_to_prop_suffix = {"Chest": "chestFlag", "Collectible": "collectibleFlag", "Switch": "switchFlag"}
    param_to_prop_suffix = {
        "Type": "type",
        "Property": "props",
        "Bool": "bool",
        "Enum": "enum",
        "ChestContent": "chestContent",
        "Collectible": "collectibleDrop",
        "Message": "naviMsg",
    }
    suffix = param_to_prop_suffix[param_type] if param_type != "Flag" else flag_to_prop_suffix[param_subtype]
    return f"{actor_key}.{suffix}{param_index}"  # e.g.: ``en_test.props1``


def initOOTActorProperties():
    """This function is used to edit the OOTActorProperty class"""

    prop_annotations = getattr(OOTActorProperty, "__annotations__", None)

    if prop_annotations is None:
        OOTActorProperty.__annotations__ = prop_annotations = {}

    param_type_to_enum_items = {
        "ChestContent": ootData.actorData.ootEnumChestContent,
        "Collectible": ootData.actorData.ootEnumCollectibleItems,
        "Message": ootData.actorData.ootEnumNaviMessageData,
    }

    for actor in ootData.actorData.actorList:
        for param in actor.params:
            prop_name = get_prop_name(actor.key, param.type, param.subType, param.index)
            enum_items = None

            if len(param.items) > 0:
                enum_items = [(f"0x{val:04X}", name, f"0x{val:04X}") for val, name in param.items]
                enum_items.insert(0, ("Custom", "Custom Value", "Custom"))
            elif param.type in {"ChestContent", "Collectible", "Message"}:
                enum_items = param_type_to_enum_items[param.type]

            if param.type in {"Property", "Flag"}:
                prop_annotations[prop_name] = StringProperty(name="", default="0x0")
            elif param.type == "Bool":
                prop_annotations[prop_name] = BoolProperty(name="", default=False)
            elif param.type in {"Type", "Enum", "ChestContent", "Collectible", "Message"} and enum_items is not None:
                prop_annotations[prop_name] = EnumProperty(name="", items=enum_items, default=enum_items[1][0])

            if param.type in {"Type", "Enum", "ChestContent", "Collectible", "Message"}:
                prop_annotations[f"{prop_name}_custom"] = StringProperty(name="", default="0x0")


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
    actor_id: EnumProperty(name="Actor", items=ootData.actorData.ootEnumActorID, default="ACTOR_PLAYER")
    actor_id_custom: StringProperty(name="Actor ID", default="ACTOR_PLAYER")

    # only used for actors with the id "Custom"
    # because of the get/set functions we need a way to input any value
    params_custom: StringProperty(name="Actor Parameter", default="0x0000")
    rot_override: BoolProperty(name="Override Rotation", default=False)
    rot_x_custom: StringProperty(name="Rot X", default="0x0000")
    rot_y_custom: StringProperty(name="Rot Y", default="0x0000")
    rot_z_custom: StringProperty(name="Rot Z", default="0x0000")

    # non-custom actors
    params: StringProperty(
        name="Actor Parameter",
        default="0x0000",
        get=lambda self: self.get_param_value("Params"),
        set=lambda self, value: self.set_param_value(value, "Params"),
    )

    rot_x: StringProperty(
        name="Rot X",
        default="0",
        get=lambda self: self.get_param_value("XRot"),
        set=lambda self, value: self.set_param_value(value, "XRot"),
    )
    rot_y: StringProperty(
        name="Rot Y",
        default="0",
        get=lambda self: self.get_param_value("YRot"),
        set=lambda self, value: self.set_param_value(value, "YRot"),
    )
    rot_z: StringProperty(
        name="Rot Z",
        default="0",
        get=lambda self: self.get_param_value("ZRot"),
        set=lambda self, value: self.set_param_value(value, "ZRot"),
    )

    headerSettings: PointerProperty(type=OOTActorHeaderProperty)
    eval_params: BoolProperty(name="Eval Params", default=False)

    @staticmethod
    def upgrade_object(obj: Object):
        print(f"Processing '{obj.name}'...")
        upgradeActors(obj)

    def is_rotation_used(self, target: str):
        actor = ootData.actorData.actorsByID[self.actor_id]
        selected_type = None

        for param in actor.params:
            if param.type == "Type":
                prop_name = get_prop_name(actor.key, param.type, param.subType, param.index)
                base_val = getattr(self, prop_name)

                if base_val == "Custom":
                    base_val = getattr(self, f"{prop_name}_custom")

                selected_type = getEvalParamsInt(base_val)

            # the first parameter type is always the "Actor Type"
            # because of that we need to make sure the current "Actor Type" value
            # is included in type list of the property as not all properties are used sometimes
            if selected_type is not None and selected_type in param.tiedTypes or len(param.tiedTypes) == 0:
                if param.target != "Params" and target == param.target:
                    return True

        return False

    def is_value_in_range(self, value: int, min: int, max: int):
        if min is not None and max is not None:
            return value >= min and value <= max
        return True

    def set_param_value(self, base_value: str | bool, target: str):
        actor = ootData.actorData.actorsByID[self.actor_id]
        base_value = getEvalParamsInt(base_value)
        found_type = None

        for param in actor.params:
            if target == param.target:
                shift = getShiftFromMask(param.mask)
                if param.type != "Type":
                    value = (base_value & param.mask) >> shift
                else:
                    value = base_value & param.mask

                    if "Rot" in target:
                        found_type = getEvalParamsInt(getattr(self, get_prop_name(actor.key, "Type", None, 1)))
                    else:
                        found_type = value

                is_in_range = self.is_value_in_range(value, param.valueRange[0], param.valueRange[1])
                found_type_in_tied_types = found_type is not None and found_type in param.tiedTypes

                if is_in_range and (found_type_in_tied_types or len(param.tiedTypes) == 0):
                    prop_name = get_prop_name(actor.key, param.type, param.subType, param.index)

                    if param.type == "ChestContent":
                        prop_value = ootData.actorData.chestItemByValue[value].key
                    elif param.type == "Collectible":
                        prop_value = ootData.actorData.collectibleItemsByValue[value].key
                    elif param.type == "Message":
                        prop_value = ootData.actorData.messageItemsByValue[value].key
                    elif param.type == "Bool":
                        prop_value = bool(value)
                    else:
                        prop_value = f"0x{value:04X}"

                    try:
                        setattr(self, prop_name, prop_value)
                    except:
                        if param.type in {"Type", "Enum", "ChestContent", "Collectible", "Message"}:
                            setattr(self, prop_name, "Custom")
                            setattr(self, f"{prop_name}_custom", prop_value)
                            print(
                                f"WARNING: invalid value '{prop_value}' ('{base_value}') for '{prop_name}'. "
                                + "Maybe `ActorList.xml` is missing informations?"
                            )

    def get_param_value(self, target: str):
        actor = ootData.actorData.actorsByID[self.actor_id]
        param_list = []
        type_value = None
        have_custom_value = False

        for param in actor.params:
            if target == param.target:
                param_val = None
                prop_name = get_prop_name(actor.key, param.type, param.subType, param.index)
                cur_prop_value = getattr(self, prop_name)

                if param.type not in {"Type", "Enum", "ChestContent", "Collectible", "Message"}:
                    if param.type == "Bool":
                        value_to_eval = "1" if cur_prop_value else "0"
                    else:
                        value_to_eval = cur_prop_value

                    param_val = getEvalParamsInt(value_to_eval)

                    # treat any invalid value as a custom value
                    if param_val is None:
                        param_list.append(value_to_eval)
                        have_custom_value = True
                        continue
                else:
                    if cur_prop_value == "Custom":
                        cur_prop_value = getattr(self, f"{prop_name}_custom")
                        param_list.append(cur_prop_value)
                        have_custom_value = True
                        continue

                    if param.type == "Type":
                        type_value = getEvalParamsInt(cur_prop_value)
                    else:
                        param_val = 0

                        if param.type == "ChestContent":
                            param_val = ootData.actorData.chestItemByKey[cur_prop_value].value
                        elif param.type == "Collectible":
                            param_val = ootData.actorData.collectibleItemsByKey[cur_prop_value].value
                        elif param.type == "Message":
                            param_val = ootData.actorData.messageItemsByKey[cur_prop_value].value
                        elif param.type == "Enum":
                            param_val = getEvalParamsInt(cur_prop_value)

                if "Rot" in target:
                    type_value = getEvalParamsInt(getattr(self, get_prop_name(actor.key, "Type", None, 1)))

                if type_value is not None and type_value in param.tiedTypes or len(param.tiedTypes) == 0:
                    val = ((param_val if param_val is not None else -1) & param.mask) >> getShiftFromMask(param.mask)
                    is_in_range = self.is_value_in_range(val, param.valueRange[0], param.valueRange[1])

                    if is_in_range and param.type != "Type" and param_val is not None:
                        value = getFormattedParams(param.mask, param_val, param.type == "Bool")

                        if value is not None:
                            param_list.append(value)

        if len(param_list) > 0:
            param_str = " | ".join(val for val in param_list)
        else:
            param_str = "0x0"

        if "Rot" in target:
            type_value = None

        eval_type_value = type_value if type_value is not None else 0

        # don't evaluate the params if there's a custom value
        if not have_custom_value:
            eval_param_value = getEvalParamsInt(param_str)
        else:
            eval_param_value = 0

        if eval_type_value and (eval_param_value != 0 or have_custom_value) and type_value is not None:
            param_str = f"(0x{type_value:04X} | ({param_str}))"
        elif eval_type_value and not (eval_param_value != 0 or have_custom_value) and type_value is not None:
            param_str = f"0x{type_value:04X}"
        elif not eval_type_value and (eval_param_value != 0 or have_custom_value):
            param_str = f"({param_str})"
        else:
            param_str = "0x0"

        if self.eval_params:
            # return `param_str` if the eval failed
            # should only happen if the user inputs invalid numbers (hex or dec)
            # returns the non-evaluated value if the function returned None
            try:
                value = getEvalParams(param_str)
                return value if value is not None else param_str
            except:
                pass

        return param_str

    def draw_params(self, layout: UILayout, obj: Object):
        actor = ootData.actorData.actorsByID[self.actor_id]
        selected_type = None

        for param in actor.params:
            prop_name = get_prop_name(actor.key, param.type, param.subType, param.index)

            if param.type == "Type":
                base_val = getattr(self, prop_name)

                if base_val == "Custom":
                    base_val = getattr(self, f"{prop_name}_custom")

                selected_type = getEvalParamsInt(base_val)

            # the first parameter type is always the "Actor Type"
            # because of that we need to make sure the current "Actor Type" value
            # is included in type list of the property as not all properties are used sometimes
            is_type_in_tied_types = selected_type is not None and selected_type in param.tiedTypes
            if is_type_in_tied_types or param.type == "Type" or len(param.tiedTypes) == 0:
                if param.type in {"ChestContent", "Message"}:
                    key: str = getattr(self, prop_name)

                    if param.type == "ChestContent":
                        search_op = layout.operator(OOT_SearchChestContentEnumOperator.bl_idname)
                        label_name = "Chest Content"
                        item_map = ootData.actorData.chestItemByKey
                    else:
                        search_op = layout.operator(OOT_SearchNaviMsgIDEnumOperator.bl_idname)
                        label_name = "Navi Message ID"
                        item_map = ootData.actorData.messageItemsByKey

                    search_op.obj_name = obj.name
                    search_op.prop_name = prop_name

                    if key != "Custom":
                        label_split(layout, label_name, item_map[key].name)
                    else:
                        prop_split(layout, self, f"{prop_name}_custom", f"{label_name} Custom")
                else:
                    prop_split(layout, self, prop_name, param.name)

                if param.type in {"Type", "Enum", "Collectible"}:
                    if getattr(self, prop_name) == "Custom":
                        prop_split(layout, self, f"{prop_name}_custom", f"{param.name} Custom")

    def draw_props(self, layout: UILayout, altRoomProp: OOTAlternateRoomHeaderProperty, obj: Object):
        actorIDBox = layout.column()
        searchOp = actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon="VIEWZOOM")
        searchOp.actor_user = "Actor"
        searchOp.obj_name = obj.name

        split = actorIDBox.split(factor=0.5)

        if self.actor_id == "None":
            actorIDBox.box().label(text="This Actor was deleted from the XML file.")
            return

        split.label(text="Actor ID")
        split.label(text=getEnumName(ootData.actorData.ootEnumActorID, self.actor_id))

        if self.actor_id != "Custom":
            self.draw_params(actorIDBox, obj)
        else:
            prop_split(actorIDBox, self, "actor_id_custom", "")

        paramBox = actorIDBox.box()
        paramBox.label(text="Actor Parameter")

        if self.actor_id != "Custom":
            paramBox.prop(self, "eval_params")
            paramBox.prop(self, "params", text="")
        else:
            paramBox.prop(self, "params_custom", text="")

        rotations_used = []
        if self.rot_override:
            rotations_used = ["X", "Y", "Z"]
        elif self.actor_id != "Custom":
            if self.is_rotation_used("XRot"):
                rotations_used.append("X")
            if self.is_rotation_used("YRot"):
                rotations_used.append("Y")
            if self.is_rotation_used("ZRot"):
                rotations_used.append("Z")

        if self.actor_id == "Custom":
            paramBox.prop(self, "rot_override", text="Override Rotation (ignore Blender rot)")

        for rot in rotations_used:
            custom = "_custom" if self.actor_id == "Custom" else ""
            prop_split(paramBox, self, f"rot_{rot.lower()}{custom}", f"Rot {rot}")

        headerProp: OOTActorHeaderProperty = self.headerSettings
        headerProp.draw_props(actorIDBox, "Actor", altRoomProp, obj.name)


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
        searchOp.actor_user = "Transition Actor"
        searchOp.obj_name = objName

        split = actorIDBox.split(factor=0.5)
        split.label(text="Actor ID")
        split.label(text=getEnumName(ootData.actorData.ootEnumActorID, self.actor.actor_id))

        if self.actor.actor_id == "Custom":
            prop_split(actorIDBox, self.actor, "actor_id_custom", "")
        else:
            self.actor.draw_params(actorIDBox, roomObj)

        paramBox = actorIDBox.box()
        paramBox.label(text="Actor Parameter")
        if self.actor.actor_id != "Custom":
            paramBox.prop(self.actor, "eval_params")
            paramBox.prop(self.actor, "params", text="")
        else:
            paramBox.prop(self.actor, "params_custom", text="")

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
            prop_split(box, entranceProp.actor, "actor_id_custom", "Actor ID Custom")

        if not self.customActor:
            self.actor.draw_params(box, obj)

        paramBox = box.box()
        paramBox.label(text="Actor Parameter")
        if not self.customActor:
            paramBox.prop(self.actor, "eval_params")
            paramBox.prop(self.actor, "params", text="")
        else:
            paramBox.prop(self.actor, "params_custom", text="")

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
