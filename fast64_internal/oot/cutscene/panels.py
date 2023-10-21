from bpy.utils import register_class, unregister_class
from bpy.types import Scene, Context
from bpy.props import BoolProperty, EnumProperty
from ...utility import prop_split
from ...panels import OOT_Panel
from .operators import OOT_ExportCutscene, OOT_ExportAllCutscenes, OOT_ImportCutscene
from .motion.preview import previewFrameHandler
from .motion.utility import getCutsceneCamera


class OoT_PreviewSettingsPanel(OOT_Panel):
    bl_idname = "OOT_PT_preview_settings"
    bl_label = "OOT CS Preview Settings"

    def draw(self, context):
        previewBox = self.layout.box()
        previewBox.box().label(text="Preview Settings")
        split = previewBox.split(factor=0.5)
        split.label(text="Player Age for Preview")
        split.prop(context.scene, "previewPlayerAge", text="")
        previewBox.prop(context.scene, "ootCsUseWidescreen")
        previewBox.prop(context.scene, "ootCsUseOpaqueCamBg")


class OOT_CutscenePanel(OOT_Panel):
    bl_idname = "OOT_PT_export_cutscene"
    bl_label = "OOT Cutscene Exporter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OOT"

    def draw(self, context):
        layout = self.layout

        exportBox = layout.box()
        exportBox.label(text="Cutscene Exporter")

        col = exportBox.column()
        if not context.scene.fast64.oot.hackerFeaturesEnabled:
            col.prop(context.scene, "useDecompFeatures")
        col.prop(context.scene, "exportMotionOnly")

        prop_split(exportBox, context.scene, "ootCutsceneExportPath", "Export To")

        activeObj = context.view_layer.objects.active
        label = None
        col = exportBox.column()
        colcol = col.column()
        if activeObj is None or activeObj.type != "EMPTY" or activeObj.ootEmptyType != "Cutscene":
            label = "Select a cutscene object"

        if activeObj is not None and activeObj.parent is not None:
            label = "Cutscene object must not be parented to anything"

        if label is not None:
            col.label(text=label)
            colcol.enabled = False

        colcol.operator(OOT_ExportCutscene.bl_idname)
        col.operator(OOT_ExportAllCutscenes.bl_idname)

        importBox = layout.box()
        importBox.label(text="Cutscene Importer")
        prop_split(importBox, context.scene, "ootCutsceneImportPath", "Import From")

        col = importBox.column()
        col.operator(OOT_ImportCutscene.bl_idname)


oot_cutscene_panel_classes = (OoT_PreviewSettingsPanel, OOT_CutscenePanel,)

def updateWidescreen(self, context: Context):
    if context.scene.ootCsUseWidescreen:
        context.scene.render.resolution_x = 426
    else:
        context.scene.render.resolution_x = 320
    context.scene.render.resolution_y = 240

    # force a refresh of the current frame
    previewFrameHandler(context.scene)


def updateCamBackground(self, context: Context):
    camObj = getCutsceneCamera(context.view_layer.objects.active)
    if camObj is not None:
        if context.scene.ootCsUseOpaqueCamBg:
            camObj.data.passepartout_alpha = 1.0
        else:
            camObj.data.passepartout_alpha = 0.95


def cutscene_panels_register():
    Scene.useDecompFeatures = BoolProperty(
        name="Use Decomp for Export", description="Use names and macros from decomp when exporting", default=True
    )

    Scene.exportMotionOnly = BoolProperty(
        name="Export Motion Data Only",
        description=(
            "Export everything or only the camera and actor motion data.\n"
            + "This will insert the data into the cutscene."
        ),
    )

    Scene.ootCsUseWidescreen = BoolProperty(name="Use Widescreen Camera", default=False, update=updateWidescreen)
    Scene.ootCsUseOpaqueCamBg = BoolProperty(
        name="Use Opaque Camera Background",
        description="Can be used to simulate the letterbox with widescreen mode enabled",
        default=False,
        update=updateCamBackground,
    )

    Scene.previewPlayerAge = EnumProperty(
        items=[("link_adult", "Adult", "Adult Link (170 cm)", 0), ("link_child", "Child", "Child Link (130 cm)", 1)],
        name="Player Age for Preview",
        description="For setting Link's height for preview",
        default="link_adult",
    )

    for cls in oot_cutscene_panel_classes:
        register_class(cls)


def cutscene_panels_unregister():
    del Scene.previewPlayerAge
    del Scene.ootCsUseOpaqueCamBg
    del Scene.ootCsUseWidescreen
    del Scene.exportMotionOnly
    del Scene.useDecompFeatures

    for cls in oot_cutscene_panel_classes:
        unregister_class(cls)
