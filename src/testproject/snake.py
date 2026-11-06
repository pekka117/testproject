"""A snake game for the terminal, controlled with h, j, k, l (vim-style)."""

from __future__ import annotations

import curses
import random
import time
from collections import deque

# Direction vectors as (dx, dy); y grows downward on the screen.
LEFT = (-1, 0)
DOWN = (0, 1)
UP = (0, -1)
RIGHT = (1, 0)

KEY_TO_DIRECTION = {
    ord("h"): LEFT,
    ord("j"): DOWN,
    ord("k"): UP,
    ord("l"): RIGHT,
    curses.KEY_LEFT: LEFT,
    curses.KEY_DOWN: DOWN,
    curses.KEY_UP: UP,
    curses.KEY_RIGHT: RIGHT,
}

QUIT_KEYS = {ord("q"), ord("Q"), 27}  # q, Q, Esc
RESTART_KEYS = {ord("r"), ord("R")}

MIN_ROWS = 14
MIN_COLS = 34
MAX_BOARD_HEIGHT = 24
MAX_BOARD_WIDTH = 60
START_DELAY_MS = 130
MIN_DELAY_MS = 60
SPEEDUP_MS_PER_FOOD = 2


def _is_reverse(a: tuple[int, int], b: tuple[int, int]) -> bool:
    """True if direction b points exactly opposite to direction a."""
    return a[0] + b[0] == 0 and a[1] + b[1] == 0


def _spawn_food(
    occupied: set[tuple[int, int]], width: int, height: int
) -> tuple[int, int] | None:
    """Pick a random free cell, or None if the board is full."""
    free = [
        (x, y) for y in range(height) for x in range(width) if (x, y) not in occupied
    ]
    return random.choice(free) if free else None


def _init_colors() -> dict[str, int]:
    colors: dict[str, int] = {}
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_RED, -1)
        curses.init_pair(3, curses.COLOR_CYAN, -1)
        colors = {
            "head": curses.color_pair(1) | curses.A_BOLD,
            "body": curses.color_pair(1),
            "food": curses.color_pair(2) | curses.A_BOLD,
            "text": curses.color_pair(3),
        }
    return colors


def _draw(
    stdscr: curses.window,
    snake: deque[tuple[int, int]],
    food: tuple[int, int] | None,
    score: int,
    width: int,
    height: int,
    colors: dict[str, int],
    message: str | None = None,
) -> None:
    stdscr.erase()
    stdscr.addstr(0, 0, f" Score: {score}   h/j/k/l: move   q: quit ", colors.get("text", 0))
    stdscr.addstr(1, 0, "+" + "-" * width + "+")
    for y in range(height):
        stdscr.addstr(2 + y, 0, "|")
        stdscr.addstr(2 + y, width + 1, "|")
    stdscr.addstr(2 + height, 0, "+" + "-" * width + "+")
    if food is not None:
        stdscr.addstr(2 + food[1], 1 + food[0], "*", colors.get("food", 0))
    for i, (x, y) in enumerate(snake):
        attr = colors.get("head" if i == 0 else "body", 0)
        stdscr.addstr(2 + y, 1 + x, "O" if i == 0 else "o", attr)
    if message is not None:
        message = message[: max(1, width - 2)]
        row = 2 + height // 2
        col = max(1, (width + 2 - len(message)) // 2)
        stdscr.addstr(row, col, message, curses.A_BOLD)
    stdscr.refresh()


def _game_over(
    stdscr: curses.window,
    snake: deque[tuple[int, int]],
    food: tuple[int, int] | None,
    score: int,
    width: int,
    height: int,
    colors: dict[str, int],
    reason: str,
) -> bool:
    """Show the game-over screen. Returns True to restart, False to quit."""
    _draw(
        stdscr,
        snake,
        food,
        score,
        width,
        height,
        colors,
        message=f"{reason} Score: {score} | r: again, q: quit",
    )
    stdscr.timeout(-1)  # block until a key is pressed
    while True:
        key = stdscr.getch()
        if key in QUIT_KEYS:
            return False
        if key in RESTART_KEYS:
            return True


def _play_round(
    stdscr: curses.window, width: int, height: int, colors: dict[str, int]
) -> bool:
    """Play one round. Returns True if the player wants to restart, False to quit."""
    cy = height // 2
    cx = width // 2
    snake: deque[tuple[int, int]] = deque([(cx, cy), (cx - 1, cy), (cx - 2, cy)])
    direction = RIGHT
    turns: deque[tuple[int, int]] = deque()
    food = _spawn_food(set(snake), width, height)
    score = 0
    delay_ms = START_DELAY_MS

    _draw(stdscr, snake, food, score, width, height, colors)

    while True:
        # Read all pending input for one game tick.
        deadline = time.monotonic() + delay_ms / 1000
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            stdscr.timeout(max(1, int(remaining * 1000)))
            key = stdscr.getch()
            if key == -1:
                break  # no more input before this tick ends
            if key in QUIT_KEYS:
                return False
            if key in KEY_TO_DIRECTION and len(turns) < 3:
                turns.append(KEY_TO_DIRECTION[key])

        # Apply at most one queued turn per tick (prevents instant 180s).
        if turns:
            candidate = turns.popleft()
            if candidate != direction and not _is_reverse(candidate, direction):
                direction = candidate

        hx, hy = snake[0]
        dx, dy = direction
        head = (hx + dx, hy + dy)

        if not (0 <= head[0] < width and 0 <= head[1] < height):
            return _game_over(
                stdscr, snake, food, score, width, height, colors, "You hit the wall!"
            )
        # The tail cell frees up this tick (unless we're growing), so it's safe.
        if head in set(snake) - {snake[-1]}:
            return _game_over(
                stdscr,
                snake,
                food,
                score,
                width,
                height,
                colors,
                "You ran into yourself!",
            )

        snake.appendleft(head)
        if food is not None and head == food:
            score += 1
            delay_ms = max(MIN_DELAY_MS, delay_ms - SPEEDUP_MS_PER_FOOD)
            food = _spawn_food(set(snake), width, height)
            if food is None:
                return _game_over(
                    stdscr,
                    snake,
                    food,
                    score,
                    width,
                    height,
                    colors,
                    "You filled the whole board!",
                )
        else:
            snake.pop()

        _draw(stdscr, snake, food, score, width, height, colors)


def run(stdscr: curses.window) -> None:
    try:
        curses.curs_set(0)  # hide the cursor
    except curses.error:
        pass
    stdscr.keypad(True)
    colors = _init_colors()

    rows, cols = stdscr.getmaxyx()
    if rows < MIN_ROWS or cols < MIN_COLS:
        stdscr.addstr(0, 0, f"Terminal too small: {cols}x{rows}.")
        stdscr.addstr(1, 0, f"Need at least {MIN_COLS}x{MIN_ROWS}. Press any key to exit.")
        stdscr.getch()
        return

    height = min(rows - 3, MAX_BOARD_HEIGHT)
    width = min(cols - 2, MAX_BOARD_WIDTH)

    # Restart loop: keep playing rounds until the player quits.
    while _play_round(stdscr, width, height, colors):
        pass


def main() -> None:
    """Entry point for the snake game."""
    curses.wrapper(run)
