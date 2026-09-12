"""Usually this would be panel.py but there is no actual panel since we only draw in the tools panel."""

from bpy.types import UILayout, Context

from .operators import F3D_ConvertBSDF, draw_generic_converter_props
from .properties import F3D_BSDFConverterProperties


def bsdf_converter_panel_draw(layout: UILayout, context: Context):
    col = layout.column()
    bsdf_converter: F3D_BSDFConverterProperties = context.scene.fast64.f3d.bsdf_converter
    draw_generic_converter_props(bsdf_converter, col, "", context)

    for direction in ("F3D", "BSDF"):
        box = layout.box().column()
        draw_generic_converter_props(bsdf_converter, box, direction, context)
        opposite = "BSDF" if direction == "F3D" else "F3D"
        F3D_ConvertBSDF.draw_props(
            box,
            text=f"Convert {opposite} to {direction}",
            direction=direction,
            converter_type=bsdf_converter.converter_type,
            backup=bsdf_converter.backup,
            put_alpha_into_color=bsdf_converter.put_alpha_into_color,
            use_recommended=bsdf_converter.use_recommended,
            lights_for_colors=bsdf_converter.lights_for_colors,
            default_to_fog=bsdf_converter.default_to_fog,
            set_rendermode_without_fog=bsdf_converter.set_rendermode_without_fog,
        )
