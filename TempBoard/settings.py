from flask_admin.contrib.sqla import ModelView

from .storage import Setting, Session


class SettingView(ModelView):
    form_columns = ["setting_name", "setting_value"]
    column_list = form_columns


class Settings(object):
    model = Setting

    def __init__(self, session: Session()):
        self.session = session
        self.__setup__()

    def __setup__(self):
        defaults = {
            'site_name': 'Temp Monitor',
            'username': 'admin',
            'password': 'admin',
            'influx_enable': 'Y',
            'influx_host': '127.0.0.1',
            'influx_port': '8086',
            'influx_ssl': 'N',
            'influx_verify': 'N',
            'influx_username': None,
            'influx_password': None,
            'influx_database': 'influxdb',
            'influx_timeout': '300',
            'influx_retries': '3',
            'influx_udp': 'N',
            'influx_tags': 'region=lab,host=temp-monitor'
        }
        for key in defaults.keys():
            data = self.session.query(Setting).filter(Setting.setting_name == key)
            if not data.count() == 1:
                data.delete()
                self.session.commit()
                self.session.add(Setting(setting_name=key, setting_value=defaults[key]))
                self.session.commit()

    def __query__(self, item):
        data = self.session.query(Setting).filter(Setting.setting_name == item)
        if data.count() == 1:
            return data.first().setting_value
        else:
            return None

    @property
    def site_name(self) -> str:
        return self.__query__("site_name")

    @property
    def username(self) -> str:
        return self.__query__('username')

    @property
    def password(self) -> str:
        return self.__query__('password')

    @property
    def influx_enable(self) -> bool:
        if self.__query__("influx_enable").lower() in ('y', 'yes', '1', 'true'):
            return True
        else:
            return False

    @property
    def influx_host(self) -> str:
        return self.__query__("influx_host")

    @property
    def influx_port(self) -> int:
        return int(self.__query__("influx_port"))

    @property
    def influx_ssl(self) -> bool:
        if self.__query__("influx_ssl").lower() in ('y', 'yes', '1', 'true'):
            return True
        else:
            return False

    @property
    def influx_verify(self) -> bool:
        if self.__query__("influx_verify").lower() in ('y', 'yes', '1', 'true'):
            return True
        else:
            return False

    @property
    def influx_username(self) -> str:
        return self.__query__("influx_username")

    @property
    def influx_password(self) -> str:
        return self.__query__("influx_password")

    @property
    def influx_database(self) -> str:
        return self.__query__("influx_database")

    @property
    def influx_timeout(self) -> int:
        return int(self.__query__("influx_timeout"))

    @property
    def influx_retries(self) -> int:
        return int(self.__query__("influx_retries"))

    @property
    def influx_udp(self) -> bool:
        if self.__query__("influx_udp").lower() in ('y', 'yes', '1', 'true'):
            return True
        else:
            return False

    @property
    def influx_tags(self) -> str:
        return self.__query__("influx_tags")
