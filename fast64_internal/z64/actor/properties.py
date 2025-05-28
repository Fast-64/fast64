import bpy

from bpy.types import Object, PropertyGroup, UILayout, Context
from bpy.utils import register_class, unregister_class
from bpy.props import EnumProperty, StringProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty
from ...utility import PluginError, prop_split, label_split, get_prop_annotations
from ...game_data import game_data
from ..constants import ootEnumCamTransition
from ..upgrade import upgradeActors
from ..scene.properties import Z64_AlternateSceneHeaderProperty
from ..room.properties import Z64_AlternateRoomHeaderProperty
from ..collection_utility import drawAddButton, drawCollectionOps
from .operators import (
    OOT_SearchActorIDEnumOperator,
    OOT_SearchChestContentEnumOperator,
    OOT_SearchNaviMsgIDEnumOperator,
)

from ..utility import (
    getRoomObj,
    getEnumName,
    drawEnumWithCustom,
    is_oot_features,
    get_list_tab_text,
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

enum_actor_menu = [
    ("General", "General", "General"),
    ("Actor Cutscene", "Actor Cutscene", "Actor Cutscene"),
]

enum_half_day = [
    ("Custom", "Custom", "Custom"),
    ("0-Dawn", "Day 0 (Intro) - Dawn", "Day 0 - Dawn"),
    ("0-Night", "Day 0 (Intro) - Night", "Day 0 - Night"),
    ("1-Dawn", "Day 1 - Dawn", "Day 1 - Dawn"),
    ("1-Night", "Day 1 - Night", "Day 1 - Night"),
    ("2-Dawn", "Day 2 - Dawn", "Day 2 - Dawn"),
    ("2-Night", "Day 2 - Night", "Day 2 - Night"),
    ("3-Dawn", "Day 3 - Dawn", "Day 3 - Dawn"),
    ("3-Night", "Day 3 - Night", "Day 3 - Night"),
    ("4-Dawn", "Day 4 (Credits) - Dawn", "Day 4 - Dawn"),
    ("4-Night", "Day 4 (Credits) - Night", "Day 4 - Night"),
]


def get_prop_name(actor_key: str, param_type: str, param_subtype: str, param_index: int, update: bool = True):
    if update:
        game_data.z64.update(bpy.context, None)
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
    return f"{game_data.z64.game.lower()}.{actor_key}.{suffix}{param_index}"  # e.g.: `oot.en_test.props1`


def create_game_props(game: str):
    """This function is used to edit the Z64_ActorProperty class"""

    game_data.z64.update(None, game, True)
    prop_ats = get_prop_annotations(Z64_ActorProperty)

    param_type_to_enum_items = {
        "ChestContent": game_data.z64.actors.ootEnumChestContent,
        "Collectible": game_data.z64.actors.ootEnumCollectibleItems,
        "Message": game_data.z64.actors.ootEnumNaviMessageData,
    }

    for actor in game_data.z64.actors.actorList:
        for param in actor.params:
            prop_name = get_prop_name(actor.key, param.type, param.subType, param.index, update=False)
            enum_items = None

            if len(param.items) > 0:
                enum_items = [(f"0x{val:04X}", name, f"0x{val:04X}") for val, name in param.items]
                enum_items.insert(0, ("Custom", "Custom Value", "Custom"))
            elif param.type in {"ChestContent", "Collectible", "Message"}:
                enum_items = param_type_to_enum_items[param.type]

            if param.type in {"Property", "Flag"}:
                prop_ats[prop_name] = StringProperty(name="", default="0x0")
            elif param.type == "Bool":
                prop_ats[prop_name] = BoolProperty(name="", default=False)
            elif param.type in {"Type", "Enum", "ChestContent", "Collectible", "Message"} and enum_items is not None:
                prop_ats[prop_name] = EnumProperty(name="", items=enum_items, default=enum_items[1][0])

            if param.type in {"Type", "Enum", "ChestContent", "Collectible", "Message"}:
                prop_ats[f"{prop_name}_custom"] = StringProperty(name="", default="0x0")


class Z64_HalfdayItem(PropertyGroup):
    value: EnumProperty(items=enum_half_day, default=1)
    value_custom: StringProperty()

    def draw_props(self, layout: UILayout, owner: Object, index: int):
        layout = layout.column()
        row = layout.row()
        row.prop(self, "value", text="")
        if self.value == "Custom":
            row.prop(self, "value_custom", text="")
        drawCollectionOps(row.row(align=True), index, "Actor Halfday", None, owner.name, compact=True)


# TODO: remove
def update_cutscene_index(self, context: Context):
    if self.headerIndex < game_data.z64.cs_index_start:
        self.headerIndex = game_data.z64.cs_index_start


class Z64_ActorHeaderItemProperty(PropertyGroup):
    headerIndex: IntProperty(name="Scene Setup", min=1, default=1, update=update_cutscene_index)

    def draw_props(
        self,
        layout: UILayout,
        propUser: str,
        index: int,
        altProp: Z64_AlternateSceneHeaderProperty | Z64_AlternateRoomHeaderProperty,
        objName: str,
    ):
        box = layout.column()
        row = box.row()
        row.prop(self, "headerIndex", text="")

        drawCollectionOps(row.row(align=True), index, propUser, None, objName, compact=True)

        if altProp is not None and self.headerIndex >= len(altProp.cutsceneHeaders) + game_data.z64.cs_index_start:
            box.label(text="Above header does not exist.", icon="QUESTION")


class Z64_ActorHeaderProperty(PropertyGroup):
    childDayHeader: BoolProperty(name="Child Day Header", default=True)
    cutsceneHeaders: CollectionProperty(type=Z64_ActorHeaderItemProperty)

    # OoT exclusive
    sceneSetupPreset: EnumProperty(name="Scene Setup Preset", items=ootEnumSceneSetupPreset, default="All Scene Setups")
    childNightHeader: BoolProperty(name="Child Night Header", default=True)
    adultDayHeader: BoolProperty(name="Adult Day Header", default=True)
    adultNightHeader: BoolProperty(name="Adult Night Header", default=True)

    # MM exclusive
    include_in_all_setups: BoolProperty(name="Include in all scene setups")
    expand_tab: BoolProperty(name="Expand Tab")

    def checkHeader(self, index: int) -> bool:
        if index == 0:
            return self.childDayHeader
        elif game_data.z64.is_oot():
            if index == 1:
                return self.childNightHeader
            elif index == 2:
                return self.adultDayHeader
            elif index == 3:
                return self.adultNightHeader

        return index in [value.headerIndex for value in self.cutsceneHeaders]

    def draw_props(
        self,
        layout: UILayout,
        propUser: str,
        altProp: Z64_AlternateSceneHeaderProperty | Z64_AlternateRoomHeaderProperty,
        objName: str,
    ):
        headerSetup = layout.column()

        if game_data.z64.is_oot():
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
                    headerItemProps: Z64_ActorHeaderItemProperty = self.cutsceneHeaders[i]
                    headerItemProps.draw_props(headerSetup, propUser, i, altProp, objName)
                drawAddButton(headerSetup, len(self.cutsceneHeaders), propUser, None, objName)
        else:
            header_settings_box = headerSetup.column().box()

            header_settings_box.label(text="Header Settings")
            header_settings_box.prop(self, "include_in_all_setups")

            if not self.include_in_all_setups:
                header_settings_box.prop(self, "childDayHeader", text="Default Header")

                cs_header_box = header_settings_box.box()
                cs_header_box.row().prop(
                    self,
                    "expand_tab",
                    text="Cutscene Headers",
                    icon="TRIA_DOWN" if self.expand_tab else "TRIA_RIGHT",
                )

                if self.expand_tab:
                    for i in range(len(self.cutsceneHeaders)):
                        headerItemProps: Z64_ActorHeaderItemProperty = self.cutsceneHeaders[i]
                        headerItemProps.draw_props(cs_header_box, propUser, i, altProp, objName)

                    drawAddButton(cs_header_box, len(self.cutsceneHeaders), propUser, None, objName)


class Z64_ActorProperty(PropertyGroup):
    actor_id: EnumProperty(name="Actor", items=lambda self, context: game_data.z64.get_enum("actor_id"), default=1)
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

    headerSettings: PointerProperty(type=Z64_ActorHeaderProperty)
    eval_params: BoolProperty(name="Eval Params", default=False)
    menu_tab: EnumProperty(items=enum_actor_menu)
    halfday_show_entries: BoolProperty(default=True)
    halfday_all: BoolProperty(default=True)
    halfday_all_dawns: BoolProperty(default=False)
    halfday_all_nights: BoolProperty(default=False)
    halfday_bits: CollectionProperty(type=Z64_HalfdayItem)
    use_global_actor_cs: BoolProperty(name="Use Global Actor Cutscene", default=False)
    actor_cs_index: IntProperty(min=0, max=127, default=127)

    @staticmethod
    def upgrade_object(obj: Object):
        if game_data.z64.is_oot():
            print(f"Processing '{obj.name}'...")
            upgradeActors(obj)

    def is_rotation_used(self, target: str):
        game_data.z64.update(bpy.context, None)
        actor = game_data.z64.actors.actorsByID[self.actor_id]
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
        game_data.z64.update(bpy.context, None)
        actor = game_data.z64.actors.actorsByID[self.actor_id]
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
                        attr = getattr(self, get_prop_name(actor.key, "Type", None, 1), None)
                        found_type = getEvalParamsInt(attr) if attr is not None else None
                    else:
                        found_type = value
                is_in_range = self.is_value_in_range(value, param.valueRange[0], param.valueRange[1])
                found_type_in_tied_types = found_type is not None and found_type in param.tiedTypes
                if is_in_range and (found_type_in_tied_types or len(param.tiedTypes) == 0):
                    prop_name = get_prop_name(actor.key, param.type, param.subType, param.index)
                    if param.type == "ChestContent":
                        prop_value = game_data.z64.actors.chestItemByValue[value].key
                    elif param.type == "Collectible":
                        prop_value = game_data.z64.actors.collectibleItemsByValue[value].key
                    elif param.type == "Message":
                        prop_value = game_data.z64.actors.messageItemsByValue[value].key
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
        game_data.z64.update(bpy.context, None)
        actor = game_data.z64.actors.actorsByID[self.actor_id]
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
                            param_val = game_data.z64.actors.chestItemByKey[cur_prop_value].value
                        elif param.type == "Collectible":
                            param_val = game_data.z64.actors.collectibleItemsByKey[cur_prop_value].value
                        elif param.type == "Message":
                            param_val = game_data.z64.actors.messageItemsByKey[cur_prop_value].value
                        elif param.type == "Enum":
                            param_val = getEvalParamsInt(cur_prop_value)
                if "Rot" in target:
                    attr = getattr(self, get_prop_name(actor.key, "Type", None, 1), None)
                    type_value = getEvalParamsInt(attr) if attr is not None else None

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
        game_data.z64.update(bpy.context, None)
        actor = game_data.z64.actors.actorsByID[self.actor_id]
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
                        item_map = game_data.z64.actors.chestItemByKey
                    else:
                        search_op = layout.operator(OOT_SearchNaviMsgIDEnumOperator.bl_idname)
                        label_name = "Navi Message ID"
                        item_map = game_data.z64.actors.messageItemsByKey
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

    def draw_props(
        self,
        layout: UILayout,
        owner: Object,
        alt_scene_props: Z64_AlternateSceneHeaderProperty,
        altRoomProp: Z64_AlternateRoomHeaderProperty,
    ):
        actorIDBox = layout.column()

        actorIDBox.row().prop(self, "menu_tab", expand=True)
        actor_cs_props = owner.z64_actor_cs_property

        if self.menu_tab == "General":
            searchOp = actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon="VIEWZOOM")
            searchOp.actor_user = "Actor"
            searchOp.obj_name = owner.name

            split = actorIDBox.split(factor=0.5)

            if self.actor_id == "None":
                actorIDBox.box().label(text="This Actor was deleted from the XML file.")
                return

            split.label(text="Actor ID")
            split.label(text=getEnumName(game_data.z64.get_enum("actor_id"), self.actor_id))

            if (
                game_data.z64.is_oot()
                and bpy.context.scene.fast64.oot.can_use_new_actor_panel()
                and self.actor_id != "Custom"
            ):
                self.draw_params(actorIDBox, owner)

            if self.actor_id == "Custom":
                prop_split(actorIDBox, self, "actor_id_custom", "Actor ID Custom")

            paramBox = actorIDBox.box()
            paramBox.label(text="Actor Parameter")

            if (
                game_data.z64.is_oot()
                and bpy.context.scene.fast64.oot.can_use_new_actor_panel()
                and self.actor_id != "Custom"
            ):
                paramBox.prop(self, "eval_params")
                paramBox.prop(self, "params", text="")
            else:
                paramBox.prop(self, "params_custom", text="")

            rotations_used = []

            if bpy.context.scene.fast64.oot.can_use_new_actor_panel() and self.actor_id != "Custom":
                if self.is_rotation_used("XRot"):
                    rotations_used.append("X")
                if self.is_rotation_used("YRot"):
                    rotations_used.append("Y")
                if self.is_rotation_used("ZRot"):
                    rotations_used.append("Z")
            elif self.rot_override:
                rotations_used = ["X", "Y", "Z"]

            if self.actor_id == "Custom":
                paramBox.prop(self, "rot_override", text="Override Rotation (ignore Blender rot)")

            for rot in rotations_used:
                custom = (
                    "_custom"
                    if not bpy.context.scene.fast64.oot.can_use_new_actor_panel() or self.actor_id == "Custom"
                    else ""
                )
                prop_split(paramBox, self, f"rot_{rot.lower()}{custom}", f"Rot {rot}")

            if not is_oot_features():
                layout_halfday = actorIDBox.box().column()
                layout_halfday.label(text="Spawn Schedule")
                row = layout_halfday.row(align=True)
                row.prop(self, "halfday_all", text="Always Spawn")

                if not self.halfday_all:
                    row.prop(self, "halfday_all_dawns", text="All Dawns")
                    row.prop(self, "halfday_all_nights", text="All Nights")

                    if not self.halfday_all_dawns and not self.halfday_all_nights:
                        prop_text = get_list_tab_text("Entries", len(self.halfday_bits))
                        layout_halfday.prop(
                            self,
                            "halfday_show_entries",
                            text=prop_text,
                            icon="TRIA_DOWN" if self.halfday_show_entries else "TRIA_RIGHT",
                        )

                        if self.halfday_show_entries:
                            for i, item in enumerate(self.halfday_bits):
                                item.draw_props(layout_halfday, owner, i)
                            drawAddButton(layout_halfday, len(self.halfday_bits), "Actor Halfday", None, owner.name)
        elif self.menu_tab == "Actor Cutscene":
            actorIDBox.prop(self, "use_global_actor_cs")

            if self.use_global_actor_cs:
                prop_split(actorIDBox, self, "actor_cs_index", "Actor CS Index")
                label_box = actorIDBox.box()
                label_box.label(text="This should match the 'CutsceneEntry' array entry of", icon="INFO")
                label_box.label(text="the actor cutscene you want to use. For instance with chests, ")
                label_box.label(text="it should be the index of the entry where there's")
                label_box.label(text="'CS_CAM_ID_GLOBAL_LONG_CHEST_OPENING'.")

                if self.actor_cs_index > 119:
                    label_box.label(text="The index can't be over 119!", icon="ERROR")
            else:
                actor_cs_props.draw_props(actorIDBox, owner, alt_scene_props, False)

        headerProp: Z64_ActorHeaderProperty = self.headerSettings
        headerProp.draw_props(actorIDBox, "Actor", altRoomProp, owner.name)


class Z64_TransitionActorProperty(PropertyGroup):
    fromRoom: PointerProperty(type=Object, poll=lambda self, object: self.isRoomEmptyObject(object))
    toRoom: PointerProperty(type=Object, poll=lambda self, object: self.isRoomEmptyObject(object))
    cameraTransitionFront: EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionFrontCustom: StringProperty(default="0x00")
    cameraTransitionBack: EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionBackCustom: StringProperty(default="0x00")
    isRoomTransition: BoolProperty(name="Is Room Transition", default=True)

    actor: PointerProperty(type=Z64_ActorProperty)

    # MM exclusive
    cutscene_id: StringProperty(
        name="Cutscene ID", default="CS_ID_GLOBAL_END", description="See the `CutsceneId` enum for more values"
    )

    def isRoomEmptyObject(self, obj: Object):
        return obj.type == "EMPTY" and obj.ootEmptyType == "Room"

    def draw_props(
        self, layout: UILayout, altSceneProp: Z64_AlternateSceneHeaderProperty, roomObj: Object, objName: str
    ):
        actorIDBox = layout.column()

        searchOp = actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon="VIEWZOOM")
        searchOp.actor_user = "Transition Actor"
        searchOp.obj_name = objName

        split = actorIDBox.split(factor=0.5)
        split.label(text="Actor ID")
        split.label(text=getEnumName(game_data.z64.get_enum("actor_id"), self.actor.actor_id))

        if bpy.context.scene.fast64.oot.can_use_new_actor_panel() and self.actor.actor_id != "Custom":
            self.actor.draw_params(actorIDBox, roomObj)

        if self.actor.actor_id == "Custom":
            prop_split(actorIDBox, self.actor, "actor_id_custom", "")

        paramBox = actorIDBox.box()
        paramBox.label(text="Actor Parameter")
        if (
            is_oot_features()
            and bpy.context.scene.fast64.oot.can_use_new_actor_panel()
            and self.actor.actor_id != "Custom"
        ):
            paramBox.prop(self.actor, "eval_params")
            paramBox.prop(self.actor, "params", text="")
        else:
            paramBox.prop(self.actor, "params_custom", text="")

        if not is_oot_features():
            prop_split(actorIDBox, self, "cutscene_id", "Cutscene ID")

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

        headerProps: Z64_ActorHeaderProperty = self.actor.headerSettings
        headerProps.draw_props(actorIDBox, "Transition Actor", altSceneProp, objName)


class Z64_EntranceProperty(PropertyGroup):
    # This is also used in entrance list.
    spawnIndex: IntProperty(min=0)
    customActor: BoolProperty(name="Use Custom Actor")
    actor: PointerProperty(type=Z64_ActorProperty)

    tiedRoom: PointerProperty(
        type=Object,
        poll=lambda self, object: self.isRoomEmptyObject(object),
        description="Used to set the room index",
    )

    def isRoomEmptyObject(self, obj: Object):
        return obj.type == "EMPTY" and obj.ootEmptyType == "Room"

    def draw_props(self, layout: UILayout, obj: Object, altSceneProp: Z64_AlternateSceneHeaderProperty, objName: str):
        box = layout.column()

        roomObj = getRoomObj(obj)
        if roomObj is None:
            box.label(text="This must be part of a Room empty's hierarchy.", icon="OUTLINER")

        entranceProp = obj.ootEntranceProperty
        box.prop(entranceProp, "customActor")

        if entranceProp.customActor:
            prop_split(box, entranceProp.actor, "actor_id_custom", "Actor ID Custom")

        prop_split(box, entranceProp, "tiedRoom", "Room")
        prop_split(box, entranceProp, "spawnIndex", "Spawn Index")

        if bpy.context.scene.fast64.oot.can_use_new_actor_panel() and not self.customActor:
            self.actor.draw_params(box, obj)

        paramBox = box.box()
        paramBox.label(text="Actor Parameter")
        if is_oot_features() and bpy.context.scene.fast64.oot.can_use_new_actor_panel() and not self.customActor:
            paramBox.prop(self.actor, "eval_params")
            paramBox.prop(self.actor, "params", text="")
        else:
            paramBox.prop(self.actor, "params_custom", text="")

        headerProps: Z64_ActorHeaderProperty = entranceProp.actor.headerSettings
        headerProps.draw_props(box, "Entrance", altSceneProp, objName)


classes = (
    Z64_HalfdayItem,
    Z64_ActorHeaderItemProperty,
    Z64_ActorHeaderProperty,
    Z64_ActorProperty,
    Z64_TransitionActorProperty,
    Z64_EntranceProperty,
)


def actor_props_register():
    # generate props for OoT
    create_game_props("OOT")

    # generate props for MM
    create_game_props("MM")

    for cls in classes:
        register_class(cls)

    Object.ootActorProperty = PointerProperty(type=Z64_ActorProperty)
    Object.ootTransitionActorProperty = PointerProperty(type=Z64_TransitionActorProperty)
    Object.ootEntranceProperty = PointerProperty(type=Z64_EntranceProperty)


def actor_props_unregister():
    del Object.ootActorProperty
    del Object.ootTransitionActorProperty
    del Object.ootEntranceProperty

    for cls in reversed(classes):
        unregister_class(cls)
