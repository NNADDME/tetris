"""
renderer.py —— 画面渲染（Renderer）
====================================================================
【职责边界】本模块只做"数据 -> 像素"的单向翻译：
    * 从不修改游戏状态，不判断规则，不处理按键。
    * 好处：想换美术风格（圆角方块、渐变、贴图）只改这个文件，逻辑一行不动。

【绘制顺序】这决定了谁盖住谁，写错了会出现"方块被网格线切碎"之类的问题
--------------------------------------------------------------------
    1 背景（整屏底色）
    2 场地底色 + 边框 + 网格线
    3 已固定的方块（来自 board.grid）
    4 幽灵方块（画在真实方块下面，半透明）
    5 当前方块
    6 右侧信息栏：下一个方块预览、分数、等级、行数、操作提示
    7 覆盖层：暂停 / 游戏结束（半透明黑 + 居中文字）
    8 pygame.display.flip()  —— 整个循环里只能调一次，在最后！

【性能小贴士】
    * 不要每帧重新 pygame.font.SysFont(...)，字体对象建一次存 self 上。
    * 纯色方块用 pygame.draw.rect 就够；想要立体感可以在左上画一条亮边、右下画暗边。
    * 如果以后要做炫光/阴影，再考虑 Surface + alpha，别一上来就优化。

【坐标换算】只有这里需要动像素，公式写在 settings.py 顶部，务必照它来：
    rect.x = BOARD_X + col * CELL_SIZE
    rect.y = BOARD_Y + row * CELL_SIZE
"""

from __future__ import annotations

from collections.abc import Iterable

import pygame

from settings import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    BOARD_X,
    BOARD_Y,
    CELL_SIZE,
    COLOR_BG,
    COLOR_BOARD_BG,
    COLOR_BORDER,
    COLOR_GHOST,
    COLOR_GRID,
    COLOR_PANEL_BG,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    COLS,
    FONT_ANTIALIAS,
    FONT_NAME,
    FONT_SIZE,
    FONT_SIZE_BIG,
    PANEL_GAP,
    PANEL_WIDTH,
    ROWS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TETROMINO_COLORS,
)
from tetromino import SHAPE_MATRICES

Cell = tuple[int, int]

def lighten(color: tuple[int, int, int], amount: int = 40) -> tuple[int, int, int]:
    """把颜色整体调亮，各通道向上限 255 靠。"""
    r, g, b = color
    return min(255, r + amount), min(255, g + amount), min(255, b + amount)


def darken(color: tuple[int, int, int], amount: int = 50) -> tuple[int, int, int]:
    """把颜色整体调暗，各通道向下限 0 靠。"""
    r, g, b = color
    return max(0, r - amount), max(0, g - amount), max(0, b - amount)


def load_font(size: int) -> pygame.font.Font:
    """加载像素字体；字体文件缺失时退回 pygame 默认字体，保证不会因为缺文件而崩。"""
    try:
        return pygame.font.Font(FONT_NAME, size)
    except (FileNotFoundError, OSError, TypeError):
        return pygame.font.Font(None, size)

class Renderer:
    """
    字段
    ------------------------------------------------------------------
    screen    : pygame.Surface   主画布
    font      : pygame.font.Font 普通字号
    font_big  : pygame.font.Font 大字号（标题/暂停/结束）
    """

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.font = load_font(FONT_SIZE)
        self.font_big = load_font(FONT_SIZE_BIG)
        self._mask = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self._mask.fill((0, 0, 0, 180))

    # ------------------------------------------------------------ 单帧入口
    def draw_frame(self, game) -> None:
        """
        画完一整帧。参数 game 是 game.Game 实例，这里只"读"它的数据：
            game.board, game.current, game.ghost_cells(),
            game.next_kind, game.score, game.level, game.lines, game.state
        调用顺序见模块开头的"绘制顺序"。
        * 想降低耦合，也可以把这些数据拆成参数传进来（但参数会很长，读起来更累）。
        """
        self.draw_background()
        self.draw_grid()
        self.draw_board(game.board)
        if game.current is not None:
            self.draw_piece(game.current.kind,game.current.cells())
            if game.show_ghost:
                self.draw_ghost(game.ghost_cells())
        self.draw_panel(game)
        if game.is_paused:
            self.draw_overlay("已暂停", "按 P 继续")
        elif game.is_over:
            self.draw_overlay("游戏结束", "按 R 重新开始")

    # ------------------------------------------------------------ 基础图元
    def cell_rect(self, col: int, row: int) -> pygame.Rect:
        """逻辑格子坐标 -> 屏幕矩形。全项目唯一的换算点。"""
        return pygame.Rect(BOARD_X+col*CELL_SIZE,BOARD_Y+row*CELL_SIZE,CELL_SIZE,CELL_SIZE)

    def draw_block(self, col: int, row: int, kind: str, ghost: bool = False) -> None:
        """
        画一个格子。
        * 颜色从 TETROMINO_COLORS[kind] 取；ghost=True 时用 COLOR_GHOST 或降低透明度。
        * 想要"砖块感"：先铺色，再在内侧画 1~2px 的亮边（简单 3D），最后描一圈深色线。
        * 想画半透明：单独建一个 Surface 设 set_alpha，再 blit 到 screen 上。
        """
        rect=self.cell_rect(col, row).inflate(-2,-2)
        color = COLOR_GHOST if ghost else TETROMINO_COLORS[kind]
        pygame.draw.rect(self.screen, color, rect)
        if not ghost:
            pygame.draw.line(self.screen, lighten(color), rect.topleft, rect.topright)  # 亮边
            pygame.draw.line(self.screen, lighten(color), rect.topleft, rect.bottomleft)
            pygame.draw.rect(self.screen, darken(color), rect, 1)  # 描边

    def draw_text(self, text: str, pos: tuple[int, int], big: bool = False,
                  color: tuple[int, int, int] = COLOR_TEXT, center: bool = False) -> pygame.Rect:
        """画一段文字并返回它的矩形（方便做居中对齐/排版）。"""
        font = self.font_big if big else self.font
        surf=font.render(text,FONT_ANTIALIAS,color)
        rect=surf.get_rect(center=pos) if center else surf.get_rect(topleft=pos)
        self.screen.blit(surf,rect)
        return rect

    # ------------------------------------------------------------ 各图层
    def draw_background(self) -> None:
        """整屏填充 COLOR_BG。"""
        self.screen.fill(COLOR_BG)

    def draw_grid(self) -> None:
        """
        画场地底色、外框和网格线。
        * 网格线画不画都行；建议用很暗的颜色，否则会抢方块的视觉。
        * 竖线 x = BOARD_X + i*CELL_SIZE，横线 y = BOARD_Y + j*CELL_SIZE，i/j 从 0 到 COLS/ROWS。
        """
        board_rect=pygame.Rect(BOARD_X,BOARD_Y,BOARD_WIDTH,BOARD_HEIGHT)
        self.screen.fill(COLOR_BOARD_BG, board_rect)
        for i in range(1,COLS):
            x=BOARD_X+i*CELL_SIZE
            pygame.draw.line(self.screen,COLOR_GRID,(x,BOARD_Y),(x,BOARD_Y+BOARD_HEIGHT))
        for i in range(1,ROWS):
            y=BOARD_Y+i*CELL_SIZE
            pygame.draw.line(self.screen,COLOR_GRID,(BOARD_X,y),(BOARD_X+BOARD_WIDTH,y))
        pygame.draw.rect(self.screen,COLOR_BORDER,board_rect,1)

    def draw_board(self, board) -> None:
        """遍历 board.occupied_cells()，调用 draw_block 画出已经固定的方块。"""
        for col,row,kind in board.occupied_cells():
            self.draw_block(col, row, kind)

    def draw_ghost(self, cells: Iterable[Cell]) -> None:
        """
        画幽灵方块（落点提示）。
        * 建议只画一个空心边框而不是实心块，否则容易和真方块混淆。
        * 如果 cells 里有 row < 0 的格子，跳过不画（屏幕外）。
        """
        for col,row in cells:
            if row<0:
                continue
            rect=self.cell_rect(col,row).inflate(-2,-2)
            pygame.draw.rect(self.screen, COLOR_GHOST, rect, 1)


    def draw_piece(self, kind: str, cells: Iterable[Cell]) -> None:
        """画当前方块：cells 来自 game.current.cells()，kind 用来取颜色。"""
        for col,row in cells:
            self.draw_block(col,row,kind)

    def draw_panel(self, game) -> None:
        """右侧信息栏：下一个方块预览 + 分数 / 等级 / 行数 + 操作提示。"""
        panel_x = BOARD_X + BOARD_WIDTH + PANEL_GAP
        rect = pygame.Rect(panel_x, BOARD_Y, PANEL_WIDTH, BOARD_HEIGHT)
        pygame.draw.rect(self.screen, COLOR_PANEL_BG, rect)
        pygame.draw.rect(self.screen, COLOR_BORDER, rect, 1)

        pad, y = 16, BOARD_Y + 16

        # 下一个方块预览：用 4x4 矩阵 + 侧栏自己的原点
        r = self.draw_text("下一个", (panel_x + pad, y), color=COLOR_TEXT_DIM)
        small = int(CELL_SIZE * 0.7)
        ox, oy = panel_x + pad + 8, r.bottom + 12
        matrix = SHAPE_MATRICES[game.next_kind]
        for rr in range(4):
            for cc in range(4):
                if matrix[rr][cc] == 1:
                    pygame.draw.rect(self.screen, TETROMINO_COLORS[game.next_kind],
                                     (ox + cc * small, oy + rr * small, small - 2, small - 2))

        # 分数 / 等级 / 行数：用返回的 rect 往下排，不用手数像素
        y = oy + 4 * small + 24
        for label, value in (("分数", game.score), ("等级", game.level), ("行数", game.lines)):
            r = self.draw_text(label, (panel_x + pad, y), color=COLOR_TEXT_DIM)
            self.draw_text(str(value), (panel_x + pad, r.bottom + 2), big=True)
            y = r.bottom + 2 + self.font_big.get_height() + 16

        # 底部操作提示：按键和说明分两列画，保证左对齐整齐
        hints = (("← →", "移动"), ("↑", "旋转"), ("空格", "硬降"), ("P", "暂停"))
        line_h = self.font.get_height() + 4
        hy = rect.bottom - pad - len(hints) * line_h
        for key, action in hints:
            self.draw_text(key, (panel_x + pad, hy))
            self.draw_text(action, (panel_x + pad + 76, hy), color=COLOR_TEXT_DIM)
            hy += line_h


    def draw_overlay(self, title: str, subtitle: str = "") -> None:
        """
        覆盖层：先铺一层半透明黑（例如 (0,0,0,180) 的 Surface），再居中写标题。
        暂停时 title="PAUSED"，结束时 title="GAME OVER"、subtitle="按 R 重新开始"。
        """
        self.screen.blit(self._mask, (0, 0))
        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        self.draw_text(title, (cx, cy - 20), big=True, center=True)
        if subtitle:
            self.draw_text(subtitle, (cx, cy + 30), color=COLOR_TEXT_DIM, center=True)
