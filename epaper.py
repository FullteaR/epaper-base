from WebsiteUpdater import WebsiteUpdater
from IllustUpdater import IllustUpdater
from WeatherUpdater import WeatherUpdater
from StockUpdater import StockUpdater
from TrainUpdater import TrainUpdater
from ExhibitionUpdater import ExhibitionUpdater
from PrometheusUpdater import PrometheusUpdater
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
exhibitionUpdater = ExhibitionUpdater()
prometheusUpdater = PrometheusUpdater()

while True:
    for updater in [trainUpdater, newsUpdater, illustUpdater, weatherUpdater, stockUpdater, exhibitionUpdater, prometheusUpdater]:
        try:
            updater.update()
            time.sleep(15*60)
        except:
            continue


