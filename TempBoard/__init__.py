import asyncio
import datetime
from collections import OrderedDict

from flask_admin import expose
from flask_admin.contrib.sqla import ModelView

from .config import Config
from .influxdb import InfluxDB, InfluxPoint
from .serial import Serial
from .settings import Settings, SettingView
from .storage import Session, Base, Sensor, Reading
from .webserver import WebServer, IndexView


class TempIndexView(IndexView):
    @expose('/')
    def index(self):
        def avg(li: list):
            if len(li) > 0:
                return sum(li) / len(li)
            else:
                return 0

        def split_rows(di: dict, interval: int = 0):
            data = {x: {} for x in range(interval)}
            start = 0
            for key, value in di.items():
                start = start if start < interval else 0
                data[start].update({key: value})
                start += 1
            return data

        ses = Session()
        now = datetime.datetime.utcnow().replace(microsecond=0)
        data = {}

        # Temp Averages (30 days, 7 days, 24 hours, and numeric. with last period overlay)
        last_thirty = [d for d in range((now - (now - datetime.timedelta(days=30))).days)]
        last_thirty = [(now - datetime.timedelta(days=d)) for d in last_thirty]
        avg_thirty = OrderedDict({x: round(avg([d.sensor_value for d in ses.query(Reading).filter(
            Reading.reading_date.between(x.replace(hour=0, minute=0, second=0),
                                         x.replace(hour=23, minute=59, second=59))).all()]), 2) for x in
                                  last_thirty})
        avg_thirty = OrderedDict({x.strftime("%Y-%m-%d"): y for x, y in avg_thirty.items()})
        data.update({"avg_thirty_max": max(avg_thirty.values()),
                     "avg_thirty_min": min(avg_thirty.values()) if min(avg_thirty.values()) < 0 else 0})
        data.update({"avg_thirty_max": data["avg_thirty_max"] + (data["avg_thirty_max"] / 2)})
        data.update({"avg_thirty": OrderedDict({x: str(y) for x, y in avg_thirty.items()})})

        last_seven = [d for d in range((now - (now - datetime.timedelta(days=7))).days)]
        last_seven = [(now - datetime.timedelta(days=d)) for d in last_seven]
        avg_seven = OrderedDict({x: round(avg([d.sensor_value for d in ses.query(Reading).filter(
            Reading.reading_date.between(x.replace(hour=0, minute=0, second=0),
                                         x.replace(hour=23, minute=59, second=59))).all()]), 2) for x in last_seven})
        avg_seven = OrderedDict({x.strftime("%Y-%m-%d"): y for x, y in avg_seven.items()})
        data.update({"avg_seven_max": max(avg_seven.values()),
                     "avg_seven_min": min(avg_seven.values()) if min(avg_seven.values()) < 0 else 0})
        data.update({"avg_seven_max": data["avg_seven_max"] + (data["avg_seven_max"] / 2)})
        data.update({"avg_seven": OrderedDict({x: str(y) for x, y in avg_seven.items()})})

        last_day = divmod(divmod((now.replace(hour=0, minute=0, second=0) - now).seconds, 60)[0], 60)[0]
        last_day = [h for h in range(last_day)]
        first_hour = now.replace(hour=0, minute=0, second=0)
        avg_day = OrderedDict({x: round(avg([y.sensor_value for y in ses.query(Reading).filter(
            Reading.reading_date.between(first_hour.replace(hour=x),
                                         first_hour.replace(hour=x, minute=59, second=58)))]), 2) for x in last_day})
        avg_day = OrderedDict(
            {(now - datetime.timedelta(hours=x)).strftime("%Y-%m-%d %H:%M:%S"): y for x, y in avg_day.items()})
        data.update({"avg_day_max": max(avg_day.values()),
                     "avg_day_min": min(avg_day.values()) if min(avg_day.values()) < 0 else 0})
        data.update({"avg_day_max": data["avg_day_max"] + (data["avg_day_max"] / 2)})
        data.update({"avg_day": OrderedDict({x: str(y) for x, y in avg_day.items()})})

        # Sensor Table
        last_reading = {s.sensor_name: ses.query(Reading).filter(Reading.sensor_id == s.sensor_id).order_by(
            Reading.reading_date.desc()).first() for s in ses.query(Sensor).all()}
        last_reading = {
            k: v.sensor_value if v is not None and v.reading_date > (now - datetime.timedelta(minutes=1)) else 0 for
            k, v in last_reading.items()}
        data.update({"last_reading": split_rows(last_reading, 3)})

        # Current Avg Temp
        data.update({"avg_current": str(round(avg([x for x in last_reading.values()]), 2))})

        return self.render('index.html', data=data)


class TempBoard(Serial):
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.config = Config()

        super(TempBoard, self).__init__(self.config.get('serial', 'port', None),
                                        self.config.get('serial', 'baud', default=115200, wrap=int))

        self.session = Session()
        Base.metadata.create_all()

        self.settings = Settings(self.session)

        self.webserver = WebServer(index_view=TempIndexView(url='/'), title=self.settings.site_name,
                                   username=self.settings.username, password=self.settings.password)
        self.webserver.admin.add_view(ModelView(Sensor, self.session, name="Sensors"))
        self.webserver.admin.add_view(SettingView(Settings.model, self.session, name="Settings"))

        self.influx = None

    @staticmethod
    def c_to_f(c: float):
        return c * 1.8 + 32

    async def on_start(self):
        print("Monitor Online")
        self.loop.create_task(self.task_influx())
        self.loop.create_task(self.task_cleanup())
        self.loop.create_task(self.task_webserver())

    async def on_reading(self, reading):
        address = reading.get("sensor", None)
        temp = reading.get("temp")
        if address is not None:
            if self.session.query(Sensor).filter(Sensor.sensor_addr == address).count() < 1:
                self.session.add(Sensor(sensor_addr=address, sensor_name=address))
                self.session.commit()

            sensor: Sensor = self.session.query(Sensor).filter(Sensor.sensor_addr == address).first()
            now = datetime.datetime.utcnow().replace(microsecond=0)
            last: Reading = self.session.query(Reading.reading_date).filter(
                Reading.sensor_id == sensor.sensor_id).order_by(Reading.reading_date.desc()).first()
            store = False
            if last is not None:
                if last.reading_date + datetime.timedelta(
                        seconds=self.config.get('serial', 'rate', default=0, wrap=int)) < now:
                    store = True
            else:
                store = True
            if store:
                self.session.add(Reading(
                    reading_date=now,
                    sensor_id=int(sensor.sensor_id),
                    sensor_value=temp
                ))
                self.session.commit()
                if self.influx is not None:
                    tags = {y[0]: y[1] for y in
                            [x.split("=") for x in self.settings.influx_tags.replace(" ", "").split(",")]}
                    tags.update({"sensor": sensor.sensor_addr, "name": sensor.sensor_name})
                    fields = {"celsius": temp, "fahrenheit": self.c_to_f(temp)}
                    point = InfluxPoint("temperature", time=now, fields=fields, tags=tags)
                    self.influx.write_points([point])

    async def task_webserver(self):
        host = self.config.get('webserver', 'host', '127.0.0.1')
        port = self.config.get('webserver', 'port', '8080', wrap=int)
        return await self.webserver.run_async(host, port)

    async def task_influx(self):
        while True:
            if self.settings.influx_enable and self.influx is None:
                print("Enabling InfluxDB")
                try:
                    self.influx = InfluxDB(host=self.settings.influx_host,
                                           port=self.settings.influx_port,
                                           username=self.settings.influx_username,
                                           password=self.settings.influx_password,
                                           database=self.settings.influx_database,
                                           ssl=self.settings.influx_ssl,
                                           verify_ssl=self.settings.influx_verify,
                                           timeout=self.settings.influx_timeout,
                                           retries=self.settings.influx_retries,
                                           use_udp=self.settings.influx_udp,
                                           udp_port=self.settings.influx_port
                                           )
                except ConnectionError:
                    print("Error - Cannot connect to InfluxDB")
            if not self.settings.influx_enable and self.influx is not None:
                print("Disabling InfluxDB")
                self.influx = None

            await asyncio.sleep(5)

    async def task_cleanup(self, days: int = 64, orphan: bool = True):
        while True:
            if days > 0:
                data = self.session.query(Reading).filter(
                    Reading.reading_date < (datetime.datetime.utcnow() - datetime.timedelta(days=days)))
                clean_count = data.count()
                data.delete(synchronize_session='fetch')
            else:
                clean_count = 0

            if orphan:
                sensors = [x[0] for x in self.session.query(Reading.sensor_id).group_by(Reading.sensor_id).all()]
                orphans = self.session.query(Sensor).filter(~Sensor.sensor_id.in_(sensors))
                orphan_count = orphans.count()
                orphans.delete(synchronize_session='fetch')
            else:
                orphan_count = 0

            if (clean_count > 0 or orphan_count > 0) and not (clean_count == 0 and orphan_count == 0):
                self.session.commit()

            print("Cleaned: {} old readings, {} orphaned sensors.".format(clean_count, orphan_count))
            await asyncio.sleep(1800)
