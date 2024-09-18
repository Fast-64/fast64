from typing import Any

from bpy.types import Scene, UILayout

from ...utility import draw_and_check_tab, prop_split


def save_sm64_repo_settings(scene: Scene):
    world = scene.world
    data: dict[str, Any] = {}
    data["draw_layers"] = world.fast64.sm64.draw_layers.to_dict()

    sm64_props = scene.fast64.sm64
    data["refresh_version"] = sm64_props.refresh_version
    data["compression_format"] = sm64_props.compression_format
    data["force_extended_ram"] = sm64_props.force_extended_ram
    data["matstack_fix"] = sm64_props.matstack_fix

    return data


def load_sm64_repo_settings(scene: Scene, data: dict[str, Any]):
    world = scene.world

    world.fast64.sm64.draw_layers.from_dict(data.get("draw_layers", {}))

    sm64_props = scene.fast64.sm64
    sm64_props.refresh_version = data.get("refresh_version", sm64_props.refresh_version)
    sm64_props.compression_format = data.get("compression_format", sm64_props.compression_format)
    sm64_props.force_extended_ram = data.get("force_extended_ram", sm64_props.force_extended_ram)
    sm64_props.matstack_fix = data.get("matstack_fix", sm64_props.matstack_fix)


def draw_repo_settings(scene: Scene, layout: UILayout):
    col = layout.column()
    sm64_props = scene.fast64.sm64
    if not draw_and_check_tab(col, sm64_props, "sm64_repo_settings_tab", icon="PROPERTIES"):
        return

    prop_split(col, sm64_props, "compression_format", "Compression Format")
    prop_split(col, sm64_props, "refresh_version", "Refresh (Function Map)")
    col.prop(sm64_props, "force_extended_ram")
    col.prop(sm64_props, "matstack_fix")

    col.label(text="See Fast64 repo settings for general settings", icon="INFO")
