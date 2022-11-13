from bpy.types import PropertyGroup, UILayout
from bpy.props import StringProperty, BoolProperty, EnumProperty
from .....utility import prop_split
from ....oot_constants import ootEnumSceneID


class OOTRemoveSceneSettingsProperty(PropertyGroup):
    name: StringProperty(name="Name", default="spot03")
    subFolder: StringProperty(name="Subfolder", default="overworld")
    customExport: BoolProperty(name="Custom Export Path")
    option: EnumProperty(items=ootEnumSceneID, default="SCENE_YDAN")


class OOTExportSceneSettingsProperty(PropertyGroup):
    name: StringProperty(name="Name", default="spot03")
    subFolder: StringProperty(name="Subfolder", default="overworld")
    exportPath: StringProperty(name="Directory", subtype="FILE_PATH")
    customExport: BoolProperty(name="Custom Export Path")
    singleFile: BoolProperty(
        name="Export as Single File",
        default=False,
        description="Does not split the scene and rooms into multiple files.",
    )
    option: EnumProperty(items=ootEnumSceneID, default="SCENE_YDAN")


class OOTImportSceneSettingsProperty(PropertyGroup):
    name: StringProperty(name="Name", default="spot03")
    subFolder: StringProperty(name="Subfolder", default="overworld")
    destPath: StringProperty(name="Directory", subtype="FILE_PATH")
    isCustomDest: BoolProperty(name="Custom Path")
    includeMesh: BoolProperty(name="Mesh", default=True)
    includeCollision: BoolProperty(name="Collision", default=True)
    includeActors: BoolProperty(name="Actors", default=True)
    includeCullGroups: BoolProperty(name="Cull Groups", default=True)
    includeLights: BoolProperty(name="Lights", default=True)
    includeCameras: BoolProperty(name="Cameras", default=True)
    includePaths: BoolProperty(name="Paths", default=True)
    includeWaterBoxes: BoolProperty(name="Water Boxes", default=True)
    option: EnumProperty(items=ootEnumSceneID, default="SCENE_YDAN")

    def draw(self, layout: UILayout, sceneOption: str):
        col = layout.column()
        includeButtons1 = col.row(align=True)
        includeButtons1.prop(self, "includeMesh", toggle=1)
        includeButtons1.prop(self, "includeCollision", toggle=1)

        includeButtons2 = col.row(align=True)
        includeButtons2.prop(self, "includeActors", toggle=1)
        includeButtons2.prop(self, "includeCullGroups", toggle=1)
        includeButtons2.prop(self, "includeLights", toggle=1)

        includeButtons3 = col.row(align=True)
        includeButtons3.prop(self, "includeCameras", toggle=1)
        includeButtons3.prop(self, "includePaths", toggle=1)
        includeButtons3.prop(self, "includeWaterBoxes", toggle=1)
        col.prop(self, "isCustomDest")
        if self.isCustomDest:
            prop_split(col, self, "destPath", "Directory")
            prop_split(col, self, "name", "Name")
        else:
            if self.option == "Custom":
                prop_split(col, self, "subFolder", "Subfolder")
                prop_split(col, self, "name", "Name")

        col.label(text="Cutscenes won't be imported.")

        if "SCENE_BDAN" in sceneOption:
            col.label(text="Pulsing wall effect won't be imported.", icon="ERROR")
