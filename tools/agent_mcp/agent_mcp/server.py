import asyncio
import os
import subprocess
import tempfile
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP, Image

from .bridge_client import BridgeClient
from .navigation import GroundVector, heading_degrees
from .virtual_pad import CONTROL_NAMES, VirtualPad
from .walker import Walker

GAME_WINDOW = "title:^Crimson Desert$"

bridge = BridgeClient(
    host="127.0.0.1",
    port=int(os.environ.get("CDMP_AGENT_PORT", "37020")),
    timeout_seconds=2.0,
)
server = FastMCP(
    "crimson-desert",
    instructions=(
        "Play Crimson Desert. Observe with get_state (structured state read from game memory by the cdmp mod: "
        "world position in metres with Y up, rotation quaternion, HP, stamina, camera) and screenshot. Act with a "
        "virtual Xbox 360 pad: press for buttons (A confirms/interacts, B cancels, Y loads on the title menu, "
        "start opens the menu), hold for sticks and held buttons, walk_to to walk to a ground point (x, z). "
        "Input reaches the game only while its window has focus: call focus_game first."
    ),
)
_pad: VirtualPad | None = None


def pad() -> VirtualPad:
    global _pad
    if _pad is None:
        _pad = VirtualPad()
    return _pad


def describe(state: dict) -> dict:
    camera = state.get("camera")
    if camera:
        state["camera_heading_degrees"] = round(heading_degrees(GroundVector.from_world(camera["forward"])), 1)
    return state


@server.tool()
def get_state() -> dict:
    """Game state from the cdmp mod: in_world, player position [x,y,z] (metres, Y up), rotation, health,
    stamina, camera position/forward/right and its ground heading (degrees from +Z toward +X)."""
    return describe(bridge.read_state())


@server.tool()
def screenshot() -> Image:
    """A half-resolution JPEG of the screen the game is on."""
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "screen.jpg")
        subprocess.run(["hypruse", "screenshot", "--scale", "0.5", "--out", path],
                       check=True, capture_output=True, timeout=20)
        with open(path, "rb") as image_file:
            return Image(data=image_file.read(), format="jpeg")


@server.tool()
def focus_game() -> str:
    """Give the game window keyboard and pad focus."""
    result = subprocess.run(["hyprctl", "dispatch", "focuswindow", GAME_WINDOW],
                            capture_output=True, text=True, timeout=10)
    return result.stdout.strip() or result.stderr.strip()


@server.tool(description=(
    "Press controls one after another, each held hold_seconds, then gap_seconds before the next. "
    f"Controls: {', '.join(CONTROL_NAMES)}."
))
async def press(controls: list[str], hold_seconds: float = 0.15, gap_seconds: float = 0.6) -> str:
    device = pad()
    for name in controls:
        device.set_control(name, True)
        await asyncio.sleep(hold_seconds)
        device.set_control(name, False)
        await asyncio.sleep(gap_seconds)
    return f"pressed {', '.join(controls)}"


@server.tool()
async def hold(seconds: float, controls: list[str] | None = None, move_right: float = 0.0,
               move_forward: float = 0.0, look_right: float = 0.0, look_up: float = 0.0) -> str:
    """Hold sticks and controls together for `seconds`, then release everything. move_* is the left stick
    (character movement relative to the camera), look_* the right stick (camera), each in [-1, 1]."""
    device = pad()
    names = controls or []
    try:
        for name in names:
            device.set_control(name, True)
        device.set_left_stick(move_right, move_forward)
        device.set_right_stick(look_right, look_up)
        await asyncio.sleep(seconds)
    finally:
        device.release_all()
    return f"held for {seconds} s"


@server.tool()
async def walk_to(x: float, z: float, tolerance_m: float = 1.0, timeout_seconds: float = 60.0) -> dict:
    """Walk to the ground point (x, z) in world metres, steering with the left stick from the live position
    and camera, then stop. Returns whether it arrived, the final position and the remaining distance."""
    walker = Walker(read_state=bridge.read_state, steer=pad().set_left_stick)
    return asdict(await walker.walk_to(x, z, tolerance_m, timeout_seconds))


def main() -> None:
    try:
        server.run()
    finally:
        if _pad is not None:
            _pad.close()
