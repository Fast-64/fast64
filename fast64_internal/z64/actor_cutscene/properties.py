from bpy.props import (
    IntProperty,
    PointerProperty,
    BoolProperty,
    EnumProperty,
    StringProperty,
    CollectionProperty,
    FloatVectorProperty,
)
from bpy.utils import register_class, unregister_class
from bpy.types import PropertyGroup, UILayout, Object
from ...utility import prop_split
from ..collection_utility import drawAddButton, drawCollectionOps
from ..utility import get_list_tab_text
from ..actor.properties import Z64_ActorHeaderProperty
from ..scene.properties import Z64_AlternateSceneHeaderProperty


enum_cs_cam_id = [
    ("Custom", "Custom", "Custom"),
    ("Camera", "Camera Object", "Camera Object"),
    ("CS_CAM_ID_GLOBAL_ELEGY", "Elegy of Emptiness", "-25 (CAM_SET_ELEGY_SHELL)"),
    ("CS_CAM_ID_GLOBAL_SIDED", "Sided", "-24 (CAM_SET_SIDED)"),
    ("CS_CAM_ID_GLOBAL_BOAT_CRUISE", "Boat Cruise", "-23 (CAM_SET_BOAT_CRUISE)"),
    ("CS_CAM_ID_GLOBAL_N16", "N16", "-22 (CAM_SET_NONE)"),
    ("CS_CAM_ID_GLOBAL_SUBJECTD", "Subjectd", "-21 (CAM_SET_SUBJECTD)"),
    ("CS_CAM_ID_GLOBAL_NORMALD", "Normald", "-20 (CAM_SET_NORMALD)"),
    ("CS_CAM_ID_GLOBAL_N13", "N13", "-19 (CAM_SET_NONE)"),
    ("CS_CAM_ID_GLOBAL_N12", "N12", "-18 (CAM_SET_NONE)"),
    ("CS_CAM_ID_GLOBAL_N11", "N11", "-17 (CAM_SET_NONE)"),
    ("CS_CAM_ID_GLOBAL_WARP_PAD_ENTRANCE", "Warp Pad Entrance", "-16 (CAM_SET_WARP_PAD_ENTRANCE)"),
    ("CS_CAM_ID_GLOBAL_ATTENTION", "Attention", "-15 (CAM_SET_ATTENTION)"),
    ("CS_CAM_ID_GLOBAL_CONNECT", "Connect", "-14 (CAM_SET_CONNECT0)"),
    ("CS_CAM_ID_GLOBAL_REMOTE_BOMB", "Remote Bomb", "-13 (CAM_SET_REMOTEBOMB)"),
    ("CS_CAM_ID_GLOBAL_N0C", "N0C", "-12 (CAM_SET_NONE)"),
    ("CS_CAM_ID_GLOBAL_MASK_TRANSFORMATION", "Mask Transformation", "-11 (CAM_SET_MASK_TRANSFORMATION)"),
    ("CS_CAM_ID_GLOBAL_LONG_CHEST_OPENING", "Long Chest Opening", "-10 (CAM_SET_LONG_CHEST_OPENING)"),
    ("CS_CAM_ID_GLOBAL_REVIVE", "Revive", "-9 (CAM_SET_REBIRTH)"),
    ("CS_CAM_ID_GLOBAL_DEATH", "Death", "-8 (CAM_SET_DEATH)"),
    ("CS_CAM_ID_GLOBAL_WARP_PAD_MOON", "Warp Pad Moon", "-7 (CAM_SET_WARP_PAD_MOON)"),
    ("CS_CAM_ID_GLOBAL_SONG_WARP", "Song Warp", "-6 (CAM_SET_NAVI)"),
    ("CS_CAM_ID_GLOBAL_ITEM_SHOW", "Item Show", "-5 (CAM_SET_ITEM3)"),
    ("CS_CAM_ID_GLOBAL_ITEM_BOTTLE", "Item Bottle", "-4 (CAM_SET_ITEM2)"),
    ("CS_CAM_ID_GLOBAL_ITEM_OCARINA", "Item Ocarina", "-3 (CAM_SET_ITEM1)"),
    ("CS_CAM_ID_GLOBAL_ITEM_GET", "Item Get", "-2 (CAM_SET_ITEM0)"),
    ("CS_CAM_ID_NONE", "None", "-1"),
]

enum_end_sfx = [
    ("Custom", "Custom", "Custom"),
    ("CS_END_SFX_NONE", "None", "0"),
    ("CS_END_SFX_TRE_BOX_APPEAR", "Chest Appear", "1"),
    ("CS_END_SFX_CORRECT_CHIME", "Correct Chime", "2"),
    ("CS_END_SFX_NONE_ALT", "None Alt", "255"),
]

enum_hud_visibility = [
    ("Custom", "Custom", "Custom"),
    ("CS_HUD_VISIBILITY_NONE", "None", "0"),
    ("CS_HUD_VISIBILITY_ALL", "All", "1"),
    ("CS_HUD_VISIBILITY_A_HEARTS_MAGIC", "Only A Button, Hearts and Magic Meter", "2"),
    ("CS_HUD_VISIBILITY_C_HEARTS_MAGIC", "Only C Buttons, Hearts and Magic Meter", "3"),
    ("CS_HUD_VISIBILITY_ALL_NO_MINIMAP", "All without Minimap", "4"),
    ("CS_HUD_VISIBILITY_A_B_C", "Only A Button, B Button and C Buttons", "5"),
    ("CS_HUD_VISIBILITY_B_MINIMAP", "Only B Button and Minimap", "6"),
    ("CS_HUD_VISIBILITY_A", "Only A Button", "7"),
    ("CS_HUD_VISIBILITY_ALL_ALT", "All 2", "-1"),
]

enum_end_cam = [
    ("Custom", "Custom", "Custom"),
    ("CS_END_CAM_0", "Cam 0", "0"),
    ("CS_END_CAM_1", "Cam 1", "1"),
    ("CS_END_CAM_SMOOTH", "Cam Smooth", "2"),
]


def poll_camera_obj(self, obj: Object):
    return obj.type == "CAMERA" and obj.ootCameraPositionProperty.is_actor_cs_cam


class Z64_ActorCutscene(PropertyGroup):
    priority: IntProperty(name="Priority", default=700, description="Lower number means higher priority")
    length: IntProperty(name="Length", min=-1, default=-1)
    cs_cam_id: EnumProperty(
        name="CS Cam ID",
        items=enum_cs_cam_id,
        default=2,
        description="Index of `CsCameraEntry` to use. Negative indices use `sGlobalCamDataSettings`. Indices 0 and above use `CsCameraEntry` from a sceneLayer",
    )
    cs_cam_id_custom: StringProperty(name="CS Cam ID Custom", default="CS_CAM_ID_NONE")
    cs_cam_obj: PointerProperty(type=Object, poll=poll_camera_obj)
    script_index: IntProperty(name="Script Index", min=-1, default=-1, description="Gets the priority over 'CS Cam ID'")
    additional_cs_id: IntProperty(name="Additional CS ID", min=-1, default=-1)
    end_sfx: EnumProperty(name="End Sound Effect", items=enum_end_sfx, default=1)
    end_sfx_custom: StringProperty(name="End Sound Effect Custom")
    custom_value: StringProperty(
        name="Custom Value", default="255", description="0 - 99: actor-specific custom value. 100+: spawn. 255: none"
    )
    hud_visibility: EnumProperty(name="HUD Visibility", items=enum_hud_visibility, default=1)
    hud_visibility_custom: StringProperty(name="HUD Visibility Custom")
    end_cam: EnumProperty(name="End Cam", items=enum_end_cam, default=1)
    end_cam_custom: StringProperty(name="End Cam Custom")
    letterbox_size: IntProperty(name="Letterbox Size", min=0, max=255, default=30)

    # ui only props
    show_item: BoolProperty()

    def draw_props(self, layout: UILayout, owner: Object, index: int):
        layout = layout.column()
        layout.prop(
            self, "show_item", text=f"Entry No. {index + 1}", icon="TRIA_DOWN" if self.show_item else "TRIA_RIGHT"
        )

        if self.show_item:
            drawCollectionOps(layout, index, "Actor CS", None, owner.name)

            prop_split(layout, self, "priority", "Priority")
            prop_split(layout, self, "length", "Length")

            prop_split(layout, self, "cs_cam_id", "CS Cam ID")
            if self.cs_cam_id == "Custom":
                prop_split(layout, self, "cs_cam_id_custom", "CS Cam ID Custom")
            elif self.cs_cam_id == "Camera":
                prop_split(layout, self, "cs_cam_obj", "Camera Object")

            prop_split(layout, self, "script_index", "Script Index")
            prop_split(layout, self, "additional_cs_id", "Additional CS ID")

            prop_split(layout, self, "end_sfx", "End Sound Effect")
            if self.end_sfx == "Custom":
                prop_split(layout, self, "end_sfx_custom", "End Sound Effect Custom")

            prop_split(layout, self, "custom_value", "Custom Value")

            prop_split(layout, self, "hud_visibility", "HUD Visibility")
            if self.hud_visibility == "Custom":
                prop_split(layout, self, "hud_visibility_custom", "HUD Visibility Custom")

            prop_split(layout, self, "end_cam", "End Cam")
            if self.end_cam == "Custom":
                prop_split(layout, self, "end_cam_custom", "End Cam Custom")

            prop_split(layout, self, "letterbox_size", "Letterbox Size")


class Z64_ActorCutsceneProperty(PropertyGroup):
    entries: CollectionProperty(type=Z64_ActorCutscene)
    header_settings: PointerProperty(type=Z64_ActorHeaderProperty)

    # ui only props
    show_entries: BoolProperty(default=True)

    def draw_props(
        self,
        layout: UILayout,
        owner: Object,
        alt_header_props: Z64_AlternateSceneHeaderProperty,
        draw_header: bool = True,
    ):
        layout_entries = layout.box().column()

        prop_text = get_list_tab_text("Entries", len(self.entries))
        layout_entries.prop(
            self, "show_entries", text=prop_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT"
        )

        if self.show_entries:
            for i, actor_cs in enumerate(self.entries):
                actor_cs.draw_props(layout_entries.box(), owner, i)

            drawAddButton(layout_entries, len(self.entries), "Actor CS", None, owner.name)

        if draw_header:
            self.header_settings.draw_props(layout, "Actor CS Headers", alt_header_props, owner.name)


classes = (
    Z64_ActorCutscene,
    Z64_ActorCutsceneProperty,
)


def actor_cs_register():
    for cls in classes:
        register_class(cls)

    Object.z64_actor_cs_property = PointerProperty(type=Z64_ActorCutsceneProperty)


def actor_cs_unregister():
    del Object.z64_actor_cs_property

    for cls in reversed(classes):
        unregister_class(cls)
