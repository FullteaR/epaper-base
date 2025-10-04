from ImageUpdater import ImageUpdater
from PIL import Image

class TestUpdater(ImageUpdater):

    def __init__(self):
        super().__init__()

    def update(self):
        imgs = [
            Image.new("RGB", (800, 480), color=(255, 0, 0)),
            Image.new("RGB", (800, 480), color=(0, 255, 0)),
            Image.new("RGB", (800, 480), color=(0, 0, 255)),
        ]
        self.image_request(imgs)


if __name__=="__main__":
    updater = TestUpdater()
    updater.update()