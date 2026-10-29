"""DualSenseゲームパッドでTello EDUを手動操作する。"""

from __future__ import annotations

import argparse
import select
import socket
import sys
import time
from dataclasses import dataclass
from typing import Optional


DEFAULT_DRONE_IP = "192.168.10.1"
DRONE_COMMAND_PORT = 8889
LOCAL_COMMAND_PORT = 8889
CONTROL_RATE_HZ = 20
CONTROL_PERIOD_SECONDS = 1.0 / CONTROL_RATE_HZ
MAX_RC_VALUE = 30
DEFAULT_DEADZONE = 0.12
DEFAULT_BATTERY_FLOOR = 20


@dataclass
class ControllerInput:
    """ゲームパッドから読み取った操作値。"""

    roll: float
    pitch: float
    descend: float
    ascend: float
    takeoff: bool
    land: bool
    deadman: bool


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manually control a Tello EDU with a gamepad."
    )
    parser.add_argument("--drone-ip", default=DEFAULT_DRONE_IP)
    parser.add_argument("--local-ip", help="PC Wi-Fi adapter IP on the Tello network, for example 192.168.10.2.")
    parser.add_argument("--controller-index", type=int, default=0)
    parser.add_argument("--confirm-flight", action="store_true")
    parser.add_argument("--input-check", action="store_true", help="Show gamepad inputs without connecting to the drone.")
    parser.add_argument("--max-rc", type=int, default=MAX_RC_VALUE, choices=range(10, 51))
    parser.add_argument("--deadzone", type=float, default=DEFAULT_DEADZONE, choices=[i / 100 for i in range(5, 31)])
    parser.add_argument("--left-x-axis", type=int, default=0)
    parser.add_argument("--left-y-axis", type=int, default=1)
    parser.add_argument("--l2-axis", type=int, default=4)
    parser.add_argument("--r2-axis", type=int, default=5)
    parser.add_argument("--trigger-rest", type=float, default=-1.0, choices=(-1.0, 0.0))
    parser.add_argument("--takeoff-button", type=int, default=0, help="DualSense Cross button index (default: 0).")
    parser.add_argument("--land-button", type=int, default=1, help="DualSense Circle button index (default: 1).")
    parser.add_argument("--deadman-button", type=int, default=4, help="Hold this button to enable movement (default: L1/index 4).")
    parser.add_argument("--min-battery", type=int, default=DEFAULT_BATTERY_FLOOR)
    return parser.parse_args(argv)


def load_pygame():
    try:
        import pygame
    except ImportError as exc:
        print("Pygame is not installed. Run: py -m pip install -r requirements.txt", file=sys.stderr)
        raise SystemExit(1) from exc
    return pygame


def apply_deadzone(value: float, deadzone: float) -> float:
    if abs(value) <= deadzone:
        return 0.0
    scaled = (abs(value) - deadzone) / (1.0 - deadzone)
    return scaled if value > 0 else -scaled


def read_trigger(value: float, rest_value: float) -> float:
    """トリガー値を休止位置0、全押し1の範囲に正規化する。"""
    if rest_value == -1.0:
        return max(0.0, min(1.0, (value + 1.0) / 2.0))
    return max(0.0, min(1.0, value))


class Gamepad:
    def __init__(self, pygame, args: argparse.Namespace) -> None:
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() <= args.controller_index:
            raise RuntimeError("Gamepad not found. Connect the DualSense and check the index.")
        self.pygame = pygame
        self.args = args
        self.device = pygame.joystick.Joystick(args.controller_index)
        self.device.init()
        self.instance_id = self.device.get_instance_id()
        print(f"Gamepad: {self.device.get_name()}")
        print(f"Axes: {self.device.get_numaxes()}, buttons: {self.device.get_numbuttons()}")

    def poll(self) -> ControllerInput:
        self.pygame.event.pump()
        events = self.pygame.event.get()
        removed = getattr(self.pygame, "JOYDEVICEREMOVED", -1)
        if any(
            event.type == removed and getattr(event, "instance_id", None) == self.instance_id
            for event in events
        ) or not self.device.get_init():
            raise RuntimeError("Gamepad disconnected.")
        axes = self.device.get_numaxes()
        buttons = self.device.get_numbuttons()
        indexes = (
            self.args.left_x_axis,
            self.args.left_y_axis,
            self.args.l2_axis,
            self.args.r2_axis,
        )
        if any(index < 0 or index >= axes for index in indexes):
            raise RuntimeError("Configured axis index is not available. Run --input-check and adjust axis options.")
        button_indexes = (self.args.takeoff_button, self.args.land_button, self.args.deadman_button)
        if any(index < 0 or index >= buttons for index in button_indexes):
            raise RuntimeError("Configured button index is not available. Run --input-check and adjust button options.")

        return ControllerInput(
            roll=apply_deadzone(self.device.get_axis(self.args.left_x_axis), self.args.deadzone),
            pitch=-apply_deadzone(self.device.get_axis(self.args.left_y_axis), self.args.deadzone),
            descend=read_trigger(self.device.get_axis(self.args.l2_axis), self.args.trigger_rest),
            ascend=read_trigger(self.device.get_axis(self.args.r2_axis), self.args.trigger_rest),
            takeoff=bool(self.device.get_button(self.args.takeoff_button)),
            land=bool(self.device.get_button(self.args.land_button)),
            deadman=bool(self.device.get_button(self.args.deadman_button)),
        )

    def close(self) -> None:
        self.device.quit()
        self.pygame.quit()


class TelloLink:
    """Tello SDKのUDPコマンドを送受信する。"""

    def __init__(self, drone_ip: str, local_ip: Optional[str] = None) -> None:
        self.address = (drone_ip, DRONE_COMMAND_PORT)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # SDK仕様に合わせ、送信と応答受信で同じUDPポートを使う。
            self.sock.bind((local_ip or "0.0.0.0", LOCAL_COMMAND_PORT))
        except OSError:
            self.sock.close()
            raise
        self.sock.setblocking(False)

    def command(self, text: str, timeout: float = 5.0) -> str:
        self.sock.sendto(text.encode("ascii"), self.address)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            ready, _, _ = select.select([self.sock], [], [], min(remaining, 0.2))
            if ready:
                response, _ = self.sock.recvfrom(1024)
                result = response.decode("ascii", errors="replace").strip()
                if result.lower() == "ok":
                    return result
                if text.endswith("?") and result and not result.lower().startswith("error"):
                    return result
                raise RuntimeError(f"Tello rejected '{text}': {result}")
        raise TimeoutError(f"No response to Tello command: {text}")

    def send_rc(self, roll: int, pitch: int, vertical: int) -> None:
        command = f"rc {roll} {pitch} {vertical} 0"
        self.sock.sendto(command.encode("ascii"), self.address)

    def close(self) -> None:
        self.sock.close()


def read_battery(link: TelloLink) -> int:
    response = link.command("battery?")
    try:
        return int(response.rstrip("%"))
    except ValueError as exc:
        raise RuntimeError(f"Unexpected battery response: {response}") from exc


def input_check(gamepad: Gamepad, args: argparse.Namespace) -> None:
    pygame = gamepad.pygame
    print("Input check only. Press Ctrl+C to quit; no drone connection is made.")
    try:
        while True:
            pygame.event.pump()
            if not gamepad.device.get_init():
                raise RuntimeError("Gamepad disconnected.")
            axis_values = [round(gamepad.device.get_axis(i), 2) for i in range(gamepad.device.get_numaxes())]
            pressed = [i for i in range(gamepad.device.get_numbuttons()) if gamepad.device.get_button(i)]
            print(f"axes={axis_values} buttons={pressed}", end="\r", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nInput check ended.")


def rc_values(control: ControllerInput, max_rc: int) -> tuple[int, int, int]:
    roll = round(control.roll * max_rc) if control.deadman else 0
    pitch = round(control.pitch * max_rc) if control.deadman else 0
    vertical = round((control.ascend - control.descend) * max_rc) if control.deadman else 0
    return roll, pitch, vertical


def run_controller(gamepad: Gamepad, args: argparse.Namespace) -> None:
    link = TelloLink(args.drone_ip, args.local_ip)
    airborne = False
    previous_takeoff = False
    previous_land = False
    try:
        print("Entering Tello SDK mode...")
        link.command("command")
        battery = read_battery(link)
        print(f"Battery: {battery}%")
        if battery < args.min_battery:
            raise RuntimeError(f"Battery is below the configured minimum ({args.min_battery}%).")
        print("Ready. Cross: takeoff, Circle: land. Hold L1 to enable movement; release L1 to hover.")
        print("Left stick: move. L2: descend. R2: ascend. Yaw is disabled.")

        next_tick = time.monotonic()
        last_status = 0.0
        while True:
            control = gamepad.poll()

            if control.takeoff and not previous_takeoff and not airborne:
                print("Taking off...")
                link.send_rc(0, 0, 0)
                link.command("takeoff", timeout=10.0)
                airborne = True
                print("Airborne. Hold L1 to move.")
            if control.land and not previous_land and airborne:
                print("Landing...")
                link.send_rc(0, 0, 0)
                link.command("land", timeout=10.0)
                airborne = False
                print("Landed.")
            previous_takeoff = control.takeoff
            previous_land = control.land

            if airborne:
                roll, pitch, vertical = rc_values(control, args.max_rc)
                link.send_rc(roll, pitch, vertical)
                now = time.monotonic()
                if now - last_status >= 0.5:
                    print(f"\rRC roll={roll:>3} pitch={pitch:>3} vertical={vertical:>3} | deadman={'ON ' if control.deadman else 'OFF'}", end="", flush=True)
                    last_status = now

            next_tick += CONTROL_PERIOD_SECONDS
            time.sleep(max(0.0, next_tick - time.monotonic()))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        if airborne:
            try:
                link.send_rc(0, 0, 0)
                link.command("land", timeout=10.0)
                print("Landed.")
                airborne = False
            except Exception as exc:
                print(f"Landing command failed: {exc}", file=sys.stderr)
    except Exception:
        if airborne:
            print("Control failure. Attempting to land...", file=sys.stderr)
            try:
                link.send_rc(0, 0, 0)
                link.command("land", timeout=10.0)
                airborne = False
            except Exception as exc:
                print(f"Landing command failed: {exc}", file=sys.stderr)
        raise
    finally:
        link.close()


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    pygame = load_pygame()
    gamepad = Gamepad(pygame, args)
    try:
        if args.input_check:
            input_check(gamepad, args)
            return 0
        if not args.confirm_flight:
            raise SystemExit("This command can fly the drone. Re-run with --confirm-flight after checking the area.")
        run_controller(gamepad, args)
        return 0
    finally:
        gamepad.close()


if __name__ == "__main__":
    raise SystemExit(main())
