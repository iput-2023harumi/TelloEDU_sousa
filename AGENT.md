# 開発者向けメモ

このファイルは、Tello EDU 制御ソフトを開発するための開発者向け情報をまとめたものです。
ユーザー向けの実行手順は `README.md` に記載します。

## プロジェクト概要

Tello EDU を Windows 11 PC から Python で制御するための実験用プロジェクトです。
まずは公式 RoboMaster SDK を使い、接続確認、離陸、短距離移動、着陸までを最小構成で扱います。

## 前提

- PC を Tello EDU の Wi-Fi に接続してから実行します。
- Tello EDU の Wi-Fi直結モードでは、機体の既定IPは `192.168.10.1` です。
- 実機が飛ぶコマンドは、十分な室内スペースを確保してから実行してください。
- 開発は Windows 11 を主対象とします。
- 実機接続テストは、Tello EDU と接続できるノートPCで行います。

## セットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows の Python Launcher を使う環境では、上記の `python` を `py` に置き換えても構いません。

## すぐ使うコマンド

```powershell
# 接続、SDKバージョン、バッテリー確認
python .\src\tello_basic_flight.py check

# 離陸して5秒ホバリング後に着陸
python .\src\tello_basic_flight.py --confirm-flight takeoff-land --hover-seconds 5

# 離陸、前進50cm、後退50cm、着陸
python .\src\tello_basic_flight.py --confirm-flight demo --distance-cm 50
```

## 開発ルール

- コード内にコメントを書く場合は、日本語で記述します。
- コメントは「です・ます」調にせず、言い切りの文体で記述します。
- 関数の役割が名前だけでは分かりにくい場合は、関数定義の直前に日本語コメントで補足します。
- 変数名だけでは用途が分かりにくい場合や、安全性・飛行制御に関わる重要な値には、日本語コメントで用途を補足します。
- 画面表示やコンソール表示に使う文字列は、原則として半角英数字を使用します。

