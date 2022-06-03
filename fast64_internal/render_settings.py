import bpy
from .utility import get_blender_to_game_scale

def on_update_sm64_render_settings(self, context: bpy.types.Context):
    renderSettings: "Fast64RenderSettings_Properties" = context.scene.fast64.renderSettings
    if renderSettings.sm64Area and renderSettings.useObjectRenderPreview:
        area: bpy.types.Object = renderSettings.sm64Area
        renderSettings.fogPreviewColor = tuple(c for c in area.area_fog_color)
        renderSettings.fogPreviewPosition = tuple(round(p) for p in area.area_fog_position)

        renderSettings.clippingPlanes = tuple(float(p) for p in area.clipPlanes)

def on_update_oot_render_settings(self, context: bpy.types.Context):
    # TODO: Update render properties from selected OOTLightProperty
    pass

def update_scene_props_from_render_settings(context: bpy.types.Context, sceneOutputs: bpy.types.NodeGroupOutput, renderSettings: "Fast64RenderSettings_Properties"):
    enableFog = int(renderSettings.enableFogPreview)
    sceneOutputs.inputs['FogEnable'].default_value = enableFog

    sceneOutputs.inputs['FogColor'].default_value = tuple(c for c in renderSettings.fogPreviewColor)
    sceneOutputs.inputs['FogNear'].default_value = renderSettings.fogPreviewPosition[0]
    sceneOutputs.inputs['FogFar'].default_value = renderSettings.fogPreviewPosition[1]

    sceneOutputs.inputs['F3D_NearClip'].default_value = float(renderSettings.clippingPlanes[0])
    sceneOutputs.inputs['F3D_FarClip'].default_value = float(renderSettings.clippingPlanes[1])

    sceneOutputs.inputs['ShadeColor'].default_value = tuple(c for c in renderSettings.lightColor)
    sceneOutputs.inputs['AmbientColor'].default_value = tuple(c for c in renderSettings.ambientColor)
    
    sceneOutputs.inputs['Blender_Game_Scale'].default_value = float(get_blender_to_game_scale(context))
    

def on_update_render_preview_nodes(self, context: bpy.types.Context):
    sceneProps = bpy.data.node_groups.get("SceneProperties")
    if sceneProps == None:
        print('Could not locate SceneProperties!')
        return

    sceneOutputs: bpy.types.NodeGroupOutput = sceneProps.nodes['Group Output']
    renderSettings: "Fast64RenderSettings_Properties" = context.scene.fast64.renderSettings
    update_scene_props_from_render_settings(context, sceneOutputs, renderSettings)

def on_update_render_settings(self, context: bpy.types.Context):
    sceneProps = bpy.data.node_groups.get("SceneProperties")
    if sceneProps == None:
        print('Could not locate sceneProps!')
        return

    sceneOutputs: bpy.types.NodeGroupOutput = sceneProps.nodes['Group Output']
    renderSettings: "Fast64RenderSettings_Properties" = context.scene.fast64.renderSettings

    match context.scene.gameEditorMode:
        case "SM64":
            on_update_sm64_render_settings(self, context)
        case "OOT":
            on_update_oot_render_settings(self, context)
        case _:
            pass

    on_update_render_preview_nodes(self, context)


def poll_sm64_area(self, object):
    return object.sm64_obj_type == "Area Root"

def poll_oot_scene(self, object):
    return object.ootEmptyType == "Scene"

class Fast64RenderSettings_Properties(bpy.types.PropertyGroup):
    enableFogPreview: bpy.props.BoolProperty(name="Enable Fog Preview", default=True, update=on_update_render_settings)
    fogPreviewColor: bpy.props.FloatVectorProperty(
        name="Fog Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(1, 1, 1, 1),
        update=on_update_render_preview_nodes
    )
    ambientColor: bpy.props.FloatVectorProperty(
        name="Ambient Light",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(0.5, 0.5, 0.5, 1),
        update=on_update_render_preview_nodes
    )
    lightColor: bpy.props.FloatVectorProperty(
        name="Light Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(1, 1, 1, 1),
        update=on_update_render_preview_nodes
    )
    # Fog Preview is int because values reflect F3D values
    fogPreviewPosition: bpy.props.IntVectorProperty(name="Fog Position", size=2, min=0, max=0x7FFFFFFF, default=(985, 1000), update=on_update_render_preview_nodes)
    # Clipping planes are float because values reflect F3D values
    clippingPlanes: bpy.props.FloatVectorProperty(name="Clipping Planes", size=2, min=0, default=(100, 30000), update=on_update_render_preview_nodes)
    useObjectRenderPreview: bpy.props.BoolProperty(name="Use Object Preview", default=True, update=on_update_render_settings)
    # SM64
    sm64Area: bpy.props.PointerProperty(name="Area Object", type=bpy.types.Object, update=on_update_sm64_render_settings, poll=poll_sm64_area)
    # OOT
    ootSceneObject: bpy.props.PointerProperty(name="Scene Object", type=bpy.types.Object, update=on_update_oot_render_settings, poll=poll_oot_scene)
