import math
from dataclasses import dataclass


@dataclass(frozen=True)
class GroundVector:
    x: float
    z: float

    @staticmethod
    def from_world(vector: list[float]) -> "GroundVector":
        return GroundVector(vector[0], vector[2])

    def length(self) -> float:
        return math.hypot(self.x, self.z)

    def normalized(self) -> "GroundVector":
        length = self.length()
        if length == 0:
            raise ValueError("cannot normalize a zero ground vector")
        return GroundVector(self.x / length, self.z / length)

    def dot(self, other: "GroundVector") -> float:
        return self.x * other.x + self.z * other.z

    def minus(self, other: "GroundVector") -> "GroundVector":
        return GroundVector(self.x - other.x, self.z - other.z)


@dataclass(frozen=True)
class StickDeflection:
    right: float
    forward: float


def stick_toward(
    player: GroundVector,
    target: GroundVector,
    camera_forward: GroundVector,
    camera_right: GroundVector,
    full_speed_distance: float,
    minimum_magnitude: float,
) -> StickDeflection:
    offset = target.minus(player)
    distance = offset.length()
    if distance == 0:
        return StickDeflection(0.0, 0.0)
    direction = offset.normalized()
    forward_axis = camera_forward.normalized()
    right_axis = camera_right.normalized()
    right = direction.dot(right_axis)
    forward = direction.dot(forward_axis)
    largest = max(abs(right), abs(forward))
    magnitude = max(minimum_magnitude, min(1.0, distance / full_speed_distance))
    return StickDeflection(right / largest * magnitude, forward / largest * magnitude)


def heading_degrees(direction: GroundVector) -> float:
    return math.degrees(math.atan2(direction.x, direction.z)) % 360.0
