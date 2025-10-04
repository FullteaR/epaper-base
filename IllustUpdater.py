from ImageUpdater import ImageUpdater
import os
import random
from PIL import Image


class IllustUpdater(ImageUpdater):
    def __init__(self, base_folder):
        super().__init__()
        self.base_folder = base_folder
        self.__reload_images()

    def __reload_images(self):
        self.files = os.listdir(self.base_folder)
        while len(self.files)<len(self.urls):
            self.files.append(random.choice(os.listdir(self.base_folder)))
        random.shuffle(self.files)

    def update(self):
        if len(self.files)>=len(self.urls):
            pathes = [os.path.join(self.base_folder, self.files.pop(0)) for i in range(len(self.urls))]
            imgs = [Image.open(path) for path in pathes]
            self.image_request(imgs)
        else:
            self.__reload_images()
            self.update()

if __name__ == "__main__":
    updater = IllustUpdater("./images/sample")
    updater.update()