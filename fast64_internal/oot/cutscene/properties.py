from bpy.types import PropertyGroup, Object, UILayout
from bpy.props import StringProperty, EnumProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty
from bpy.utils import register_class, unregister_class
from ...utility import PluginError, prop_split
from ..oot_utility import OOTCollectionAdd, drawCollectionOps, getEnumName
from ..oot_constants import ootEnumMusicSeq
from ..oot_upgrade import upgradeCutsceneProperties
from .operators import OOTCSTextboxAdd, OOT_SearchCSDestinationEnumOperator, drawCSListAddOp
from .constants import (
    ootEnumCSTextboxType,
    ootEnumCSListType,
    ootEnumCSTransitionType,
    ootEnumCSTextboxTypeIcons,
    ootEnumCSDestinationType,
    ootEnumCSMiscType,
    ootEnumTextType,
    ootCSSubPropToName,
    ootEnumOcarinaAction,
    ootEnumSeqPlayer,
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

    def draw(self, layout: UILayout, listProp: "OOTCSListProperty", listIndex: int, cmdIndex: int, objName: str, collectionType: str):
        # Draws list elements
        box = layout.box().column()

        box.prop(
            self,
            "expandTab",
            text=self.getName() + " " + str(cmdIndex),
            icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT",
        )
        if not self.expandTab:
            return

        drawCollectionOps(box, cmdIndex, collectionType + "." + self.attrName, listIndex, objName)

        for p in self.subprops:
            if self.filterProp(p, listProp):
                name = self.filterName(p, listProp)
                displayName = ootCSSubPropToName[name]

                if name == "csSeqPlayer":
                    # change the property name to draw the other enum for fade seq command
                    p = name

                prop_split(box, self, p, displayName)

                customValues = [
                    "csMiscType",
                    "csTextType",
                    "ocarinaAction",
                    "csSeqID",
                    "csSeqPlayer",
                ]
                if name in customValues and getattr(self, p) == "Custom":
                    prop_split(box, self, f"{name}Custom", f"{displayName} Custom")


class OOTCSTextboxProperty(OOTCSProperty, PropertyGroup):
    propName = "Textbox"
    attrName = "textbox"
    subprops = [
        "textID",
        "ocarinaAction",
        "startFrame",
        "endFrame",
        "csTextType",
        "topOptionTextID",
        "bottomOptionTextID",
        "ocarinaMessageId",
    ]
    textboxType: EnumProperty(items=ootEnumCSTextboxType)

    # subprops
    textID: StringProperty(name="", default="0x0000")
    ocarinaAction: EnumProperty(name="Ocarina Action", items=ootEnumOcarinaAction, default="OCARINA_ACTION_TEACH_MINUET")
    ocarinaActionCustom: StringProperty(default="OCARINA_ACTION_CUSTOM")
    topOptionTextID: StringProperty(name="", default="0x0000")
    bottomOptionTextID: StringProperty(name="", default="0x0000")
    ocarinaMessageId: StringProperty(name="", default="0x0000")
    csTextType: EnumProperty(name="Text Type", items=ootEnumTextType, default="CS_TEXT_NORMAL")
    csTextTypeCustom: StringProperty(default="CS_TEXT_CUSTOM")

    def getName(self):
        return self.textboxType

    def filterProp(self, name, listProp):
        if self.textboxType == "Text":
            return name not in ["ocarinaAction", "ocarinaMessageId"]
        elif self.textboxType == "None":
            return name in ["startFrame", "endFrame"]
        elif self.textboxType == "LearnSong":
            return name in ["ocarinaAction", "startFrame", "endFrame", "ocarinaMessageId"]
        else:
            raise PluginError("Invalid property name for OOTCSTextboxProperty")


class OOTCSLightingProperty(OOTCSProperty, PropertyGroup):
    propName = "Lighting"
    attrName = "lighting"
    subprops = ["lightSettingsIndex", "startFrame"]
    lightSettingsIndex: IntProperty(name="", default=1, min=1)


class OOTCSTimeProperty(OOTCSProperty, PropertyGroup):
    propName = "Time"
    attrName = "time"
    subprops = ["startFrame", "hour", "minute"]
    hour: IntProperty(name="", default=23, min=0, max=23)
    minute: IntProperty(name="", default=59, min=0, max=59)


class OOTCSBGMProperty(OOTCSProperty, PropertyGroup):
    propName = "BGM"
    attrName = "bgm"
    subprops = ["csSeqID", "startFrame", "endFrame"]
    csSeqID: EnumProperty(name="Seq ID", items=ootEnumMusicSeq, default="NA_BGM_GENERAL_SFX")
    csSeqIDCustom: StringProperty(default="NA_BGM_CUSTOM")
    csSeqPlayer: EnumProperty(name="Seq Player", items=ootEnumSeqPlayer, default="CS_FADE_OUT_BGM_MAIN")
    csSeqPlayerCustom: StringProperty(default="NA_BGM_CUSTOM")

    def filterProp(self, name, listProp):
        return name != "endFrame" or listProp.listType == "FadeBGM"

    def filterName(self, name, listProp):
        if name == "csSeqID" and listProp.listType == "FadeBGM":
            return "csSeqPlayer"
        return name


class OOTCSMiscProperty(OOTCSProperty, PropertyGroup):
    propName = "Misc"
    attrName = "misc"
    subprops = ["csMiscType", "startFrame", "endFrame"]
    csMiscType: EnumProperty(name="Type", items=ootEnumCSMiscType, default="CS_MISC_SET_LOCKED_VIEWPOINT")
    csMiscTypeCustom: StringProperty(default="CS_MISC_CUSTOM")


class OOTCSRumbleProperty(OOTCSProperty, PropertyGroup):
    propName = "0x09"
    attrName = "nine"
    subprops = ["startFrame", "rumbleSourceStrength", "rumbleDuration", "rumbleDecreaseRate"]

    # those variables are unsigned chars in decomp
    # see https://github.com/zeldaret/oot/blob/542012efa68d110d6b631f9d149f6e5f4e68cc8e/src/code/z_rumble.c#L58-L77
    rumbleSourceStrength: IntProperty(name="", default=0, min=0, max=255)
    rumbleDuration: IntProperty(name="", default=0, min=0, max=255)
    rumbleDecreaseRate: IntProperty(name="", default=0, min=0, max=255)


class OOTCSListProperty(PropertyGroup):
    expandTab: BoolProperty(default=True)

    listType: EnumProperty(items=ootEnumCSListType)
    textbox: CollectionProperty(type=OOTCSTextboxProperty)
    lighting: CollectionProperty(type=OOTCSLightingProperty)
    time: CollectionProperty(type=OOTCSTimeProperty)
    bgm: CollectionProperty(type=OOTCSBGMProperty)
    misc: CollectionProperty(type=OOTCSMiscProperty)
    nine: CollectionProperty(type=OOTCSRumbleProperty)

    fxType: EnumProperty(items=ootEnumCSTransitionType)
    fxTypeCustom: StringProperty(default="CS_TRANS_CUSTOM")
    fxStartFrame: IntProperty(name="", default=0, min=0)
    fxEndFrame: IntProperty(name="", default=1, min=0)

    def draw_props(self, layout: UILayout, listIndex: int, objName: str, collectionType: str):
        box = layout.box().column()

        # Draw current command tab
        box.prop(
            self,
            "expandTab",
            text=self.listType + " List" if self.listType != "FX" else "Transition",
            icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT",
        )

        if not self.expandTab:
            return

        drawCollectionOps(box, listIndex, collectionType, None, objName, False)

        # Draw current command content
        if self.listType == "Textbox":
            attrName = "textbox"
        elif self.listType == "FX":
            prop_split(box, self, "fxType", "Transition Type")
            if self.fxType == "Custom":
                prop_split(box, self, "fxTypeCustom", "Transition Type Custom")

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
        else:
            raise PluginError("Internal error: invalid listType " + self.listType)

        dat = getattr(self, attrName)

        if self.listType == "Textbox":
            subBox = box.box()
            subBox.label(text="TextBox Commands")
            row = subBox.row(align=True)

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

        for i, p in enumerate(dat):
            p.draw(box, self, listIndex, i, objName, collectionType)

        if len(dat) == 0:
            box.label(text="No items in " + self.listType + " List.")


class OOTCutsceneProperty(PropertyGroup):
    csEndFrame: IntProperty(name="End Frame", min=0, default=100)
    csWriteTerminator: BoolProperty(name="Cutscene Destination (Scene Change)")
    csDestination: EnumProperty(name="Destination", items=ootEnumCSDestinationType, default="CS_DEST_CUTSCENE_MAP_GANON_HORSE")
    csDestinationCustom: StringProperty(default="CS_DEST_CUSTOM")
    csTermIdx: IntProperty(name="Index", min=0)
    csTermStart: IntProperty(name="Start Frame", min=0, default=99)
    csTermEnd: IntProperty(name="End Frame", min=0, default=100)
    csLists: CollectionProperty(type=OOTCSListProperty, name="Cutscene Lists")

    @staticmethod
    def upgrade_object(csListProp: OOTCSTextboxProperty | OOTCSBGMProperty | OOTCSMiscProperty | OOTCSRumbleProperty):
        upgradeCutsceneProperties(csListProp)

    def draw_props(self, layout: UILayout, obj: Object):
        layout.prop(self, "csEndFrame")

        csDestLayout = layout.box()
        csDestLayout.prop(self, "csWriteTerminator")
        if self.csWriteTerminator:
            r = csDestLayout.row()

            searchBox = r.box()
            boxRow = searchBox.row()
            searchOp = boxRow.operator(OOT_SearchCSDestinationEnumOperator.bl_idname, icon="VIEWZOOM", text="")
            searchOp.objName = obj.name
            boxRow.label(text=getEnumName(ootEnumCSDestinationType, self.csDestination))
            if self.csDestination == "Custom":
                prop_split(searchBox.column(), self, "csDestinationCustom", "Cutscene Destination Custom")

            r = csDestLayout.row()
            r.prop(self, "csTermStart")
            r.prop(self, "csTermEnd")

        drawCSListAddOp(layout, obj.name, "Cutscene")

        for i, p in enumerate(self.csLists):
            p.draw_props(layout, i, obj.name, "Cutscene")


classes = (
    OOTCSTextboxProperty,
    OOTCSLightingProperty,
    OOTCSTimeProperty,
    OOTCSBGMProperty,
    OOTCSMiscProperty,
    OOTCSRumbleProperty,
    OOTCSListProperty,
    OOTCutsceneProperty,
)


def cutscene_props_register():
    for cls in classes:
        register_class(cls)

    Object.ootCutsceneProperty = PointerProperty(type=OOTCutsceneProperty)


def cutscene_props_unregister():
    del Object.ootCutsceneProperty

    for cls in reversed(classes):
        unregister_class(cls)
