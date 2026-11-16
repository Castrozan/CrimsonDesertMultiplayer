import math
import unittest

from hypothesis import HealthCheck, given, settings, strategies as st

from agent_mcp.navigation import GroundVector, heading_degrees, stick_toward

coordinate = st.floats(min_value=-5000, max_value=5000, allow_nan=False)
angle = st.floats(min_value=0, max_value=2 * math.pi, allow_nan=False)


def camera_axes(yaw: float) -> tuple[GroundVector, GroundVector]:
    forward = GroundVector(math.sin(yaw), math.cos(yaw))
    right = GroundVector(math.cos(yaw), -math.sin(yaw))
    return forward, right


class StickTowardTest(unittest.TestCase):
    @settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(coordinate, coordinate, coordinate, coordinate, angle)
    def test_stick_points_at_target_in_camera_frame(self, player_x, player_z, target_x, target_z, yaw):
        player, target = GroundVector(player_x, player_z), GroundVector(target_x, target_z)
        offset = target.minus(player)
        forward, right = camera_axes(yaw)
        stick = stick_toward(player, target, forward, right, 4.0, 0.35)
        if offset.length() < 1e-6:
            return
        moved = GroundVector(right.x * stick.right + forward.x * stick.forward,
                             right.z * stick.right + forward.z * stick.forward)
        self.assertGreater(moved.normalized().dot(offset.normalized()), 0.999)

    @settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(coordinate, coordinate, coordinate, coordinate, angle)
    def test_stick_stays_in_range_and_never_below_minimum(self, player_x, player_z, target_x, target_z, yaw):
        player, target = GroundVector(player_x, player_z), GroundVector(target_x, target_z)
        forward, right = camera_axes(yaw)
        stick = stick_toward(player, target, forward, right, 4.0, 0.35)
        largest = max(abs(stick.right), abs(stick.forward))
        self.assertLessEqual(largest, 1.0 + 1e-9)
        if target.minus(player).length() > 1e-6:
            self.assertGreaterEqual(largest, 0.35 - 1e-9)

    def test_target_reached_means_centred_stick(self):
        here = GroundVector(3.0, 4.0)
        forward, right = camera_axes(0.0)
        stick = stick_toward(here, here, forward, right, 4.0, 0.35)
        self.assertEqual((stick.right, stick.forward), (0.0, 0.0))


class HeadingTest(unittest.TestCase):
    def test_cardinal_headings(self):
        self.assertAlmostEqual(heading_degrees(GroundVector(0, 1)), 0.0)
        self.assertAlmostEqual(heading_degrees(GroundVector(1, 0)), 90.0)
        self.assertAlmostEqual(heading_degrees(GroundVector(0, -1)), 180.0)
        self.assertAlmostEqual(heading_degrees(GroundVector(-1, 0)), 270.0)


if __name__ == "__main__":
    unittest.main()
