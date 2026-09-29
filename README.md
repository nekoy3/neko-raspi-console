# Neko Raspberry Pi Console

HTTPS対応のUSBシリアルコンソールWebGUI。OSシェルの公開機能はありません。

## 起動

Python 3.13 / OpenSSL / systemdと、シリアルへの読み書き権限が必要です。

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
umask 077
.venv/bin/python initialize.py
openssl req -x509 -newkey rsa:3072 -nodes -keyout data/key.pem -out data/cert.pem -days 365 -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
.venv/bin/python server.py
```

初期パスワードは `data/login-password.txt` に生成されます。認証・証明書の初期化は既存データを上書きしないよう管理してください。証明書の信頼確認は利用者が行います。

設定項目は `.env.example` を参照。systemdで使う実設定は `data/deployment.env` に600で置きます（Git対象外）。LAN公開時は実ホスト名をHost許可と証明書SANに指定し、接続元範囲を適切に制限してください。サービス定義は配置先 `~/console-server` を想定しています。自動起動にはユーザーlingerが必要です。

## 安全性

- 受信のみが初期状態。入力有効化と貼り付けは確認付き。
- ポート単位の排他接続、接続中の速度変更禁止。
- パスワード照合はscrypt。HTTPS・Secure/HttpOnly/SameSite Cookie、Origin/Host検証。
- コンソール本文は保存せず、接続等のメタデータのみ記録（2MiB・旧世代3本）。
- Webからの切断は機器上のログアウトではありません。CLIでログアウトしてから切断してください。

## 機密情報の扱い

認証データ、初期パスワード、秘密鍵、証明書、実環境設定、ログ、実機出力、内部インベントリをコミットしないでください。`.gitignore`だけに依存せず、履歴を含むsecret scanを行います。詳細は `docs/SECURITY.md`。

同梱ライブラリ: xterm.js 6.0.0 / addon-fit 0.11.0（ライセンスはstatic/vendor）、aiohttp 3.14.3 / pySerial 3.5。

テスト: `.venv/bin/python verify_pty.py`（疑似端末のみ、実機には送信しません）。
