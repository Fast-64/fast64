import bpy

from typing import Optional


class GameData:
    def __init__(self, game_editor_mode: Optional[str] = None):
        from .data import Z64_Data

        self.z64 = Z64_Data("OOT")

        if game_editor_mode is not None:
            self.update(game_editor_mode)

    def update(self, game_editor_mode: str):
        from .z64.utility import getObjectList

        if game_editor_mode is not None and game_editor_mode in {"OOT", "MM"}:
            self.z64.update(None, game_editor_mode, True)

            # ensure `currentCutsceneIndex` is set to a correct value
            if bpy.context.scene.gameEditorMode in {"OOT", "MM"}:
                for scene_obj in bpy.data.objects:
                    scene_obj.ootAlternateSceneHeaders.currentCutsceneIndex = game_data.z64.cs_index_start

                    if scene_obj.type == "EMPTY" and scene_obj.ootEmptyType == "Scene":
                        room_obj_list = getObjectList(scene_obj.children_recursive, "EMPTY", "Room")

                        for room_obj in room_obj_list:
                            room_obj.ootAlternateRoomHeaders.currentCutsceneIndex = game_data.z64.cs_index_start

            if game_editor_mode in {"OOT", "MM"} and game_editor_mode != self.z64.game:
                raise ValueError(f"ERROR: Z64 game mismatch: {game_editor_mode}, {game_data.z64.game}")


game_data = GameData()
