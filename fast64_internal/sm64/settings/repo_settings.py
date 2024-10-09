from typing import Any

from bpy.types import Scene, UILayout

from ...utility import draw_and_check_tab, prop_split, set_prop_if_in_data


def save_sm64_repo_settings(scene: Scene):
    world = scene.world
    data: dict[str, Any] = {}
    draw_layers: dict[str, Any] = {}
    data["draw_layers"] = draw_layers

    for layer in range(8):
        draw_layers[layer] = {
            "cycle_1": getattr(world, f"draw_layer_{layer}_cycle_1"),
            "cycle_2": getattr(world, f"draw_layer_{layer}_cycle_2"),
        }

    sm64_props = scene.fast64.sm64
    data.update(sm64_props.to_repo_settings())
    return data


def load_sm64_repo_settings(scene: Scene, data: dict[str, Any]):
    world = scene.world

    draw_layers = data.get("draw_layers", {})
    for layer in range(8):
        draw_layer = draw_layers.get(str(layer), {})
        if "cycle_1" in draw_layer:
            set_prop_if_in_data(world, f"draw_layer_{layer}_cycle_1", draw_layer, "cycle_1")
        if "cycle_2" in draw_layer:
            set_prop_if_in_data(world, f"draw_layer_{layer}_cycle_2", draw_layer, "cycle_2")

    sm64_props = scene.fast64.sm64
    sm64_props.from_repo_settings(data)
