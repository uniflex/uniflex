import logging
import time
import yaml
from driver import *

class Agent(object):
    def __init__(self, controller):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.log.debug("Controller: {0}".format(controller))
        self.config = None
        self.driver_port = 5000
        pass

    drivers = {}
    driver_groups = {}

    def read_config_file(self, path=None):
        self.log.debug("Path to driver: {0}".format(path))

        with open(path, 'r') as f:
           config = yaml.load(f)

        return config

    def load_drivers(self, config):
        self.log.debug("Config: {0}".format(config))

        for key, value in config.iteritems():
            self.driver_port += 1
            self.add_driver(
                value['message_type'],
                self.exec_driver(
                        name=key,
                        path=value['path'],
                        args=value['args'],
                        port=self.driver_port
                )
            )
        pass

    def exec_driver(self, name, path, args, port):
        new_driver = Driver(name, path, args, port)
        return new_driver

    def add_driver(self, message_types, driver):
        self.log.debug("Adding new driver: {0}".format(driver))
        self.drivers[driver.name] = driver

        for message_type in message_types:
            if message_type in self.driver_groups.keys():
                self.driver_groups[message_type].append(driver.name)
            else:
                self.driver_groups[message_type] = [driver.name]
        pass

    def send_msg_to_driver(self, driver_name, msg):
        self.drivers[driver_name].send_msg(msg)
        pass

    def send_msg_to_driver_group(self, message_type_name, msg):
        driver_name_list = self.driver_groups[message_type_name]
        for driver_name in driver_name_list:
            self.send_msg_to_driver(driver_name, msg)
        pass

    def run(self):
        self.log.debug("Agent starting".format())
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print "Good bye"

        pass