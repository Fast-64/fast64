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


def int_from_str(value: str):
    """Better errors than int(x, 0), supports hex, binary, octal and decimal."""
    bases = {
        "0x": (16, "hexadecimal value. \nOnly use characters [0-F] when representing base 16."),
        "0b": (2, "binary value. \nOnly use 0 or 1 when representing base 2."),
        "0o": (8, "octal value. \nOnly use characters [0-7] when representing base 8."),
    }
    decimal = (10, "decimal value. \nUse 0x for hexadecimal, 0b for binary, and 0o for octal.")

    value = value.strip()
    prefix = value[:2].lower() if len(value) > 1 else ""
    number_part = value[2:] if prefix else value
    if not number_part:
        raise ValueError("Empty value.")

    base_and_error = bases.get(prefix, decimal)
    try:
        return int(number_part, base_and_error[0])
    except ValueError as exc:
        raise ValueError(f"{value} is not a valid " + base_and_error[1]) from exc


def string_int_warning(layout: UILayout, value: str) -> bool:
    try:
        int_from_str(value)
        return True
    except Exception as exc:
        multilineLabel(layout.box(), str(exc), "ERROR")
        return False


def string_int_prop(layout: UILayout, data, prop: str, name: str, **prop_kwargs):
    prop_split(layout, data, prop, name, **prop_kwargs)
    return string_int_warning(layout, getattr(data, prop))


def check_expanded(rom: os.PathLike):
    size = os.path.getsize(rom)
    if size < 9000000:  # check if 8MB
        raise PluginError(
            f"ROM at {rom} is too small.\nYou may be using an unexpanded ROM.\nYou can expand a ROM by opening it in SM64 Editor or ROM Manager."
        )
