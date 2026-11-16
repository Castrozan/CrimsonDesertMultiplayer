import asyncio
import unittest

from agent_mcp.walker import Walker


class SimulatedWorld:
    def __init__(self, start: list[float], camera_forward: list[float], camera_right: list[float],
                 speed_m_per_tick: float, blocked: bool = False) -> None:
        self.position = list(start)
        self.camera = {"position": [0, 0, 0], "forward": camera_forward, "right": camera_right}
        self.speed = speed_m_per_tick
        self.blocked = blocked
        self.stick = (0.0, 0.0)
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    def read_state(self) -> dict:
        return {"player": {"position": list(self.position)}, "camera": self.camera,
                "player_status": "in world", "camera_status": "ok"}

    def steer(self, right: float, forward: float) -> None:
        self.stick = (right, forward)

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        if self.blocked:
            return
        right, forward = self.stick
        for axis in (0, 2):
            self.position[axis] += self.speed * (right * self.camera["right"][axis]
                                                 + forward * self.camera["forward"][axis])


class WalkerTest(unittest.TestCase):
    def test_walks_twenty_metres_and_stops_within_tolerance(self):
        world = SimulatedWorld([0, 50, 0], [0.6, 0, 0.8], [0.8, 0, -0.6], speed_m_per_tick=0.5)
        result = asyncio.run(Walker(world.read_state, world.steer, world.sleep, world.clock).walk_to(12.0, 16.0, 1.0, 30.0))
        self.assertTrue(result.arrived, result)
        self.assertEqual(result.reason, "arrived")
        self.assertLessEqual(result.distance_m, 1.0)
        self.assertEqual(world.stick, (0.0, 0.0))

    def test_reports_not_in_world(self):
        world = SimulatedWorld([0, 0, 0], [0, 0, 1], [1, 0, 0], 0.5)
        world.read_state = lambda: {"player": None, "camera": None, "player_status": "loading",
                                    "camera_status": "ok"}
        result = asyncio.run(Walker(world.read_state, world.steer, world.sleep, world.clock).walk_to(5.0, 5.0, 1.0, 5.0))
        self.assertFalse(result.arrived)
        self.assertTrue(result.reason.startswith("not in world: loading"))
        self.assertIsNone(result.position)

    def test_gives_up_when_stuck(self):
        world = SimulatedWorld([0, 0, 0], [0, 0, 1], [1, 0, 0], 0.5, blocked=True)
        result = asyncio.run(Walker(world.read_state, world.steer, world.sleep, world.clock).walk_to(20.0, 0.0, 1.0, 30.0))
        self.assertFalse(result.arrived)
        self.assertTrue(result.reason.startswith("stuck"), result.reason)
        self.assertEqual(world.stick, (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
