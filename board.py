"""
board.py —— 场地（Board）

只负责场地本身：哪些格子被占、某行满没满、能消几行。不判断方块旋转、不算分数、不做绘制。
场地用行优先二维表 grid[row][col] 表示：None 表示空格，"T" 等代号表示该格属于哪种方块。
"""

from __future__ import annotations

from collections.abc import Iterable

from settings import COLS, EMPTY_CELL, ROWS

Cell = tuple[int, int]   # 棋盘格子坐标 (col, row)


class Board:
    """
    cols, rows: int                 场地尺寸（默认取 settings）
    grid: list[list[str | None]]    行优先二维表，grid[row][col]
    """

    def __init__(self, cols: int = COLS, rows: int = ROWS) -> None:
        self.cols = cols
        self.rows = rows
        self.grid: list[list[str | None]] = []
        self.reset()

    def reset(self) -> None:
        """清空成全空场地。"""
        self.grid=[[None for _ in range(self.cols)] for _ in range(self.rows)]

    def in_bounds(self, col: int, row: int) -> bool:
        """(col,row) 是否在场地范围内。"""
        return 0 <= col < self.cols and 0 <= row < self.rows

    def is_free(self, col: int, row: int) -> bool:
        """该格能不能放东西：在界内且为空；row < 0 是棋盘上方，视为空。"""
        if not (0 <= col < self.cols):
            return False
        if row < 0:
            return True
        if row >= self.rows:
            return False
        return self.grid[row][col] is None

    def can_place(self, cells: Iterable[Cell]) -> bool:
        """一整组格子能不能同时放下（撞墙、撞已有方块、出底都不行）。"""
        return all(self.is_free(c,r) for c,r in cells)

    def drop_distance(self, cells: Iterable[Cell]) -> int:
        """这组格子还能往下走几格才落地（0 表示已经贴着底或已有方块）。"""
        cells=list(cells)
        d=0
        while self.can_place((c,r+d+1) for c,r in cells):  # 先试"下一格"
            d+=1
        return d

    def top_out(self, cells: Iterable[Cell]) -> bool:
        """方块在出生位置就放不下，说明顶到顶部了，游戏结束。"""
        return not self.can_place(cells)

    def lock(self, kind: str, cells: Iterable[Cell]) -> int:
        """把方块固定进场地（跳过 row < 0 的部分），顺便消行，返回消除的行数。"""
        for col,row in cells:
            if row<0:
                continue
            self.grid[row][col]=kind
        return self.clear_full_rows()

    def full_rows(self) -> list[int]:
        """返回所有满行的行号（从 0 开始）。"""
        return [row for row in range(self.rows) if None not in self.grid[row]]

    def clear_full_rows(self) -> int:
        """消掉满行并在顶部补回等量空行，返回消除的行数。"""
        kept=[row for row in self.grid if None in row]
        cleared=self.rows-len(kept)
        if cleared > 0:
            self.grid=[[None]*self.cols for _ in range(cleared)] + kept
        return cleared

    def occupied_cells(self) -> Iterable[tuple[int, int, str]]:
        """遍历已有方块，产出 (col, row, kind)，方便 Renderer 直接画。"""
        ret=[]
        for row in range(self.rows):
            for col in range(self.cols):
                if self.grid[row][col] is not None:
                    ret.append((col,row,self.grid[row][col]))
        return ret
