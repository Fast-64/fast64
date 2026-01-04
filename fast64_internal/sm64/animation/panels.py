from typing import TYPE_CHECKING

from bpy.utils import register_class, unregister_class
from bpy.types import Context

from ...utility_anim import is_action_stashed, CreateAnimData, AddBasicAction, StashAction
from ...panels import SM64_Panel

from .utility import (
    get_action_props,
    get_anim_actor_name,
    get_anim_props,
    get_selected_action,
    dma_structure_context,
    get_anim_obj,
)
from .operators import SM64_ExportAnim, SM64_ExportAnimTable, SM64_AddNLATracksToTable

if TYPE_CHECKING:
    from ..settings.properties import SM64_Properties
    from ..sm64_objects import SM64_CombinedObjectProperties
    from .properties import SM64_AnimImportProperties


# Base
class AnimationPanel(SM64_Panel):
    bl_label = "SM64 Animation Inspector"
    goal = "Object/Actor/Anim"


# Base panels
class SceneAnimPanel(AnimationPanel):
    bl_idname = "SM64_PT_anim"
    bl_parent_id = bl_idname


class ObjAnimPanel(AnimationPanel):
    bl_idname = "OBJECT_PT_SM64_anim"
    bl_context = "object"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_parent_id = bl_idname


# Main tab
class SceneAnimPanelMain(SceneAnimPanel):
    bl_parent_id = ""

    def draw(self, context):
        col = self.layout.column()
        sm64_props: SM64_Properties = context.scene.fast64.sm64
        combined_props: SM64_CombinedObjectProperties = sm64_props.combined_export

        if sm64_props.export_type == "C":
            if not sm64_props.hackersm64:
                col.prop(sm64_props, "designated_prop", text="Designated Initialization for Tables")
        else:
            combined_props.draw_anim_props(col, sm64_props.export_type, dma_structure_context(context))
            SM64_ExportAnimTable.draw_props(col)
        anim_obj = get_anim_obj(context)
        if anim_obj is None:
            col.box().label(text="No selected armature/animated object")
        else:
            col.box().label(text=f'Armature "{anim_obj.name}"')


class ObjAnimPanelMain(ObjAnimPanel):
    bl_parent_id = "OBJECT_PT_context_object"

    @classmethod
    def poll(cls, context: Context):
        return get_anim_obj(context) is not None

    def draw(self, context):
        sm64_props: SM64_Properties = context.scene.fast64.sm64
        combined_props: SM64_CombinedObjectProperties = sm64_props.combined_export
        get_anim_props(context).draw_props(
            self.layout,
            sm64_props.export_type,
            combined_props.export_header_type,
            get_anim_actor_name(context),
            combined_props.export_bhv,
        )


# Action tab


class AnimationPanelAction(AnimationPanel):
    bl_label = "Action Inspector"

    def draw(self, context):
        col = self.layout.column()

        if context.object.animation_data is None:
            col.box().label(text="Select object has no animation data")
            CreateAnimData.draw_props(col)
            action = None
        else:
            col.prop(context.object.animation_data, "action", text="Selected Action")
            action = get_selected_action(context.object, False)
        if action is None:
            AddBasicAction.draw_props(col)
            return

        if not is_action_stashed(context.object, action):
            warn_col = col.column()
            StashAction.draw_props(warn_col, action=action.name)
            warn_col.alert = True

        sm64_props: SM64_Properties = context.scene.fast64.sm64
        combined_props: SM64_CombinedObjectProperties = sm64_props.combined_export
        if sm64_props.export_type != "C":
            SM64_ExportAnim.draw_props(col)
        anim_props = get_anim_props(context)

        export_seperately = get_anim_props(context).export_seperately
        if sm64_props.export_type == "C":
            export_seperately = export_seperately or combined_props.export_single_action
        elif sm64_props.export_type == "Insertable Binary":
            export_seperately = True
        get_action_props(action).draw_props(
            layout=col,
            action=action,
            specific_variant=None,
            in_table=False,
            table_elements=anim_props.elements,
            updates_table=anim_props.update_table,
            export_seperately=export_seperately,
            export_type=sm64_props.export_type,
            actor_name=get_anim_actor_name(context),
            gen_enums=anim_props.gen_enums,
            dma=dma_structure_context(context),
        )


class SceneAnimPanelAction(AnimationPanelAction, SceneAnimPanel):
    bl_idname = "SM64_PT_anim_panel_action"

    @classmethod
    def poll(cls, context: Context):
        return get_anim_obj(context) is not None and SceneAnimPanel.poll(context)


class ObjAnimPanelAction(AnimationPanelAction, ObjAnimPanel):
    bl_idname = "OBJECT_PT_SM64_anim_action"


class ObjAnimPanelTable(ObjAnimPanel):
    bl_label = "Table"
    bl_idname = "OBJECT_PT_SM64_anim_table"

    def draw(self, context):
        if SM64_AddNLATracksToTable.poll(context):
            SM64_AddNLATracksToTable.draw_props(self.layout)
        sm64_props: SM64_Properties = context.scene.fast64.sm64
        get_anim_props(context).draw_table(self.layout, sm64_props.export_type, get_anim_actor_name(context))


# Importing tab


class AnimationPanelImport(AnimationPanel):
    bl_label = "Importing"
    import_panel = True

    def draw(self, context):
        sm64_props: SM64_Properties = context.scene.fast64.sm64
        importing: SM64_AnimImportProperties = sm64_props.animation.importing
        importing.draw_props(self.layout, sm64_props.import_rom, sm64_props.decomp_path)


class SceneAnimPanelImport(SceneAnimPanel, AnimationPanelImport):
    bl_idname = "SM64_PT_anim_panel_import"

    @classmethod
    def poll(cls, context: Context):
        return get_anim_obj(context) is not None and AnimationPanelImport.poll(context)


class ObjAnimPanelImport(ObjAnimPanel, AnimationPanelImport):
    bl_idname = "OBJECT_PT_SM64_anim_panel_import"


classes = (
    ObjAnimPanelMain,
    ObjAnimPanelTable,
    ObjAnimPanelAction,
    SceneAnimPanelMain,
    SceneAnimPanelAction,
    SceneAnimPanelImport,
)


def anim_panel_register():
    for cls in classes:
        register_class(cls)


def anim_panel_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
