import os
from configparser import ConfigParser


class Config:
    def __init__(self, config_file: str = None):
        if config_file is None:
            config_file = os.getcwd() + "/config.ini"
        config_file = os.path.normpath(config_file)
        self._config = ConfigParser()
        if os.path.isfile(config_file):
            self._config.read(config_file)

    @staticmethod
    def _gen_env(section: str, option: str):
        return section.upper() + "__" + option.upper()

    def get(self, section: str, option: str, default=None, wrap=None):
        value = os.getenv(self._gen_env(section, option), self._config.get(section, option, fallback=default))
        if callable(wrap):
            if isinstance(wrap(), bool):
                value = str(value)
                if value.lower() == 'true' or str(value) == "1" or str(value).lower() == 'y':
                    value = True
                elif value.lower() == 'false' or str(value) == "0" or str(value).lower() == 'n':
                    value = False
                else:
                    value = default
            else:
                value = wrap(value)
        return value
