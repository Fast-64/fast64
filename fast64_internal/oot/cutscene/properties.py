import bpy
from bpy.types import PropertyGroup, Object, UILayout, Scene
from bpy.props import StringProperty, EnumProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty
from bpy.utils import register_class, unregister_class
from ...utility import PluginError, prop_split
from ..oot_utility import OOTCollectionAdd, drawCollectionOps
from .operators import OOTCSTextboxAdd, drawCSListAddOp
from .constants import ootEnumCSTextboxType, ootEnumCSListType, ootEnumCSTransitionType, ootEnumCSTextboxTypeIcons

from .motion.operators import (
    OOTCSMotionPlayPreview,
    OOTCSMotionCreateCameraShot,
    OOTCSMotionCreatePlayerCueList,
    OOTCSMotionCreateActorCueList,
)


# Perhaps this should have been called something like OOTCSParentPropertyType,
# but now it needs to keep the same name to not break existing scenes which use
# the cutscene system.
class OOTCSProperty:
    propName = None
    attrName = None
    subprops = ["startFrame", "endFrame"]
    expandTab: BoolProperty(default=True)
    startFrame: IntProperty(name="", default=0, min=0)
    endFrame: IntProperty(name="", default=1, min=0)

    def getName(self):
        return self.propName

    def filterProp(self, name, listProp):
        return True

    def filterName(self, name, listProp):
        return name

    def draw(self, layout, listProp, listIndex, cmdIndex, objName, collectionType):
        layout.prop(
            self,
            "expandTab",
            text=self.getName() + " " + str(cmdIndex),
            icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT",
        )
        if not self.expandTab:
            return
        box = layout.box().column()
        drawCollectionOps(box, cmdIndex, collectionType + "." + self.attrName, listIndex, objName)
        for p in self.subprops:
            if self.filterProp(p, listProp):
                prop_split(box, self, p, self.filterName(p, listProp))


class OOTCSTextboxProperty(OOTCSProperty, PropertyGroup):
    propName = "Textbox"
    attrName = "textbox"
    subprops = [
        "messageId",
        "ocarinaSongAction",
        "startFrame",
        "endFrame",
        "type",
        "topOptionBranch",
        "bottomOptionBranch",
        "ocarinaMessageId",
    ]
    textboxType: EnumProperty(items=ootEnumCSTextboxType)
    messageId: StringProperty(name="", default="0x0000")
    ocarinaSongAction: StringProperty(name="", default="0x0000")
    type: StringProperty(name="", default="0x0000")
    topOptionBranch: StringProperty(name="", default="0x0000")
    bottomOptionBranch: StringProperty(name="", default="0x0000")
    ocarinaMessageId: StringProperty(name="", default="0x0000")

    def getName(self):
        return self.textboxType

    def filterProp(self, name, listProp):
        if self.textboxType == "Text":
            return name not in ["ocarinaSongAction", "ocarinaMessageId"]
        elif self.textboxType == "None":
            return name in ["startFrame", "endFrame"]
        elif self.textboxType == "LearnSong":
            return name in ["ocarinaSongAction", "startFrame", "endFrame", "ocarinaMessageId"]
        else:
            raise PluginError("Invalid property name for OOTCSTextboxProperty")


class OOTCSLightingProperty(OOTCSProperty, PropertyGroup):
    propName = "Lighting"
    attrName = "lighting"
    subprops = ["index", "startFrame"]
    index: IntProperty(name="", default=1, min=1)


class OOTCSTimeProperty(OOTCSProperty, PropertyGroup):
    propName = "Time"
    attrName = "time"
    subprops = ["startFrame", "hour", "minute"]
    hour: IntProperty(name="", default=23, min=0, max=23)
    minute: IntProperty(name="", default=59, min=0, max=59)


class OOTCSBGMProperty(OOTCSProperty, PropertyGroup):
    propName = "BGM"
    attrName = "bgm"
    subprops = ["value", "startFrame", "endFrame"]
    value: StringProperty(name="", default="0x0000")

    def filterProp(self, name, listProp):
        return name != "endFrame" or listProp.listType == "FadeBGM"

    def filterName(self, name, listProp):
        if name == "value":
            return "Fade Type" if listProp.listType == "FadeBGM" else "Sequence"
        return name


class OOTCSMiscProperty(OOTCSProperty, PropertyGroup):
    propName = "Misc"
    attrName = "misc"
    subprops = ["operation", "startFrame", "endFrame"]
    operation: IntProperty(name="", default=1, min=1, max=35)


class OOTCS0x09Property(OOTCSProperty, PropertyGroup):
    propName = "0x09"
    attrName = "nine"
    subprops = ["startFrame", "unk2", "unk3", "unk4"]
    unk2: StringProperty(name="", default="0x00")
    unk3: StringProperty(name="", default="0x00")
    unk4: StringProperty(name="", default="0x00")


class OOTCSUnkProperty(OOTCSProperty, PropertyGroup):
    propName = "Unk"
    attrName = "unk"
    subprops = ["unk1", "unk2", "unk3", "unk4", "unk5", "unk6", "unk7", "unk8", "unk9", "unk10", "unk11", "unk12"]
    unk1: StringProperty(name="", default="0x00000000")
    unk2: StringProperty(name="", default="0x00000000")
    unk3: StringProperty(name="", default="0x00000000")
    unk4: StringProperty(name="", default="0x00000000")
    unk5: StringProperty(name="", default="0x00000000")
    unk6: StringProperty(name="", default="0x00000000")
    unk7: StringProperty(name="", default="0x00000000")
    unk8: StringProperty(name="", default="0x00000000")
    unk9: StringProperty(name="", default="0x00000000")
    unk10: StringProperty(name="", default="0x00000000")
    unk11: StringProperty(name="", default="0x00000000")
    unk12: StringProperty(name="", default="0x00000000")


class OOTCSListProperty(PropertyGroup):
    expandTab: BoolProperty(default=True)

    listType: EnumProperty(items=ootEnumCSListType)
    textbox: CollectionProperty(type=OOTCSTextboxProperty)
    lighting: CollectionProperty(type=OOTCSLightingProperty)
    time: CollectionProperty(type=OOTCSTimeProperty)
    bgm: CollectionProperty(type=OOTCSBGMProperty)
    misc: CollectionProperty(type=OOTCSMiscProperty)
    nine: CollectionProperty(type=OOTCS0x09Property)
    unk: CollectionProperty(type=OOTCSUnkProperty)

    unkType: StringProperty(name="", default="0x0001")
    fxType: EnumProperty(items=ootEnumCSTransitionType)
    fxStartFrame: IntProperty(name="", default=0, min=0)
    fxEndFrame: IntProperty(name="", default=1, min=0)

    def draw_props(self, layout: UILayout, listIndex: int, objName: str, collectionType: str):
        layout.prop(
            self,
            "expandTab",
            text=self.listType + " List" if self.listType != "FX" else "Scene Trans FX",
            icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT",
        )
        if not self.expandTab:
            return
        box = layout.box().column()
        drawCollectionOps(box, listIndex, collectionType, None, objName, False)

        if self.listType == "Textbox":
            attrName = "textbox"
        elif self.listType == "FX":
            prop_split(box, self, "fxType", "Transition")
            prop_split(box, self, "fxStartFrame", "Start Frame")
            prop_split(box, self, "fxEndFrame", "End Frame")
            return
        elif self.listType == "Lighting":
            attrName = "lighting"
        elif self.listType == "Time":
            attrName = "time"
        elif self.listType in ["PlayBGM", "StopBGM", "FadeBGM"]:
            attrName = "bgm"
        elif self.listType == "Misc":
            attrName = "misc"
        elif self.listType == "0x09":
            attrName = "nine"
        elif self.listType == "Unk":
            prop_split(box, self, "unkType", "Unk List Type")
            attrName = "unk"
        else:
            raise PluginError("Internal error: invalid listType " + self.listType)

        dat = getattr(self, attrName)
        for i, p in enumerate(dat):
            p.draw(box, self, listIndex, i, objName, collectionType)
        if len(dat) == 0:
            box.label(text="No items in " + self.listType + " List.")
        if self.listType == "Textbox":
            row = box.row(align=True)
            for l in range(3):
                addOp = row.operator(
                    OOTCSTextboxAdd.bl_idname,
                    text="Add " + ootEnumCSTextboxType[l][1],
                    icon=ootEnumCSTextboxTypeIcons[l],
                )
                addOp.collectionType = collectionType + ".textbox"
                addOp.textboxType = ootEnumCSTextboxType[l][0]
                addOp.listIndex = listIndex
                addOp.objName = objName
        else:
            addOp = box.operator(OOTCollectionAdd.bl_idname, text="Add item to " + self.listType + " List")
            addOp.option = len(dat)
            addOp.collectionType = collectionType + "." + attrName
            addOp.subIndex = listIndex
            addOp.objName = objName


class OOTCutsceneCommandBase:
    startFrame: IntProperty(min=0)
    endFrame: IntProperty(min=0)


class OOTCutsceneTransitionProperty(OOTCutsceneCommandBase, PropertyGroup):
    type: StringProperty(default="Unknown")


class OOTCutsceneMiscProperty(OOTCutsceneCommandBase, PropertyGroup):
    type: StringProperty(default="Unknown")


class OOTCutscenePreviewProperty(PropertyGroup):
    transitionList: CollectionProperty(type=OOTCutsceneTransitionProperty)
    miscList: CollectionProperty(type=OOTCutsceneMiscProperty)

    isFixedCamSet: BoolProperty(default=False)
    prevFrame: IntProperty(default=-1)
    nextFrame: IntProperty(default=1)


class OOTCutsceneProperty(PropertyGroup):
    csEndFrame: IntProperty(name="End Frame", min=0, default=100)
    csWriteTerminator: BoolProperty(name="Write Terminator (Code Execution)")
    csTermIdx: IntProperty(name="Index", min=0)
    csTermStart: IntProperty(name="Start Frm", min=0, default=99)
    csTermEnd: IntProperty(name="End Frm", min=0, default=100)
    csLists: CollectionProperty(type=OOTCSListProperty, name="Cutscene Lists")

    preview: PointerProperty(type=OOTCutscenePreviewProperty)

    def draw_props(self, layout: UILayout, obj: Object):
        split = layout.split(factor=0.5)
        split.label(text="Player Age for Preview")
        split.prop(bpy.context.scene, "previewPlayerAge", text="")

        split = layout.split(factor=0.5)
        split.operator(OOTCSMotionCreateCameraShot.bl_idname, icon="VIEW_CAMERA")
        split.operator(OOTCSMotionPlayPreview.bl_idname, icon="RESTRICT_VIEW_OFF")

        split = layout.split(factor=0.5)
        split.operator(OOTCSMotionCreatePlayerCueList.bl_idname)
        split.operator(OOTCSMotionCreateActorCueList.bl_idname)
         
        layout.prop(self, "csEndFrame")
        layout.prop(self, "csWriteTerminator")
        if self.csWriteTerminator:
            r = layout.row()
            r.prop(self, "csTermIdx")
            r.prop(self, "csTermStart")
            r.prop(self, "csTermEnd")
        for i, p in enumerate(self.csLists):
            p.draw_props(layout, i, obj.name, "Cutscene")

        drawCSListAddOp(layout, obj.name, "Cutscene")


classes = (
    OOTCSTextboxProperty,
    OOTCSLightingProperty,
    OOTCSTimeProperty,
    OOTCSBGMProperty,
    OOTCSMiscProperty,
    OOTCS0x09Property,
    OOTCSUnkProperty,
    OOTCSListProperty,
    OOTCutsceneTransitionProperty,
    OOTCutsceneMiscProperty,
    OOTCutscenePreviewProperty,
    OOTCutsceneProperty,
)


def cutscene_props_register():
    for cls in classes:
        register_class(cls)

    Object.ootCutsceneProperty = PointerProperty(type=OOTCutsceneProperty)
    Scene.ootCSPreviewNodesReady = BoolProperty(default=False)
    Scene.ootCSPreviewCSObj = PointerProperty(type=Object)


def cutscene_props_unregister():
    del Scene.ootCSPreviewCSObj
    del Scene.ootCSPreviewNodesReady
    del Object.ootCutsceneProperty

    for cls in reversed(classes):
        unregister_class(cls)
