import bpy


class SM64_Panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SM64"
    bl_options = {"DEFAULT_CLOSED"}

    # goal refers to the selected enum_sm64_goal_type, a different selection than this goal will filter this panel out
    goal = None
    # if this is True, the panel is hidden whenever the scene's export_type is not 'C'
    decomp_only = False
    import_panel = False

    @classmethod
    def poll(cls, context):
        sm64_props = context.scene.fast64.sm64
        if context.scene.gameEditorMode != "SM64":
            return False
        elif not cls.goal:
            return True  # Panel should always be shown
        elif cls.decomp_only and sm64_props.export_type != "C":
            return False
        elif cls.import_panel and not sm64_props.show_importing_menus:
            return False

        scene_goal = sm64_props.goal
        return scene_goal == "All" or scene_goal == cls.goal


class OOT_Panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OOT"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT"
