import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from .navigation import GroundVector, stick_toward

TICK_SECONDS = 0.1
SETTLE_SECONDS = 1.0
FULL_SPEED_DISTANCE_M = 4.0
MINIMUM_STICK = 0.35
PROGRESS_WINDOW_SECONDS = 4.0
MINIMUM_PROGRESS_M = 0.5


@dataclass(frozen=True)
class WalkResult:
    arrived: bool
    reason: str
    distance_m: float
    position: list[float] | None
    elapsed_seconds: float


class Walker:
    def __init__(self, read_state: Callable[[], dict], steer: Callable[[float, float], None],
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._read_state = read_state
        self._steer = steer
        self._sleep = sleep
        self._clock = clock

    async def walk_to(self, target_x: float, target_z: float, tolerance_m: float, timeout_seconds: float) -> WalkResult:
        target = GroundVector(target_x, target_z)
        started = self._clock()
        progress_mark = (started, float("inf"))
        reason = "timeout"
        try:
            while self._clock() - started < timeout_seconds:
                state = self._read_state()
                if not state.get("player") or not state.get("camera"):
                    reason = f"not in world: {state.get('player_status')} / camera {state.get('camera_status')}"
                    break
                player = GroundVector.from_world(state["player"]["position"])
                distance = target.minus(player).length()
                if distance <= tolerance_m:
                    reason = "arrived"
                    break
                now = self._clock()
                if now - progress_mark[0] >= PROGRESS_WINDOW_SECONDS:
                    if progress_mark[1] - distance < MINIMUM_PROGRESS_M:
                        reason = "stuck: less than 0.5 m of progress in 4 s"
                        break
                    progress_mark = (now, distance)
                elif progress_mark[1] == float("inf"):
                    progress_mark = (now, distance)
                deflection = stick_toward(
                    player, target,
                    GroundVector.from_world(state["camera"]["forward"]),
                    GroundVector.from_world(state["camera"]["right"]),
                    FULL_SPEED_DISTANCE_M, MINIMUM_STICK,
                )
                self._steer(deflection.right, deflection.forward)
                await self._sleep(TICK_SECONDS)
        finally:
            self._steer(0.0, 0.0)
        await self._sleep(SETTLE_SECONDS)
        final = self._read_state()
        position = final["player"]["position"] if final.get("player") else None
        final_distance = target.minus(GroundVector.from_world(position)).length() if position else float("nan")
        return WalkResult(
            arrived=position is not None and final_distance <= tolerance_m,
            reason=reason,
            distance_m=round(final_distance, 3),
            position=position,
            elapsed_seconds=round(self._clock() - started, 2),
        )
