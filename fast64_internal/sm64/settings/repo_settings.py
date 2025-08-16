from typing import Any

from bpy.types import Scene, UILayout

from ...utility import draw_and_check_tab, prop_split, set_prop_if_in_data


def save_sm64_repo_settings(scene: Scene):
    data: dict[str, Any] = {}
    data["draw_layers"] = scene.fast64.sm64.draw_layers.to_dict()

    sm64_props = scene.fast64.sm64
    data.update(sm64_props.to_repo_settings())
    return data


def load_sm64_repo_settings(scene: Scene, data: dict[str, Any]):
    if "draw_layers" in data:
        scene.fast64.sm64.draw_layers.from_dict(data["draw_layers"])

    sm64_props = scene.fast64.sm64
    sm64_props.from_repo_settings(data)
