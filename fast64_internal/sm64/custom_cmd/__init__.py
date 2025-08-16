from .properties import props_register, props_unregister
from .operators import operators_register, operators_unregister


def custom_cmd_register():
    props_register()
    operators_register()


def custom_cmd_unregister():
    props_unregister()
    operators_unregister()
