from typing import Optional


class GameData:
    def __init__(self, game_editor_mode: Optional[str] = None):
        from .data import Z64_Data

        self.z64 = Z64_Data(game_editor_mode if game_editor_mode is not None else "MM")


game_data = GameData()
