"""公式RoboMaster SDKを使ったTello EDUの基本飛行制御サンプル"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional


# SDKアクションの完了待ちに使う既定タイムアウト秒数
DEFAULT_ACTION_TIMEOUT_SECONDS = 20

# デモ飛行で指定できる移動距離の安全範囲
MIN_SAFE_DISTANCE_CM = 20
MAX_SAFE_DISTANCE_CM = 100


@dataclass
class ConnectedDrone:
    drone: Any

    @property
    def flight(self):
        return self.drone.flight

    @property
    def battery(self):
        return self.drone.battery

    def close(self) -> None:
        self.drone.close()


# SDKのアクション完了待ちをSDKバージョン差に対応して扱う
def wait_action(action, timeout: int = DEFAULT_ACTION_TIMEOUT_SECONDS) -> None:
    try:
        action.wait_for_completed(timeout=timeout)
    except TypeError:
        action.wait_for_completed(timeout)


# Tello EDUへ接続し、操作用のSDKオブジェクトを返す
def connect(local_ip: Optional[str]) -> ConnectedDrone:
    try:
        import robomaster
        from robomaster import robot
    except ImportError as exc:  # pragma: no cover - ローカル環境の依存関係に左右される箇所
        print(
            "RoboMaster SDK is not installed. Run: py -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    if local_ip:
        robomaster.config.LOCAL_IP_STR = local_ip

    tl_drone = robot.Drone()
    tl_drone.initialize()
    return ConnectedDrone(tl_drone)


def print_drone_status(conn: ConnectedDrone) -> None:
    sdk_version = conn.drone.get_sdk_version()
    print(f"Drone SDK version: {sdk_version}")

    try:
        battery = conn.battery.get_battery()
    except Exception as exc:  # バッテリー取得に失敗しても接続確認は継続
        print(f"Battery: unavailable ({exc})")
    else:
        print(f"Battery: {battery}%")


def require_flight_confirmation(confirm_flight: bool) -> None:
    if confirm_flight:
        return

    raise SystemExit(
        "This command will fly the drone. Re-run with --confirm-flight after checking the area."
    )


# 飛行中の例外時にも着陸を試みるための安全処理
def safe_land(conn: ConnectedDrone) -> None:
    try:
        conn.flight.stop()
    except Exception:
        pass

    try:
        wait_action(conn.flight.land())
    except Exception as exc:
        print(f"Landing command failed: {exc}", file=sys.stderr)


# 離陸から着陸までをまとめ、途中失敗時も着陸を試みる
def run_with_landing(conn: ConnectedDrone, flight_plan: Callable[[ConnectedDrone], None]) -> None:
    # 機体が空中にいる可能性を判断するための安全フラグ
    airborne = False
    try:
        print("Takeoff...")
        wait_action(conn.flight.takeoff())
        airborne = True

        flight_plan(conn)

        print("Landing...")
        wait_action(conn.flight.land())
        airborne = False
    except KeyboardInterrupt:
        print("\nInterrupted. Landing...")
        if airborne:
            safe_land(conn)
        raise SystemExit(130)
    except Exception:
        if airborne:
            print("Error during flight. Attempting to land...", file=sys.stderr)
            safe_land(conn)
        raise


def cmd_check(args: argparse.Namespace) -> None:
    conn = connect(args.local_ip)
    try:
        print_drone_status(conn)
    finally:
        conn.close()


def cmd_takeoff_land(args: argparse.Namespace) -> None:
    require_flight_confirmation(args.confirm_flight)
    conn = connect(args.local_ip)
    try:
        print_drone_status(conn)

        def plan(_: ConnectedDrone) -> None:
            print(f"Hovering for {args.hover_seconds} seconds...")
            import time

            time.sleep(args.hover_seconds)

        run_with_landing(conn, plan)
    finally:
        conn.close()


def cmd_demo(args: argparse.Namespace) -> None:
    require_flight_confirmation(args.confirm_flight)
    conn = connect(args.local_ip)
    try:
        print_drone_status(conn)

        def plan(active: ConnectedDrone) -> None:
            distance_cm = args.distance_cm
            print(f"Forward {distance_cm} cm...")
            wait_action(active.flight.forward(distance=distance_cm))
            print(f"Backward {distance_cm} cm...")
            wait_action(active.flight.backward(distance=distance_cm))

        run_with_landing(conn, plan)
    finally:
        conn.close()


# コマンドライン引数とサブコマンドを定義
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Basic Tello EDU control sample.")
    parser.add_argument(
        "--local-ip",
        help="Local PC IP address on the Tello Wi-Fi adapter, for example 192.168.10.2.",
    )
    parser.add_argument(
        "--confirm-flight",
        action="store_true",
        help="Required for commands that start the motors or fly the drone.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Connect and print SDK/battery status.")
    check.set_defaults(func=cmd_check)

    takeoff_land = subparsers.add_parser(
        "takeoff-land", help="Take off, hover briefly, and land."
    )
    takeoff_land.add_argument("--hover-seconds", type=float, default=5.0)
    takeoff_land.set_defaults(func=cmd_takeoff_land)

    demo = subparsers.add_parser("demo", help="Take off, move forward/backward, and land.")
    demo.add_argument(
        "--distance-cm",
        type=int,
        default=50,
        choices=range(MIN_SAFE_DISTANCE_CM, MAX_SAFE_DISTANCE_CM + 1),
        metavar=f"{MIN_SAFE_DISTANCE_CM}-{MAX_SAFE_DISTANCE_CM}",
    )
    demo.set_defaults(func=cmd_demo)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

