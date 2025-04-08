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

from .sm64_anim import (
    sm64_anim_panel_register,
    sm64_anim_panel_unregister,
    sm64_anim_register,
    sm64_anim_unregister,
)

from .custom_cmd import custom_cmd_register, custom_cmd_unregister


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
    sm64_anim_panel_register()


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
    sm64_anim_panel_unregister()


def sm64_register(register_panels: bool):
    custom_cmd_register()
    tools_operators_register()
    tools_props_register()
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
    sm64_anim_register()
    settings_props_register()

    if register_panels:
        sm64_panel_register()


def sm64_unregister(unregister_panels: bool):
    custom_cmd_unregister()
    tools_operators_unregister()
    tools_props_unregister()
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
    sm64_anim_unregister()
    settings_props_unregister()

    if unregister_panels:
        sm64_panel_unregister()
