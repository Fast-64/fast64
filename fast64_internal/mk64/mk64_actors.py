import math, bpy, mathutils
import os
from bpy.utils import register_class, unregister_class
from ..panels import MK64_Panel



enumModelIDs = [
    ("Custom", "Custom", "Custom"),
    ("ITEMBOX", "itembox", "itembox"),
    ("FOLIAGE", "foliage", "foliage"),
    ("FALLING_ROCK", "fallingRocks", "fallingRocks"),
    ("PALM_TREES", "palmTrees", "palmTrees"),
    ("PIRANHA_PLANT", "piranhaPlant", "piranhaPlant"),
    ("Cow", "cow", "cow"),
]

class SearchModelIDEnumOperator(bpy.types.Operator):
    bl_idname = "object.search_model_id_enum_operator"
    bl_label = "Search Model IDs"
    bl_property = "mk64_model_enum"
    bl_options = {"REGISTER", "UNDO"}

    mk64_model_enum: bpy.props.EnumProperty(items=enumModelIDs)

    def execute(self, context):
        context.object.mk64_model_enum = self.mk64_model_enum
        bpy.context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.mk64_model_enum)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class MK64ObjectPanel(bpy.types.Panel):
    bl_label = "Object Inspector"
    bl_idname = "OBJECT_PT_MK64_Object_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "MK64" and (
            context.object is not None and context.object.type == "EMPTY"
        )

    def draw_inline_obj(self, box: bpy.types.UILayout, obj: bpy.types.Object):
        obj_details: InlineGeolayoutObjConfig = inlineGeoLayoutObjects.get(obj.mk64_obj_type)

        # display transformation warnings
        warnings = set()
        if obj_details.uses_scale and not obj_scale_is_unified(obj):
            warnings.add("Object's scale must all be the same exact value (e.g. 2, 2, 2)")

        if not obj_details.uses_scale and not all_values_equal_x(obj.scale, 1):
            warnings.add("Object's scale values must all be set to 1")

        loc = obj.matrix_local.decompose()[0]
        if not obj_details.uses_location and not all_values_equal_x(loc, 0):
            warnings.add("Object's relative location must be set to 0")

        if not obj_details.uses_rotation and not all_values_equal_x(obj.rotation_euler, 0):
            warnings.add("Object's rotations must be set to 0")

        if len(warnings):
            warning_box = box.box()
            warning_box.alert = True
            warning_box.label(text="Warning: Unexpected export results from these issues:", icon="ERROR")
            for warning in warnings:
                warning_box.label(text=warning, icon="ERROR")
            warning_box.label(text=f'Relative location: {", ".join([str(l) for l in loc])}')

        if obj.mk64_obj_type == "Geo ASM":
            prop_split(box, obj.fast64.mk64.geo_asm, "func", "Function")
            prop_split(box, obj.fast64.mk64.geo_asm, "param", "Parameter")
            return

        elif obj.mk64_obj_type == "Custom Geo Command":
            prop_split(box, obj, "customGeoCommand", "Geo Macro")
            prop_split(box, obj, "customGeoCommandArgs", "Parameters")
            return

        if obj_details.can_have_dl:
            prop_split(box, obj, "draw_layer_static", "Draw Layer")

            if not obj_details.must_have_dl:
                prop_split(box, obj, "useDLReference", "Use DL Reference")

            if obj_details.must_have_dl or obj.useDLReference:
                # option to specify a mesh instead of string reference
                prop_split(box, obj, "dlReference", "Displaylist variable or hex address")

        if obj_details.must_have_geo:
            prop_split(box, obj, "geoReference", "Geolayout variable or hex address")

        if obj_details.uses_rotation or obj_details.uses_location or obj_details.uses_scale:
            info_box = box.box()
            info_box.label(text="Note: uses empty object's:")
            if obj_details.uses_location:
                info_box.label(text="Location", icon="DOT")
            if obj_details.uses_rotation:
                info_box.label(text="Rotation", icon="DOT")
            if obj_details.uses_scale:
                info_box.label(text="Scale", icon="DOT")

        if len(obj.children):
            if checkIsMK64PreInlineGeoLayout(obj.mk64_obj_type):
                box.box().label(text="Children of this object will just be the following geo commands.")
            else:
                box.box().label(text="Children of this object will be wrapped in GEO_OPEN_NODE and GEO_CLOSE_NODE.")

    def draw_behavior_params(self, obj: bpy.types.Object, parent_box: bpy.types.UILayout):
        game_object = obj.fast64.mk64.game_object  # .bparams
        parent_box.separator()
        box = parent_box.box()
        box.label(text="Behavior Parameters")

        box.prop(game_object, "use_individual_params", text="Use Individual Behavior Params")

        if game_object.use_individual_params:
            individuals = box.box()
            individuals.label(text="Individual Behavior Parameters")
            column = individuals.column()
            for i in range(1, 5):
                row = column.row()
                row.prop(game_object, f"bparam{i}", text=f"Param {i}")
            individuals.separator(factor=0.25)
            individuals.label(text=f"Result: {game_object.get_combined_bparams()}")
        else:
            box.separator(factor=0.5)
            box.label(text="All Behavior Parameters")
            box.prop(game_object, "bparams", text="")
            parent_box.separator()

    def draw(self, context):
        prop_split(self.layout, context.scene, "gameEditorMode", "Game")
        box = self.layout.box().column()
        column = self.layout.box().column()  # added just for puppycam trigger importing
        box.box().label(text="MK64 Object Inspector")
        obj = context.object
        prop_split(box, obj, "mk64_obj_type", "Object Type")
        if obj.mk64_obj_type == "Actor":
            prop_split(box, obj, "mk64_model_enum", "Model")
            if obj.mk64_model_enum == "Custom":
                prop_split(box, obj, "mk64_obj_model", "Model ID")
            box.operator(SearchModelIDEnumOperator.bl_idname, icon="VIEWZOOM")
            box.box().label(text="Model IDs defined in include/model_ids.h.")
            prop_split(box, obj, "mk64_behaviour_enum", "Behaviour")
            if obj.mk64_behaviour_enum == "Custom":
                prop_split(box, obj, "mk64_obj_behaviour", "Behaviour Name")
            box.operator(SearchBehaviourEnumOperator.bl_idname, icon="VIEWZOOM")
            behaviourLabel = box.box()
            behaviourLabel.label(text="Behaviours defined in include/behaviour_data.h.")
            behaviourLabel.label(text="Actual contents in data/behaviour_data.c.")
            self.draw_behavior_params(obj, box)
            self.draw_acts(obj, box)

        elif obj.mk64_obj_type == "None":
            box.box().label(text="This can be used as an empty transform node in a geolayout hierarchy.")

    def draw_acts(self, obj, layout):
        layout.label(text="Acts")
        acts = layout.row()
        self.draw_act(obj, acts, 1)
        self.draw_act(obj, acts, 2)
        self.draw_act(obj, acts, 3)
        self.draw_act(obj, acts, 4)
        self.draw_act(obj, acts, 5)
        self.draw_act(obj, acts, 6)

    def draw_act(self, obj, layout, value):
        layout = layout.column()
        layout.label(text=str(value))
        layout.prop(obj, "mk64_obj_use_act" + str(value), text="")


class MK64_CombinedObjectPanel(MK64_Panel):
    bl_idname = "MK64_PT_export_combined_object"
    bl_label = "MK64 Combined Exporter"
    decomp_only = True

    def draw(self, context):
        col = self.layout.column()
        context.scene.fast64.mk64.combined_export.draw_props(col)


mk64_obj_panel_classes = (MK64ObjectPanel, MK64_CombinedObjectPanel)

def mk64_obj_panel_register():
    for cls in mk64_obj_panel_classes:
        register_class(cls)


def mk64_obj_panel_unregister():
    for cls in mk64_obj_panel_classes:
        unregister_class(cls)
