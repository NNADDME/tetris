"""
tetromino.py —— 方块（Tetromino）

本模块只描述方块长什么样、朝哪边、在哪个格子；不判断棋盘、不负责绘制。
所有坐标都是棋盘格子坐标 (col, row)。形状统一用 4x4 的 0/1 矩阵表示（0=空，1=实心），
这样旋转只需把矩阵转 90°，七种方块共用一套代码，不用为 I 型和 O 型写特例。
"""

from __future__ import annotations

import copy
import random

from settings import COLS

# 棋盘格子坐标：(col, row)，横向在前、纵向在后
Cell = tuple[int, int]

# 7 种方块代号
SHAPE_KINDS: tuple[str, ...] = ("I", "O", "T", "S", "Z", "J", "L")

# 每个形状的 4x4 矩阵；所有矩阵必须一样大，旋转才不会错位
SHAPE_MATRICES: dict[str, list[list[int]]] = {
    "I":[
        [0,0,0,0],
        [1,1,1,1],
        [0,0,0,0],
        [0,0,0,0]
    ],
    "O":[
        [0,0,0,0],
        [0,1,1,0],
        [0,1,1,0],
        [0,0,0,0]
    ],
    "T":[
        [0,1,0,0],
        [1,1,1,0],
        [0,0,0,0],
        [0,0,0,0]
    ],
    "S":[
        [0,1,1,0],
        [1,1,0,0],
        [0,0,0,0],
        [0,0,0,0]
    ],
    "Z":[
        [1,1,0,0],
        [0,1,1,0],
        [0,0,0,0],
        [0,0,0,0]
    ],
    "J":[
        [1,0,0,0],
        [1,1,1,0],
        [0,0,0,0],
        [0,0,0,0]
    ],
    "L":[
        [0,0,1,0],
        [1,1,1,0],
        [0,0,0,0],
        [0,0,0,0]
    ]
}

# 出生位置：4x4 矩阵水平居中，所以列偏移是 COLS//2 - 2
SPAWN_COL = COLS // 2 - 2
SPAWN_ROW = 0


def rotate_matrix_cw(matrix: list[list[int]]) -> list[list[int]]:
    """顺时针旋转 90°，返回新矩阵：new[r][c] = old[n-1-c][r]。"""
    n=len(matrix)
    ret=[[0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            ret[i][j]=matrix[n-1-j][i]
    return ret


def rotate_matrix_ccw(matrix: list[list[int]]) -> list[list[int]]:
    """逆时针旋转 90°，返回新矩阵：new[r][c] = old[c][n-1-r]。"""
    n=len(matrix)
    ret=[[0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            ret[n-1-j][i]=matrix[i][j]
    return ret


class Tetromino:
    """
    kind   : 形状代号，如 "T"；Board 里也存这个值当颜色索引
    matrix : 当前旋转状态的 4x4 矩阵
    col    : 矩阵左上角在棋盘的列
    row    : 矩阵左上角的行（可以是负数，方块从顶部上方进入）
    """

    def __init__(self, kind: str, col: int = SPAWN_COL, row: int = SPAWN_ROW) -> None:
        self.kind=kind
        self.matrix=copy.deepcopy(SHAPE_MATRICES[self.kind])
        self.col=col
        self.row=row

    def cells(self) -> list[Cell]:
        """返回方块当前占据的棋盘格子坐标列表，是逻辑层与棋盘之间的翻译层。"""
        return self.cells_at(self.matrix,self.col,self.row)

    @staticmethod
    def cells_at(matrix: list[list[int]], col: int, row: int) -> list[Cell]:
        """算出"换成 matrix、放在 (col,row)"时会占据哪些格子；
        供旋转踢墙试探用，不改变方块自身状态。"""
        ret=[]
        n=len(matrix)
        for r in range(n):
            for c in range(n):
                if matrix[r][c]==1:
                    ret.append((col+c, row+r))
        return ret

    def rotated_matrix(self, clockwise: bool = True) -> list[list[int]]:
        """返回旋转后的矩阵，不改自身状态——它只是候选，是否采用由 Game 决定。"""
        return rotate_matrix_cw(self.matrix) if clockwise else rotate_matrix_ccw(self.matrix)

    def move(self, d_col: int, d_row: int) -> None:
        """平移一步，不做碰撞检查（合法性由 Board / Game 判断）。"""
        self.col+=d_col
        self.row+=d_row

    def apply(self, matrix: list[list[int]], col: int, row: int) -> None:
        """采用某个试探成功的状态（旋转踢墙成功后由 Game 调用）。"""
        self.matrix=copy.deepcopy(matrix)
        self.row=row
        self.col=col

    def copy(self) -> "Tetromino":
        """复制一个带当前朝向和位置的副本，用于"如果这样放会怎样"的推演。"""
        ret=Tetromino(self.kind, self.col, self.row)
        ret.matrix=[row[:] for row in self.matrix]
        return ret

    @staticmethod
    def spawn(kind: str) -> "Tetromino":
        """按出生位置造一个新方块。"""
        ret=Tetromino(kind)
        return ret


class SevenBag:
    """
    7-bag 随机生成器：把 7 种方块洗牌成一袋依次发，发完再洗新袋。
    保证任意连续 7 个方块里七种各出现一次，避免同一个形状连来多次、或长时间不出 I 型。
    """

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._bag: list[str] = []

    def _refill(self) -> None:
        """洗一袋新的：7 种各一次、顺序随机。"""
        self._bag=list(SHAPE_KINDS)
        self._rng.shuffle(self._bag)

    def next_kind(self) -> str:
        """取下一个方块代号；袋子空了先补一袋。"""
        if not self._bag:
            self._refill()
        return self._bag.pop()
