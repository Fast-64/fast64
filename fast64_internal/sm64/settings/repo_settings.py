from typing import Any
from bpy.types import Scene


def save_sm64_repo_settings(scene: Scene):
    data: dict[str, Any] = {}

    world = scene.world

    draw_layers: dict[str, Any] = {}
    data["draw_layers"] = draw_layers

    for layer in range(8):
        draw_layers[layer] = {
            "cycle_1": getattr(world, f"draw_layer_{layer}_cycle_1"),
            "cycle_2": getattr(world, f"draw_layer_{layer}_cycle_2"),
        }

    sm64_props = scene.fast64.sm64
    data["refresh_version"] = sm64_props.refresh_version
    data["compression_format"] = sm64_props.compression_format
    data["force_extended_ram"] = sm64_props.force_extended_ram
    data["matstack_fix"] = sm64_props.matstack_fix

    return data


def load_sm64_repo_settings(scene: Scene, data: dict[str, Any]):
    world = scene.world

    draw_layers = data.get("draw_layers", {})
    for layer in range(8):
        draw_layer = draw_layers.get(str(layer), {})
        if "cycle_1" in draw_layer:
            setattr(world, f"draw_layer_{layer}_cycle_1", draw_layer["cycle_1"])
        if "cycle_2" in draw_layer:
            setattr(world, f"draw_layer_{layer}_cycle_2", draw_layer["cycle_2"])

    sm64_props = scene.fast64.sm64
    sm64_props.refresh_version = data.get("refresh_version", sm64_props.refresh_version)
    sm64_props.compression_format = data.get("compression_format", sm64_props.compression_format)
    sm64_props.force_extended_ram = data.get("force_extended_ram", sm64_props.force_extended_ram)
    sm64_props.matstack_fix = data.get("matstack_fix", sm64_props.matstack_fix)