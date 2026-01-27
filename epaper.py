from WebsiteUpdater import WebsiteUpdater
from IllustUpdater import IllustUpdater
from WeatherUpdater import WeatherUpdater
from StockUpdater import StockUpdater
from TrainUpdater import TrainUpdater
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
stockUpdater = StockUpdater()
trainUpdater = TrainUpdater()

while True:
    for updater in [newsUpdater, illustUpdater, weatherUpdater, stockUpdater, trainUpdater]:
        updater.update()
        time.sleep(15*60)


