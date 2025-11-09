from WebsiteUpdater import WebsiteUpdater
from IllustUpdater import IllustUpdater
from WeatherUpdater import WeatherUpdater
import time

illustUpdater = IllustUpdater("./images/illust")
newsUpdater = WebsiteUpdater(
    [
        "https://www.cnn.co.jp/",
        "https://www.bbc.com/japanese",
        "https://www.bloomberg.co.jp/"
    ]
)
weatherUpdater = WeatherUpdater()

while True:
    for updater in [newsUpdater, illustUpdater, weatherUpdater]:
        updater.update()
        time.sleep(15*60)


