from typing import Optional


class GameData:
    def __init__(self, game_editor_mode: Optional[str] = None):
        from .data import Z64_Data

        self.z64 = Z64_Data("OOT")

        if game_editor_mode is not None:
            self.update(game_editor_mode)

    def update(self, game_editor_mode: str):
        if game_editor_mode is not None and game_editor_mode in {"OOT", "MM"}:
            self.z64.update(None, game_editor_mode, True)

            if game_editor_mode in {"OOT", "MM"} and game_editor_mode != self.z64.game:
                raise ValueError(f"ERROR: Z64 game mismatch: {game_editor_mode}, {game_data.z64.game}")


game_data = GameData()
