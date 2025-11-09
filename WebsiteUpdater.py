import io
import os
import re
import time
from PIL import Image
import requests

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from ImageUpdater import ImageUpdater

class WebsiteUpdater(ImageUpdater):

    def __init__(self, urls):
        self.website_urls = urls
        super().__init__()


    def download_latest_ublock_firefox_xpi(self):
        dest_dir = "./ublock"
        os.makedirs(dest_dir, exist_ok=True)

        for file in os.listdir(dest_dir):
            if file.endswith(".firefox.signed.xpi"):
                return os.path.join(dest_dir, file)

        api = "https://api.github.com/repos/gorhill/uBlock/releases/latest"
        r = requests.get(api, timeout=30)
        r.raise_for_status()
        data = r.json()

        # uBlockのFirefox用xpi資産を探す（例: uBlock0_1.58.0.firefox.xpi）
        asset = None
        for a in data.get("assets", []):
            name = a.get("name", "")
            if name.endswith(".firefox.xpi") or name.endswith(".firefox.signed.xpi"):
                asset = a
                break
        else:
            raise RuntimeError("Firefox向けXPIが見つかりませんでした。")

        url = asset["browser_download_url"]
        xpi_path = os.path.join(dest_dir, asset["name"])
        with requests.get(url, timeout=60, stream=True) as rr:
            rr.raise_for_status()
            with open(xpi_path, "wb") as f:
                for chunk in rr.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return xpi_path

    def screen_shot(self, urls):
        xpi_path = self.download_latest_ublock_firefox_xpi()

        options = Options()
        options.add_argument("-headless")

        # 画面サイズ
        options.set_preference("layout.css.devPixelsPerPx", "1.0")

        driver = webdriver.Firefox(
            service = Service(),
            options=options
        )
        try:

            # uBlockを一時インストール
            driver.install_addon(xpi_path, temporary=True)

            outputs = []
            for url in urls:
                # アドオン初回タブなどが開くことがあるので、対象URLで上書き
                driver.get(url)
                driver.set_window_size(int(800*1.5), int(480*1.5))

                # DOMの安定待ち
                WebDriverWait(driver, 30).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                # uBlockのフィルタが効くまで、わずかに待機（広告DOMやネットワークの抑制が浸透）
                time.sleep(1.0)
                png_bytes = driver.get_screenshot_as_png()
                outputs.append(Image.open(io.BytesIO(png_bytes)))
            return outputs
            
        finally:
            driver.quit()
    
    def update(self):
        imgs = self.screen_shot(self.website_urls)
        self.image_request(imgs)

if __name__ == "__main__":
    updater = WebsiteUpdater([
        "https://www.google.com/",
        "https://www.yahoo.co.jp/",
        "https://www.bing.com/?cc=jp"
    ])
    updater.update()