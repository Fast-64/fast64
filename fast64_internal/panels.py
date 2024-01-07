import bpy

sm64GoalImport = "Import"  # Not in enum, separate UI option
sm64GoalTypeEnum = [
    ("All", "All", "All"),
    ("Export Object/Actor/Anim", "Export Object/Actor/Anim", "Export Object/Actor/Anim"),
    ("Export Level", "Export Level", "Export Level"),
    ("Export Displaylist", "Export Displaylist", "Export Displaylist"),
    ("Export UI Image", "Export UI Image", "Export UI Image"),
]


class SM64_Panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SM64"
    bl_options = {"DEFAULT_CLOSED"}
    # goal refers to the selected sm64GoalTypeEnum, a different selection than this goal will filter this panel out
    goal = None
    # if this is True, the panel is hidden whenever the scene's exportType is not 'C'
    decomp_only = False

    @classmethod
    def poll(cls, context):
        sm64Props = bpy.context.scene.fast64.sm64
        if context.scene.gameEditorMode != "SM64":
            return False
        elif not cls.goal:
            return True  # Panel should always be shown
        elif cls.goal == sm64GoalImport:
            # Only show if importing is enabled
            return sm64Props.showImportingMenus
        elif cls.decomp_only and sm64Props.exportType != "C":
            return False

        sceneGoal = sm64Props.goal
        return sceneGoal == "All" or sceneGoal == cls.goal


class OOT_Panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OOT"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT"
