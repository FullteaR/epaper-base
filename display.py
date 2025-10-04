# This is for raspberry pi zero with waveshare epaper display

import os
import io
import time
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from flask import Flask, request, jsonify, abort, make_response

# Waveshare EPD ライブラリのパス追加（必要なら）
LIBDIR = "/home/rikuta/e-Paper/RaspberryPi_JetsonNano/python/lib"
if os.path.exists(LIBDIR):
    import sys
    sys.path.append(LIBDIR)

from waveshare_epd import epd7in3f   # 7.3" EPD
from PIL import Image

TARGET_WIDTH = 800
TARGET_HEIGHT = 480
MIN_REFRESH_INTERVAL = 5 * 60  # 5 minutes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def trim_to_800x480(image: Image.Image) -> Image.Image:
    width, height = image.size
    target_ratio = TARGET_WIDTH / TARGET_HEIGHT
    current_ratio = width / height

    if current_ratio > target_ratio:
        new_height = TARGET_HEIGHT
        new_width = int(width * (TARGET_HEIGHT / height))
        image = image.resize((new_width, new_height), Image.LANCZOS)
        left = (new_width - TARGET_WIDTH) // 2
        image = image.crop((left, 0, left + TARGET_WIDTH, TARGET_HEIGHT))
    else:
        new_width = TARGET_WIDTH
        new_height = int(height * (TARGET_WIDTH / width))
        image = image.resize((new_width, new_height), Image.LANCZOS)
        top = (new_height - TARGET_HEIGHT) // 2
        image = image.crop((0, top, TARGET_WIDTH, top + TARGET_HEIGHT))

    return image.convert("RGB")


class EPDController:
    """EPD を安全に直列制御するためのラッパー（非永続・プロセス内のみ状態保持）。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._epd = None  # 遅延初期化
        self._last_update: Optional[float] = None
        logging.info("EPDController initialized (no persistence).")

    @property
    def last_update(self) -> Optional[float]:
        return self._last_update

    def can_update_now(self, force: bool) -> tuple[bool, int]:
        if force or self._last_update is None:
            return True, 0
        elapsed = time.time() - self._last_update
        if elapsed >= MIN_REFRESH_INTERVAL:
            return True, 0
        return False, int(MIN_REFRESH_INTERVAL - elapsed)

    def _ensure_epd(self):
        if self._epd is None:
            self._epd = epd7in3f.EPD()

    def display_image_and_sleep(self, pil_image: Image.Image):
        with self._lock:
            self._ensure_epd()
            self._epd.init()
            img = trim_to_800x480(pil_image)
            self._epd.display(self._epd.getbuffer(img))
            self._epd.sleep()
            self._last_update = time.time()
            logging.info("EPD updated and put to sleep.")

    def hard_clear(self):
        with self._lock:
            self._ensure_epd()
            self._epd.init()
            self._epd.Clear()
            self._epd.sleep()
            logging.info("EPD hard cleared and slept.")


def create_app() -> Flask:
    app = Flask(__name__)
    controller = EPDController()

    @app.route("/health", methods=["GET"])
    def health():
        last_ts = controller.last_update
        if last_ts is None:
            status = {"status": "ok", "last_update": None, "seconds_since_last": None}
        else:
            status = {
                "status": "ok",
                "last_update": datetime.fromtimestamp(last_ts, tz=timezone.utc).isoformat(),
                "seconds_since_last": int(time.time() - last_ts),
            }
        return jsonify(status)

    @app.route("/last_update", methods=["GET"])
    def last_update():
        last_ts = controller.last_update
        if last_ts is None:
            return jsonify({"last_update": None})
        return jsonify(
            {
                "last_update": datetime.fromtimestamp(last_ts, tz=timezone.utc).isoformat(),
                "epoch": last_ts,
            }
        )

    @app.route("/display", methods=["POST"])
    def display():
        """
        画像を表示するエンドポイント。
        - multipart/form-data で 'image' フィールドに画像を送る
        - または、リクエストボディに生バイナリを送り、Content-Type: image/* を付与
        - ?force=true でクールダウン無視
        """
        force = request.args.get("force", "false").lower() in ("1", "true", "yes", "on")

        can, wait_sec = controller.can_update_now(force=force)
        if not can:
            resp = make_response(
                jsonify(
                    {
                        "error": "Too Many Requests",
                        "message": "EPD refresh interval is 5 minutes. Use ?force=true to override.",
                        "retry_after_seconds": wait_sec,
                    }
                ),
                429,
            )
            resp.headers["Retry-After"] = str(wait_sec)
            return resp

        pil_img = None
        if "image" in request.files and request.files["image"].filename:
            pil_img = Image.open(request.files["image"].stream).convert("RGB")
        elif request.data and request.content_type and request.content_type.startswith("image/"):
            pil_img = Image.open(io.BytesIO(request.data)).convert("RGB")

        if pil_img is None:
            abort(
                make_response(
                    jsonify(
                        {
                            "error": "Unsupported Media Type",
                            "message": "Send image via multipart 'image' field or raw body with Content-Type: image/*",
                        }
                    ),
                    415,
                )
            )

        try:
            controller.display_image_and_sleep(pil_img)
        except Exception as e:
            logging.exception("Display failed:")
            abort(make_response(jsonify({"error": "DisplayFailed", "message": str(e)}), 500))

        return jsonify({"status": "ok", "forced": force})

    @app.route("/clear", methods=["POST"])
    def clear():
        try:
            controller.hard_clear()
            return jsonify({"status": "ok"})
        except Exception as e:
            logging.exception("Clear failed:")
            abort(make_response(jsonify({"error": "ClearFailed", "message": str(e)}), 500))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, threaded=True)