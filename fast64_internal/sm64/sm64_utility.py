import os
from bpy.types import UILayout
from bpy.path import abspath

from ..utility import PluginError, filepath_checks, multilineLabel, prop_split


def starSelectWarning(operator, fileStatus):
    if fileStatus is not None and not fileStatus.starSelectC:
        operator.report({"WARNING"}, "star_select.c not found, skipping star select scrolling.")


def cameraWarning(operator, fileStatus):
    if fileStatus is not None and not fileStatus.cameraC:
        operator.report({"WARNING"}, "camera.c not found, skipping camera volume and zoom mask exporting.")


ULTRA_SM64_MEMORY_C = "src/boot/memory.c"
SM64_MEMORY_C = "src/game/memory.c"


def getMemoryCFilePath(decompDir):
    isUltra = os.path.exists(os.path.join(decompDir, ULTRA_SM64_MEMORY_C))
    relPath = ULTRA_SM64_MEMORY_C if isUltra else SM64_MEMORY_C
    return os.path.join(decompDir, relPath)


def import_rom_checks(rom: os.PathLike):
    filepath_checks(
        rom,
        empty_error="Import ROM path is empty.",
        doesnt_exist_error="Import ROM path does not exist.",
        not_a_file_error="Import ROM path is not a file.",
    )
    check_expanded(rom)


def export_rom_checks(rom: os.PathLike):
    filepath_checks(
        rom,
        empty_error="Export ROM path is empty.",
        doesnt_exist_error="Export ROM path does not exist.",
        not_a_file_error="Export ROM path is not a file.",
    )
    check_expanded(rom)


def import_rom_ui_warnings(layout: UILayout, rom: os.PathLike) -> bool:
    try:
        import_rom_checks(abspath(rom))
        return True
    except Exception as exc:
        multilineLabel(layout.box(), str(exc), "ERROR")
        return False


def export_rom_ui_warnings(layout: UILayout, rom: os.PathLike) -> bool:
    try:
        export_rom_checks(abspath(rom))
        return True
    except Exception as exc:
        multilineLabel(layout.box(), str(exc), "ERROR")
        return False


def is_valid_int(value: str):
    try:
        int(value, 0)
        return True
    except ValueError as exc:
        return False


def string_int_warning(layout: UILayout, value: str):
    if value:
        if is_valid_int(value):
            return True
        multilineLabel(
            layout.box(),
            "Invalid integer\nUse 0x for hexadecimal, 0b for bytes.\nDon´t use decimals, don´t use trailing zeros.",
            "ERROR",
        )
    else:
        layout.box().label(text="Empty Number", icon="ERROR")
    return False


def string_int_prop(layout: UILayout, data, prop: str, name: str, **prop_args):
    prop_split(layout, data, prop, name, **prop_args)
    return string_int_warning(layout, getattr(data, prop))


def check_expanded(rom: os.PathLike):
    size = os.path.getsize(rom)
    if size < 9000000:  # check if 8MB
        raise PluginError(
            f"ROM at {rom} is too small.\nYou may be using an unexpanded ROM.\nYou can expand a ROM by opening it in SM64 Editor or ROM Manager."
        )
