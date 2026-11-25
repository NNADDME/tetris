"""
game.py —— 游戏规则与流程（Game）

持有全部游戏状态（场地、当前方块、下一个方块、分数、等级、状态机），接收"意图"和时间，
不接触任何绘制代码，因此可以脱离窗口单独测试。
时间一律按毫秒推进：主循环把 dt 传进 update()，与帧率无关。
"""

from __future__ import annotations

from enum import Enum, auto

import pygame

from board import Board
from settings import (
    BASE_FALL_INTERVAL_MS,
    HARD_DROP_SCORE_PER_CELL,
    KEY_HARD_DROP,
    KEY_MOVE_LEFT,
    KEY_MOVE_RIGHT,
    KEY_PAUSE,
    KEY_RENDER_GHOST,
    KEY_REPEAT_DELAY_MS,
    KEY_REPEAT_INTERVAL_MS,
    KEY_RESTART,
    KEY_ROTATE_CCW,
    KEY_ROTATE_CW,
    KEY_SOFT_DROP,
    LINE_SCORES,
    LINES_PER_LEVEL,
    MIN_FALL_INTERVAL_MS,
    SOFT_DROP_SCORE_PER_CELL,
    SPEED_UP_FACTOR,
)
from tetromino import Cell, SevenBag, Tetromino


class GameState(Enum):
    """游戏状态：进行中 / 暂停 / 结束。"""
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()


class Game:
    """
    board          : Board            场地
    current        : Tetromino | None 当前下落的方块
    next_kind      : str              下一个方块代号（侧栏预览用）
    score          : int
    lines          : int              累计消行数，等级由它算出
    level          : int              从 1 开始
    state          : GameState
    _fall_accum_ms : int              距下一次自动下落的累计时间
    show_ghost          : bool             是否显示幽灵方块
    """

    # 旋转踢墙的试探顺序：原地 -> 左右各挪一两格 -> 再往上顶一格
    WALL_KICKS: tuple[Cell, ...] = ((0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1))

    def __init__(self) -> None:
        self.board = Board()
        self.bag = SevenBag()
        self.show_ghost = False
        self.reset()

    def reset(self) -> None:
        """回到开局：清空场地、分数等级归零、状态设为 PLAYING，并生成第一个方块。"""
        self.board.reset()
        self.bag = SevenBag()
        self.score=0
        self.lines=0
        self.level=1
        self.state=GameState.PLAYING
        self.current = None
        self.next_kind = self.bag.next_kind()
        # 长按连发（DAS）的状态
        self._held_dirs: set[int] = set()          # 现在按住的方向：-1 左 / +1 右
        self._das_dir = 0                          # 正在连发的方向，0 表示不连发
        self._das_accum_ms = 0                     # 距下一次连发累计的时间
        self._das_gap_ms = KEY_REPEAT_DELAY_MS     # 下一次连发要等的间隔（首次是延迟）
        self._spawn()

    def handle_event(self, event: pygame.event.Event) -> None:
        """把按键事件翻译成游戏动作；KEYDOWN / KEYUP 都要处理（KEYUP 决定什么时候停止连发）。"""
        if event.type == pygame.KEYUP:
            if event.key == KEY_MOVE_LEFT:
                self._stop_repeat(-1)
            elif event.key == KEY_MOVE_RIGHT:
                self._stop_repeat(1)
            return

        if event.type != pygame.KEYDOWN:
            return

        key=event.key
        if self.is_over:
            if key==KEY_RESTART:
                self.reset()
            return

        if key==KEY_MOVE_LEFT:
            self._start_repeat(-1)
        elif key==KEY_MOVE_RIGHT:
            self._start_repeat(1)
        elif key==KEY_SOFT_DROP:
            self.soft_drop()
        elif key==KEY_HARD_DROP:
            self.hard_drop()
        elif key==KEY_ROTATE_CW:
            self.rotate()
        elif key==KEY_ROTATE_CCW:
            self.rotate(False)
        elif key==KEY_RENDER_GHOST:
            self.show_ghost=not self.show_ghost
        elif key==KEY_PAUSE:
            self.toggle_pause()
        elif key==KEY_RESTART:
            self.reset()

    def update(self, dt_ms: int) -> None:
        """按时间推进游戏：累计够一个下落间隔就下移一格，落地则锁定、消行、出新方块。"""
        if not self.is_playing or self.current is None:
            return
        dt=min(dt_ms,100)
        self._update_das(dt)
        self._fall_accum_ms+=dt
        while self._fall_accum_ms>=self.fall_interval_ms:
            self._fall_accum_ms-=self.fall_interval_ms
            if not self._step_down():
                self._lock()
                break

    def move(self, d_col: int) -> bool:
        """左右平移一格；撞墙或撞到已有方块时回退并返回 False。"""
        if not self.is_playing or self.current is None:
            return False

        self.current.move(d_col,0)
        if self.board.can_place(self.current.cells()):
            return True
        self.current.move(-d_col,0)
        return False

    def _start_repeat(self, d_col: int) -> None:
        """按下左右键：立刻走一格，然后开始累积长按时长。"""
        self._held_dirs.add(d_col)
        self._das_dir = d_col
        self._das_accum_ms = 0
        self._das_gap_ms = KEY_REPEAT_DELAY_MS
        self.move(d_col)

    def _stop_repeat(self, d_col: int) -> None:
        """松开左右键：松开的是当前方向时，切到另一个还按着的方向（没有就停下）。"""
        self._held_dirs.discard(d_col)
        if self._das_dir != d_col:
            return
        self._das_dir = next(iter(self._held_dirs), 0)
        self._das_accum_ms = 0
        # 换方向时不用再等一次延迟，直接进入重复节奏
        self._das_gap_ms = KEY_REPEAT_INTERVAL_MS

    def _update_das(self, dt_ms: int) -> None:
        """长按左右键的连续移动（DAS）：先等 KEY_REPEAT_DELAY_MS，之后每 KEY_REPEAT_INTERVAL_MS 走一格。"""
        if self._das_dir == 0:
            return

        self._das_accum_ms += dt_ms
        gap = max(1, self._das_gap_ms)          # 防止被配成 0 导致死循环
        while self._das_accum_ms >= gap:
            self._das_accum_ms -= gap
            if not self.move(self._das_dir):
                self._das_accum_ms = 0          # 撞墙了就别攒时间
                break
            self._das_gap_ms = KEY_REPEAT_INTERVAL_MS
            gap = max(1, self._das_gap_ms)

    def rotate(self, clockwise: bool = True) -> bool:
        """旋转当前方块，按 WALL_KICKS 依次试探贴墙偏移；成功则采用并返回 True，
        全部位置都碰撞时保持原状并返回 False。"""
        if not self.is_playing or self.current is None:
            return False

        matrix=self.current.rotated_matrix(clockwise)
        for dx, dy in self.WALL_KICKS:
            col=self.current.col+dx
            row=self.current.row+dy
            if self.board.can_place(Tetromino.cells_at(matrix,col,row)):
                self.current.apply(matrix,col,row)
                return True
        return False

    def soft_drop(self) -> bool:
        """软降：手动下移一格，成功时加 SOFT_DROP_SCORE_PER_CELL 分。"""
        if not self.is_playing or self.current is None:
            return False

        if self._step_down():
            self.score+=SOFT_DROP_SCORE_PER_CELL
            return True
        return False

    def hard_drop(self) -> None:
        """硬降：一次落到不能再落，按落差加分后立刻锁定。"""
        if not self.is_playing or self.current is None:
            return

        drop=self.board.drop_distance(self.current.cells())
        self.current.move(0,drop)
        self.score+=HARD_DROP_SCORE_PER_CELL*drop
        self._lock()

    def toggle_pause(self) -> None:
        """在 PLAYING 与 PAUSED 之间切换；GAME_OVER 状态下无效。"""
        if self.state==GameState.GAME_OVER:
            return
        if self.state==GameState.PLAYING:
            self.state=GameState.PAUSED
        elif self.state==GameState.PAUSED:
            self.state=GameState.PLAYING

    def _spawn(self) -> None:
        """把 next_kind 变成当前方块，再抽一个新的 next_kind；出生位置就放不下则游戏结束。"""
        self._fall_accum_ms = 0
        self.current=Tetromino.spawn(self.next_kind)
        self.next_kind=self.bag.next_kind()
        if not self.board.can_place(self.current.cells()):
            self.state=GameState.GAME_OVER

    def _step_down(self) -> bool:
        """尝试下移一格；成功返回 True，已贴底则回退并返回 False。
        注意它只负责移动，是否锁定由调用方决定（update 会锁，soft_drop 不会）。"""
        self.current.move(0,1)
        if self.board.can_place(self.current.cells()):
            return True
        self.current.move(0,-1)
        return False

    def _lock(self) -> None:
        """锁定当前方块：写进场地、按消行数加分升级，然后生成下一个方块。"""
        self._fall_accum_ms=0
        cleared=self.board.lock(self.current.kind,self.current.cells())
        self._apply_line_clear(cleared)
        self._spawn()

    def _apply_line_clear(self, cleared: int) -> None:
        """按消行数加分、累计 lines，并由 lines 推算等级。"""
        if cleared <= 0:
            return
        self.lines += cleared
        self.score += LINE_SCORES[cleared]
        self.level = 1 + self.lines // LINES_PER_LEVEL

    def ghost_cells(self) -> list[Cell]:
        """落点预览：当前方块一直下落到不能再落时所占据的格子，供 Renderer 画幽灵方块。"""
        if self.current is None:
            return []
        d=self.board.drop_distance(self.current.cells())
        return [(c,r+d) for c,r in self.current.cells()]

    @property
    def fall_interval_ms(self) -> int:
        """当前等级对应的自动下落间隔（毫秒），随等级缩短但不低于 MIN_FALL_INTERVAL_MS。"""
        return max(int(BASE_FALL_INTERVAL_MS * SPEED_UP_FACTOR ** (self.level-1)),MIN_FALL_INTERVAL_MS)

    @property
    def is_playing(self) -> bool:
        """是否处于进行中状态。"""
        return self.state is GameState.PLAYING

    @property
    def is_over(self) -> bool:
        """是否已经游戏结束。"""
        return self.state is GameState.GAME_OVER

    @property
    def is_paused(self) -> bool:
        """是否处于暂停状态。"""
        return self.state is GameState.PAUSED
