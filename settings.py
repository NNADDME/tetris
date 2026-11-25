"""
settings.py —— 全局配置
====================================================================
所有"可以调的数字"都集中在这个文件里，其他模块只 import、不硬编码。
好处：改窗口大小、改下落速度、改配色、改按键，只动这一个文件。

【坐标约定】全项目统一，这是最容易出错的地方，先定死
--------------------------------------------------------------------
1) 逻辑坐标（游戏世界）：格子坐标 (col, row)
   * col 从左到右：0 .. COLS-1
   * row 从上到下：0 .. ROWS-1   （row = 0 是最上面一行）
   * Board.grid / Tetromino.cells() 里全部用这套坐标，绝不出现像素。

2) 像素坐标（屏幕）：只有 Renderer 用
   * pixel_x = BOARD_X + col * CELL_SIZE
   * pixel_y = BOARD_Y + row * CELL_SIZE
   逻辑层完全不知道像素存在 -> 以后想换分辨率/加缩放，只改这一处换算。

【屏幕布局草图】
   +--------------------------------------------+
   |  MARGIN                                    |
   |   +------------------+   +--------------+   |
   |   |   棋盘 BOARD     |   | 侧栏 PANEL   |   |
   |   |  COLS x CELL     |   | 下一个/分数  |   |
   |   |  ROWS x CELL     |   | 等级/行数    |   |
   |   +------------------+   +--------------+   |
   |                                            |
   +--------------------------------------------+
"""

from pathlib import Path

import pygame  # 只用它的按键常量（K_LEFT 等），不需要 pygame.init()

# 项目根目录，用来拼字体等资源文件的位置（从任何目录启动都能找到）
BASE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------- 窗口 / 帧率
FPS = 60                      # 主循环最高帧率；游戏逻辑用 dt 计时，不依赖帧率
CAPTION = "Tetris - pygame"

# ---------------------------------------------------------------- 棋盘尺寸
CELL_SIZE = 32                # 一个格子多少像素（改它整盘等比缩放）
COLS = 10                     # 俄罗斯方块标准场地宽 10 列
ROWS = 20                     # 标准场地高 20 行

MARGIN = 24                   # 棋盘四周留白
PANEL_GAP = 16                # 棋盘与侧栏之间的间距
PANEL_WIDTH = 220             # 右侧信息栏宽度

BOARD_WIDTH = COLS * CELL_SIZE
BOARD_HEIGHT = ROWS * CELL_SIZE
BOARD_X = MARGIN              # 棋盘左上角像素坐标
BOARD_Y = MARGIN

SCREEN_WIDTH = BOARD_X * 2 + BOARD_WIDTH + PANEL_GAP + PANEL_WIDTH
SCREEN_HEIGHT = BOARD_Y * 2 + BOARD_HEIGHT

# ---------------------------------------------------------------- 颜色
COLOR_BG = (18, 18, 24)        # 整个窗口底色
COLOR_BOARD_BG = (10, 10, 14)  # 场地底色
COLOR_GRID = (38, 38, 50)      # 网格线
COLOR_BORDER = (90, 90, 112)   # 场地边框
COLOR_PANEL_BG = (26, 26, 34)  # 侧栏底色
COLOR_TEXT = (235, 235, 240)
COLOR_TEXT_DIM = (150, 150, 168)
COLOR_GHOST = (110, 110, 132)  # 幽灵方块（落点预览）颜色

# 每种方块的主题色：board 里只存形状代号 "I"/"O"/…，渲染时来这里取色
TETROMINO_COLORS = {
    "I": (0, 200, 220),
    "O": (230, 200, 60),
    "T": (170, 90, 200),
    "S": (90, 200, 90),
    "Z": (220, 80, 80),
    "J": (70, 120, 230),
    "L": (235, 150, 60),
}

# 空格子用什么表示（Board.grid 里存 None 或形状代号）
EMPTY_CELL = None

# ---------------------------------------------------------------- 下落节奏
BASE_FALL_INTERVAL_MS = 800    # 1 级时每 800ms 自动下落一格
SPEED_UP_FACTOR = 0.82         # 每升一级，间隔乘以该系数（越小越快）
MIN_FALL_INTERVAL_MS = 80      # 速度上限，别快到不可玩
LINES_PER_LEVEL = 10           # 每消 10 行升 1 级
LOCK_DELAY_MS = 0              # >0 表示落地后还能再微调这么多毫秒才锁定（进阶，可先设 0）

# ---------------------------------------------------------------- 计分
LINE_SCORES = {1: 100, 2: 300, 3: 500, 4: 800}  # 一次消 1/2/3/4 行
SOFT_DROP_SCORE_PER_CELL = 1     # 按 ↓ 每手动下落一格加分
HARD_DROP_SCORE_PER_CELL = 2     # 空格硬降，按落差格数加分

# ---------------------------------------------------------------- 字体
# 像素风中文字体 ZPix（最像素）：https://github.com/SolidZORO/zpix-pixel-font
# 授权：个人项目、教育项目免费；商业产品需向作者购买授权（若要商用请换成 OFL 授权的像素字体）。
# 文件放在 assets/fonts/zpix.ttf；找不到时 renderer 会自动退回 pygame 默认字体（那种情况下中文是方块）。
FONT_NAME = str(BASE_DIR / "assets" / "fonts" / "zpix.ttf")
FONT_SIZE = 24        # ZPix 的设计尺寸是 12px，用 12 的整数倍（24/36）才不会被插值糊掉
FONT_SIZE_BIG = 36
FONT_ANTIALIAS = False   # 像素字体必须关抗锯齿，否则笔画边缘会发虚

# ---------------------------------------------------------------- 按键映射
# 想改成 WASD，只改这里
KEY_MOVE_LEFT = pygame.K_LEFT
KEY_MOVE_RIGHT = pygame.K_RIGHT
KEY_SOFT_DROP = pygame.K_DOWN      # 按住加速下落
KEY_HARD_DROP = pygame.K_SPACE     # 瞬间落底
KEY_ROTATE_CW = pygame.K_UP        # 顺时针
KEY_ROTATE_CCW = pygame.K_z        # 逆时针
KEY_RENDER_GHOST = pygame.K_g      # 开启/关闭幽灵方块
KEY_PAUSE = pygame.K_p
KEY_RESTART = pygame.K_r           # 游戏结束后重开
KEY_QUIT = pygame.K_ESCAPE

# 按住左右键的连续移动（DAS：Delayed Auto Shift），进阶功能
KEY_REPEAT_DELAY_MS = 170          # 按住多久后开始连续移动
KEY_REPEAT_INTERVAL_MS = 50        # 之后每隔多久移动一格
