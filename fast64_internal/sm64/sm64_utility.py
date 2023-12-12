import os
from bpy.path import abspath

from ..utility import PluginError, filepath_checks


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


def import_rom_checks(filepath: str):
    filepath_checks(
        filepath,
        empty_error=f"Import ROM path is empty.",
        doesnt_exist_error=f"Import ROM path does not exist.",
        not_a_file_error=f"Import ROM path is not a file.",
    )
    check_expanded(filepath)


def export_rom_checks(filepath: str):
    filepath_checks(
        filepath,
        empty_error=f"Export ROM path is empty.",
        doesnt_exist_error=f"Export ROM path does not exist.",
        not_a_file_error=f"Export ROM path is not a file.",
    )
    check_expanded(filepath)


def check_expanded(filepath: str):
    filepath_checks(
        filepath,
        empty_error=f"ROM path is empty.",
        doesnt_exist_error=f"ROM path does not exist.",
        not_a_file_error=f"ROM path is not a file.",
    )

    size = os.path.getsize(filepath)
    if size < 9000000:  # check if 8MB
        raise PluginError(
            f"ROM at {filepath} is too small. You may be using an unexpanded ROM. You can expand a ROM by opening it in SM64 Editor or ROM Manager."
        )
