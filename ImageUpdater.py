import requests
import io
import functools
from PIL import Image
from tqdm.contrib.concurrent import thread_map

class ImageUpdater():

    def __init__(self):
        self.urls = [
            "http://display1.raspi.rikuta:8000/display",
            "http://display2.raspi.rikuta:8000/display",
            "http://display3.raspi.rikuta:8000/display",
        ]

    def __send_image(self, image: Image.Image, url: str, session=None):
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)

        files = {"image": ("image.png", buf, "image/png")}
        params= {"force": False}
        try:
            resp = session.post(url, params=params,files=files, timeout=60)
            resp.raise_for_status()
            return url, resp.status_code, resp.text
        except Exception as e:
            return url, None, str(e)

    def image_request(self, images):
        assert len(images) == len(self.urls)
        with requests.Session() as session:
            tasks = list(zip(images, self.urls))
            bound = functools.partial(self.__send_image, session=session)
            results = thread_map(
                lambda args: bound(*args),  # (image, url) を展開
                tasks,
                max_workers=len(tasks),
                chunksize=1,
                desc="Uploading images"
            )
        return results
    
    def update(self):
        raise Exception("Please override this function.")