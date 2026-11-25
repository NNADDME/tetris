"""
main.py —— 程序入口
====================================================================
【整个程序的心跳只有这一段】
    pygame.init()
    建 Game / Renderer / Clock
    while 运行中:
        1) dt = clock.tick(FPS)            # 控制帧率，同时拿到本帧耗时（毫秒）
        2) 处理事件（pygame.event.get()）   # 谁想关窗口、按了什么键
        3) game.update(dt)                 # 按"时间"推进游戏逻辑
        4) renderer.draw_frame(game)       # 把状态画出来
        5) pygame.display.flip()           # 双缓冲翻页
    pygame.quit()

【顺序很重要】
    * 先处理事件再 update：否则玩家按下的键会晚一帧才生效，手感发黏。
    * update 里只改数据，draw 里只画像素 —— 严格分离，出 bug 时好定位。
    * clock.tick(FPS) 放在循环开头，返回值就是 dt，不用自己算时间差。

【事件的三类去向】
    1) pygame.QUIT（点窗口 X）      -> 退出循环
    2) ESC                         -> 退出（或先弹"确认退出"菜单，进阶）
    3) 其他所有按键                 -> 全部交给 game.handle_event(event)
       这样"按键决定游戏动作"的知识只存在于 game.py 一处。

【暂停时的两个坑】
    * 暂停了还要继续 tick(clock)，否则窗口会"无响应"（Windows 会提示未响应）。
    * 暂停时 dt 照常累计会让计时器跳变，所以 game.update() 内部要先看状态再累加。
"""

from __future__ import annotations

import sys

import pygame

from game import Game
from renderer import Renderer
from settings import CAPTION, FPS, KEY_QUIT, SCREEN_HEIGHT, SCREEN_WIDTH


def main() -> None:
    """启动游戏。实现步骤见模块开头的注释。"""
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(CAPTION)
    game = Game()
    renderer = Renderer(screen)
    clock = pygame.time.Clock()
    running = True

    while running:
        dt=clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == KEY_QUIT:
                running = False
            else:
                game.handle_event(event)
        game.update(dt)
        renderer.draw_frame(game)
        pygame.display.flip()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
