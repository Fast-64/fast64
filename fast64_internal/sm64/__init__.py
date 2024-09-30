from bpy.types import PropertyGroup
from bpy.props import PointerProperty
from bpy.utils import register_class, unregister_class

from .settings import (
    settings_props_register,
    settings_props_unregister,
    settings_panels_register,
    settings_panels_unregister,
)

from .tools import (
    tools_operators_register,
    tools_operators_unregister,
    tools_props_register,
    tools_props_unregister,
    tools_panels_register,
    tools_panels_unregister,
)

from .sm64_collision import (
    sm64_col_panel_register,
    sm64_col_panel_unregister,
    sm64_col_register,
    sm64_col_unregister,
)

from .sm64_geolayout_bone import (
    sm64_bone_panel_register,
    sm64_bone_panel_unregister,
    sm64_bone_register,
    sm64_bone_unregister,
)

from .sm64_camera import (
    sm64_cam_panel_register,
    sm64_cam_panel_unregister,
    sm64_cam_register,
    sm64_cam_unregister,
)

from .sm64_objects import (
    SM64_CombinedObjectProperties,
    sm64_obj_panel_register,
    sm64_obj_panel_unregister,
    sm64_obj_register,
    sm64_obj_unregister,
)

from .sm64_geolayout_parser import (
    sm64_geo_parser_panel_register,
    sm64_geo_parser_panel_unregister,
    sm64_geo_parser_register,
    sm64_geo_parser_unregister,
)

from .sm64_geolayout_writer import (
    sm64_geo_writer_panel_register,
    sm64_geo_writer_panel_unregister,
    sm64_geo_writer_register,
    sm64_geo_writer_unregister,
)

from .sm64_level_writer import (
    sm64_level_register,
    sm64_level_unregister,
)

from .sm64_spline import (
    sm64_spline_panel_register,
    sm64_spline_panel_unregister,
    sm64_spline_register,
    sm64_spline_unregister,
)

from .sm64_f3d_parser import (
    sm64_dl_parser_panel_register,
    sm64_dl_parser_panel_unregister,
    sm64_dl_parser_register,
    sm64_dl_parser_unregister,
)

from .sm64_f3d_writer import (
    sm64_dl_writer_panel_register,
    sm64_dl_writer_panel_unregister,
    sm64_dl_writer_register,
    sm64_dl_writer_unregister,
)

from .animation import (
    anim_panel_register,
    anim_panel_unregister,
    anim_register,
    anim_unregister,
    SM64_ActionAnimProperty,
)


class SM64_ActionProperty(PropertyGroup):
    """
    Properties in Action.fast64.sm64.
    """

    animation: PointerProperty(type=SM64_ActionAnimProperty, name="SM64 Properties")


def sm64_panel_register():
    settings_panels_register()
    tools_panels_register()
    sm64_col_panel_register()
    sm64_bone_panel_register()
    sm64_cam_panel_register()
    sm64_obj_panel_register()
    sm64_geo_parser_panel_register()
    sm64_geo_writer_panel_register()
    sm64_spline_panel_register()
    sm64_dl_writer_panel_register()
    sm64_dl_parser_panel_register()
    anim_panel_register()


def sm64_panel_unregister():
    settings_panels_unregister()
    tools_panels_unregister()
    sm64_col_panel_unregister()
    sm64_bone_panel_unregister()
    sm64_cam_panel_unregister()
    sm64_obj_panel_unregister()
    sm64_geo_parser_panel_unregister()
    sm64_geo_writer_panel_unregister()
    sm64_spline_panel_unregister()
    sm64_dl_writer_panel_unregister()
    sm64_dl_parser_panel_unregister()
    anim_panel_unregister()


def sm64_register(register_panels: bool):
    tools_operators_register()
    tools_props_register()
    anim_register()
    sm64_col_register()
    sm64_bone_register()
    sm64_cam_register()
    sm64_obj_register()
    sm64_geo_parser_register()
    sm64_geo_writer_register()
    sm64_level_register()
    sm64_spline_register()
    sm64_dl_writer_register()
    sm64_dl_parser_register()
    settings_props_register()
    register_class(SM64_ActionProperty)

    if register_panels:
        sm64_panel_register()


def sm64_unregister(unregister_panels: bool):
    tools_operators_unregister()
    tools_props_unregister()
    anim_unregister()
    sm64_col_unregister()
    sm64_bone_unregister()
    sm64_cam_unregister()
    sm64_obj_unregister()
    sm64_geo_parser_unregister()
    sm64_geo_writer_unregister()
    sm64_level_unregister()
    sm64_spline_unregister()
    sm64_dl_writer_unregister()
    sm64_dl_parser_unregister()
    settings_props_unregister()
    unregister_class(SM64_ActionProperty)

    if unregister_panels:
        sm64_panel_unregister()
