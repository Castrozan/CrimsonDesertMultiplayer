import time

from evdev import AbsInfo, UInput, ecodes

BUTTONS = {
    "a": ecodes.BTN_SOUTH,
    "b": ecodes.BTN_EAST,
    "x": ecodes.BTN_WEST,
    "y": ecodes.BTN_NORTH,
    "lb": ecodes.BTN_TL,
    "rb": ecodes.BTN_TR,
    "start": ecodes.BTN_START,
    "back": ecodes.BTN_SELECT,
    "guide": ecodes.BTN_MODE,
    "left_stick_click": ecodes.BTN_THUMBL,
    "right_stick_click": ecodes.BTN_THUMBR,
}
TRIGGERS = {"lt": ecodes.ABS_Z, "rt": ecodes.ABS_RZ}
DPAD = {"dpad_left": (ecodes.ABS_HAT0X, -1), "dpad_right": (ecodes.ABS_HAT0X, 1),
        "dpad_up": (ecodes.ABS_HAT0Y, -1), "dpad_down": (ecodes.ABS_HAT0Y, 1)}
CONTROL_NAMES = sorted([*BUTTONS, *TRIGGERS, *DPAD])

STICK_RANGE = 32767
STICK = AbsInfo(value=0, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)
TRIGGER = AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)
HAT = AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)
DETECTION_DELAY_SECONDS = 2.0


def stick_value(deflection: float) -> int:
    return round(max(-1.0, min(1.0, deflection)) * STICK_RANGE)


class VirtualPad:
    def __init__(self) -> None:
        capabilities = {
            ecodes.EV_KEY: list(BUTTONS.values()),
            ecodes.EV_ABS: [
                (ecodes.ABS_X, STICK), (ecodes.ABS_Y, STICK), (ecodes.ABS_RX, STICK), (ecodes.ABS_RY, STICK),
                (ecodes.ABS_Z, TRIGGER), (ecodes.ABS_RZ, TRIGGER),
                (ecodes.ABS_HAT0X, HAT), (ecodes.ABS_HAT0Y, HAT),
            ],
        }
        self._device = UInput(capabilities, name="Microsoft X-Box 360 pad", vendor=0x045E, product=0x028E,
                              version=0x110, bustype=ecodes.BUS_USB)
        time.sleep(DETECTION_DELAY_SECONDS)

    def close(self) -> None:
        self.release_all()
        self._device.close()

    def set_control(self, name: str, pressed: bool) -> None:
        if name in BUTTONS:
            self._device.write(ecodes.EV_KEY, BUTTONS[name], int(pressed))
        elif name in TRIGGERS:
            self._device.write(ecodes.EV_ABS, TRIGGERS[name], 255 if pressed else 0)
        elif name in DPAD:
            axis, value = DPAD[name]
            self._device.write(ecodes.EV_ABS, axis, value if pressed else 0)
        else:
            raise ValueError(f"unknown control {name!r}; known: {', '.join(CONTROL_NAMES)}")
        self._device.syn()

    def set_left_stick(self, right: float, forward: float) -> None:
        self._write_stick(ecodes.ABS_X, ecodes.ABS_Y, right, forward)

    def set_right_stick(self, right: float, up: float) -> None:
        self._write_stick(ecodes.ABS_RX, ecodes.ABS_RY, right, up)

    def release_all(self) -> None:
        self.set_left_stick(0.0, 0.0)
        self.set_right_stick(0.0, 0.0)
        for name in CONTROL_NAMES:
            self.set_control(name, False)

    def _write_stick(self, horizontal_axis: int, vertical_axis: int, right: float, up: float) -> None:
        self._device.write(ecodes.EV_ABS, horizontal_axis, stick_value(right))
        self._device.write(ecodes.EV_ABS, vertical_axis, stick_value(-up))
        self._device.syn()
