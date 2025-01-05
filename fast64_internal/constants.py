from typing import Optional


class GameData:
    def __init__(self, game_editor_mode: Optional[str] = None):
        from .data import OoT_Data

        self.z64 = OoT_Data()


game_data = GameData()
