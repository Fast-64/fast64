from bpy.types import Panel, Curve
from bpy.utils import register_class, unregister_class
from ..utility import getSceneObj, get_scene_header_props
from .properties import OOTSplineProperty


class OOTSplinePanel(Panel):
    bl_label = "Spline Inspector"
    bl_idname = "OBJECT_PT_OOT_Spline_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode in {"OOT", "MM"} and (
            context.object is not None and type(context.object.data) == Curve
        )

    def draw(self, context):
        box = self.layout.box().column()
        box.box().label(text="Spline Inspector")
        curve = context.object.data
        if curve.splines[0].type != "NURBS":
            box.label(text="Only NURBS curves are compatible.")
        else:
            sceneObj = getSceneObj(context.object)
            altSceneProp = get_scene_header_props(sceneObj, True) if sceneObj is not None else None
            splineProp: OOTSplineProperty = context.object.ootSplineProperty
            splineProp.draw_props(box, altSceneProp, context.object.name)


oot_spline_panel_classes = (OOTSplinePanel,)


def spline_panels_register():
    for cls in oot_spline_panel_classes:
        register_class(cls)


def spline_panels_unregister():
    for cls in oot_spline_panel_classes:
        unregister_class(cls)
