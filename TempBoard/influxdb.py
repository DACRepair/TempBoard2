import datetime

from influxdb import InfluxDBClient


class InfluxPoint(object):
    def __init__(self, measurement: str, time: datetime.datetime, fields: dict, tags: dict):
        self.measurement = measurement
        self.tags = tags
        self.time = time
        self.fields = fields

    @property
    def point(self):
        return {
            "measurement": self.measurement,
            "tags": self.tags,
            "time": self.time,
            "fields": self.fields
        }


class InfluxDB:
    def __init__(self, host: str = "localhost", port: int = 8086, username: str = "root", password: str = "root",
                 database: str = None, **kwargs):
        self._client = InfluxDBClient(host, port, username, password, database, **kwargs)
        if database is not None and database not in [x['name'] for x in self._client.get_list_database()]:
            self._client.create_database(database)

    def write_points(self, points: [InfluxPoint, list]):
        if not isinstance(points, list):
            points = [points]
        points = [x.point for x in points]
        return self._client.write_points(points=points)
