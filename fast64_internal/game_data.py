from typing import Optional


class GameData:
    def __init__(self, game_editor_mode: Optional[str] = None):
        from .data import Z64_Data

        if game_editor_mode is not None and game_editor_mode in {"OOT", "MM"}:
            self.z64 = Z64_Data(game_editor_mode)
        else:
            # default value to avoid issues
            self.z64 = Z64_Data("OOT")


game_data = GameData()
