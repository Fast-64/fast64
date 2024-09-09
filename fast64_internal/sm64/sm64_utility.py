import os
import bpy
from bpy.types import UILayout

from ..utility import PluginError, filepath_checks, run_and_draw_errors, multilineLabel, prop_split
from .sm64_function_map import func_map


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


MIB = 1024.0**2.0
SIZE_8MIB = 8 * MIB


def check_expanded(rom: os.PathLike, include_path=True):
    filepath_checks(rom, include_path=include_path)
    size = os.path.getsize(rom)
    if size <= SIZE_8MIB:
        raise PluginError(
            "ROM " + (f"at {rom} " if include_path else "") + "is vanilla sized (8.38 MB).\n"
            "You may be using an unexpanded ROM.\n"
            "You can expand it using ROM Manager or sm64Extend."
        )


def import_rom_checks(rom: os.PathLike, include_path=True):
    filepath_checks(
        rom,
        "Import ROM path is empty.",
        "Import ROM path {}does not exist.",
        "Import ROM path {}is not a file.",
        include_path,
    )
    check_expanded(rom, include_path)


def export_rom_checks(rom: os.PathLike, include_path=True):
    filepath_checks(
        rom,
        "Export ROM path is empty.",
        "Export ROM path {}does not exist.",
        "Export ROM path {}is not a file.",
        include_path,
    )
    check_expanded(rom, include_path)


def import_rom_ui_warnings(layout: UILayout, rom: os.PathLike):
    return run_and_draw_errors(layout, import_rom_checks, rom, False)


def export_rom_ui_warnings(layout: UILayout, rom: os.PathLike):
    return run_and_draw_errors(layout, export_rom_checks, rom, False)


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
    number_part = value[2:] if prefix in bases else value
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


def string_int_prop(layout: UILayout, data, prop: str, name="", split=True, **prop_kwargs):
    if split:
        prop_split(layout, data, prop, name, **prop_kwargs)
    else:
        layout.prop(data, prop, text=name, **prop_kwargs)
    return string_int_warning(layout, getattr(data, prop))


def convert_addr_to_func(addr: str):
    if addr == "":
        raise PluginError("Empty function name/address.")
    refresh_version: str = bpy.context.scene.fast64.sm64.refresh_version
    if refresh_version.startswith("HackerSM64"):  # hacker uses refresh 13
        refresh_version = "Refresh 13"
    assert refresh_version in func_map, "Refresh version not found in function map"
    refresh_func_map = func_map[refresh_version]
    if addr.lower() in refresh_func_map:
        return refresh_func_map[addr.lower()]
    else:
        return addr
