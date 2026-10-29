# Tello EDU 操作用手順書

この手順書は、Windows 11 PC から Tello EDU を Python で操作するためのユーザー向けガイドです。
接続確認、離陸、ホバリング、前進、後退、着陸までをコンソール操作で実行します。

## できること

- Tello EDU との接続確認
- Tello EDU のカメラ映像をPC画面でプレビュー
- SDKバージョンとバッテリー残量の表示
- 離陸して指定秒数ホバリング
- 離陸、前進、後退、着陸
- 実行中に `Ctrl+C` で中断した場合の着陸処理

## 準備するもの

- Tello EDU 本体
- Tello EDU のバッテリー
- Windows 11 PC
- Python がインストールされた環境
- このプロジェクトのファイル一式

## 作業前の安全確認

実行前に、必ず次の内容を確認してください。

- Tello EDU の周囲に人や壊れやすい物がない
- 室内に十分な飛行スペースがある
- プロペラが正しく取り付けられている
- バッテリー残量が十分にある
- 機体を水平で安定した場所に置いている
- 緊急時に `Ctrl+C` を押せる状態でコンソールを開いている

## 初回セットアップ

この作業は、Tello EDU の Wi-Fi に接続する前に実行してください。
Tello EDU の Wi-Fi に接続すると、PCがインターネットに接続できなくなる場合があります。

1. PowerShell を開く
2. プロジェクトフォルダへ移動する

```powershell
cd D:\harumi\VSC\TelloApp
```

3. Python仮想環境を作成する

```powershell
python -m venv .venv
```

4. Python仮想環境を有効化する

```powershell
.\.venv\Scripts\Activate.ps1
```

5. pip を更新する

```powershell
python -m pip install --upgrade pip
```

6. 必要なライブラリをインストールする

```powershell
python -m pip install -r requirements.txt
```

Windows の Python Launcher を使う環境では、上記の `python` を `py` に置き換えても構いません。

## 2回目以降の起動準備

2回目以降は、PowerShell を開いて次の操作だけを行います。

```powershell
cd D:\harumi\VSC\TelloApp
.\.venv\Scripts\Activate.ps1
```

## ドローンとの接続

1. Tello EDU の電源を入れる
2. Tello EDU のランプが点滅するまで待つ
3. Windows の Wi-Fi 設定を開く
4. `TELLO-` から始まるWi-Fiを選択する
5. PCをTello EDUのWi-Fiへ接続する
6. PowerShell に戻る

接続後、PCがインターネットから切断される場合があります。
ライブラリのインストールやGitHub操作は、Tello EDUのWi-Fiへ接続する前に済ませてください。

## 接続確認

まず、飛行しない接続確認コマンドを実行します。

```powershell
python .\src\tello_basic_flight.py check
```

成功すると、次のような情報が表示されます。

```text
Drone SDK version: ...
Battery: 85%
```

## 映像プレビュー

Tello EDUのWi-FiにPCを接続してから、プレビュー画面を起動します。

```powershell
python .\src\tello_video_preview.py
```

画面の **Connect** を押して接続し、**Start video** で映像を開始します。停止するときは **Stop video** を押します。この画面には飛行操作はありません。

## DualSenseによる手動操作

DualSenseをUSBでPCに接続し、Tello EDUのWi-Fiへ接続してから実行します。初回は入力軸とボタン番号を確認します。この確認モードはドローンに接続しません。

```powershell
python .\src\tello_controller.py --input-check
```

入力表示で左スティックとL2/R2の軸番号、Cross/Circle/L1のボタン番号を確認します。既定値は左スティック軸 `0/1`、L2/R2軸 `4/5`、Cross/Circle/L1ボタン `0/1/4` です。実機の表示が異なる場合は `--left-x-axis`、`--left-y-axis`、`--l2-axis`、`--r2-axis`、`--takeoff-button`、`--land-button`、`--deadman-button` で指定します。トリガーが休止時に `0` を表示する場合は `--trigger-rest 0` を指定します。

入力を確認したら、周囲の安全を確認して手動操作を開始します。

```powershell
python .\src\tello_controller.py --confirm-flight
```

PCのTello Wi-Fiアダプターが複数ある場合や接続に失敗する場合は、アダプターのIPアドレスを指定します。たとえば `192.168.10.2` の場合は次のように起動します。

```powershell
python .\src\tello_controller.py --local-ip 192.168.10.2 --confirm-flight
```

Crossで離陸、Circleで着陸します。飛行中にL1を押している間だけ左スティックとL2/R2の操作を有効にし、L1を離すとホバリング指令を送ります。左スティックは前後左右、L2は下降、R2は上昇です。初期のRC上限は30/100で、`--max-rc` で10から50の範囲に設定できます。旋回は無効です。入力確認・初回飛行では低い上限から始めてください。

ゲームパッドの切断や制御中のエラーを検出すると、プログラムは着陸を試みます。Wi-Fiが切断された場合は着陸指令が届かないため、機体を目視し、必要に応じて手動で対応してください。

接続に失敗する場合は、PCのTello Wi-FiアダプターのIPアドレスを指定します。

```powershell
python .\src\tello_video_preview.py --local-ip 192.168.10.2
```

## 接続に失敗する場合

Windowsでネットワークアダプタが複数ある場合、Tello EDU側のローカルIPを指定すると接続できる場合があります。

```powershell
python .\src\tello_basic_flight.py --local-ip 192.168.10.2 check
```

## 離陸してホバリング、着陸

接続確認が成功してから実行してください。
実際に飛行するため、誤実行防止として `--confirm-flight` が必要です。

```powershell
python .\src\tello_basic_flight.py --confirm-flight takeoff-land --hover-seconds 5
```

このコマンドでは、離陸して5秒ホバリングしたあとに着陸します。

## 離陸、前進、後退、着陸

接続確認と短時間ホバリングが成功してから実行してください。

```powershell
python .\src\tello_basic_flight.py --confirm-flight demo --distance-cm 50
```

このコマンドでは、離陸後に50cm前進し、50cm後退してから着陸します。
指定できる距離は `20` から `100` cm です。

距離を変更する場合は、`--distance-cm` の値を変更します。

```powershell
python .\src\tello_basic_flight.py --confirm-flight demo --distance-cm 30
```

## 実行中に止めたい場合

コンソールで `Ctrl+C` を押してください。
プログラムは可能な範囲で着陸を試みます。

## 終了手順

1. Tello EDU が着陸していることを確認する
2. PowerShell で必要な操作が終わっていることを確認する
3. Tello EDU の電源を切る
4. PCのWi-Fi接続を通常のネットワークに戻す

