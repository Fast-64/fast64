tile_scroll_c = """#include <ultra64.h>
#include "game/memory.h"
#include "game/tile_scroll.h"


/*
 * Parameters:
 * dl - Which display list to modify (make sure it's passed by reference).
 *
 * cmd - Location of the gsDPSetTileSize command in the display list.
 *
 * s/t - How much to scroll.
 */

void shift_s(Gfx *dl, u32 cmd, u16 s) {
    SetTileSize *tile = dl;
    tile += cmd;
    tile->s += s;
    tile->u += s;
}

void shift_t(Gfx *dl, u32 cmd, u16 t) {
    SetTileSize *tile = dl;
    tile += cmd;
    tile->t += t;
    tile->v += t;
}

void shift_s_down(Gfx *dl, u32 cmd, u16 s) {
    SetTileSize *tile = dl;
    tile += cmd;
    tile->s -= s;
    tile->u += s;
}

void shift_t_down(Gfx *dl, u32 cmd, u16 t) {
    SetTileSize *tile = dl;
    tile += cmd;
    tile->t -= t;
    tile->v += t;
}

"""

tile_scroll_h = """#include "types.h"

#define PACK_TILESIZE(w, d) ((w << 2) + d)

typedef struct {
    int cmd:8;
    int s:12;
    int t:12;
    int pad:4;
    int i:4;
    int u:12;
    int v:12;
} SetTileSize;

void shift_s(Gfx *dl, u32 cmd, u16 s);
void shift_t(Gfx *dl, u32 cmd, u16 t);
void shift_s_down(Gfx *dl, u32 cmd, u16 s);
void shift_t_down(Gfx *dl, u32 cmd, u16 t);

"""
