import logging
import time
import sys
import yaml
from driver import *
import zmq
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import uuid

class Agent(object):
    def __init__(self, controller):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.log.debug("Controller: {0}".format(controller))
        self.config = None
        self.driver_port = 5000
        self.myUuid = uuid.uuid4()
        self.myId = str(self.myUuid)

        self.jobScheduler = BackgroundScheduler()
        self.jobScheduler.start()

        self.poller = zmq.Poller()
        self.context = zmq.Context()
        self.socket_sub = self.context.socket(zmq.SUB) # for downlink communication with controller
        self.socket_pair = self.context.socket(zmq.PAIR) # for setup of communication between controller

        #register driver socket in poller
        self.poller.register(self.socket_sub, zmq.POLLIN)
        self.poller.register(self.socket_pair, zmq.POLLIN)

    drivers = {}
    driver_groups = {}

    def read_config_file(self, path=None):
        self.log.debug("Path to driver: {0}".format(path))

        with open(path, 'r') as f:
           config = yaml.load(f)

        return config

    def load_drivers(self, config):
        self.log.debug("Config: {0}".format(config))

        for driver_name, driver_parameters in config.iteritems():
            self.driver_port += 1
            self.add_driver(
                driver_parameters['message_type'],
                self.exec_driver(
                        name=driver_name,
                        path=driver_parameters['path'],
                        args=driver_parameters['args'],
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

        #register driver socket in poller
        self.poller.register(driver.socket, zmq.POLLIN)
        pass

    def send_msg_to_driver(self, driver_name, msgType, msg):
        self.drivers[driver_name].send_msg_to_driver(msgType, msg)
        pass

    def send_msg_to_driver_group(self, msgType, msgContainer):
        msg = msgContainer[1]
        driver_name_list = self.driver_groups[msgType]
        for driver_name in driver_name_list:
            self.send_msg_to_driver(driver_name, msgType, msg)
        pass

    def setup_connection_to_controller(self, msg):
        controllerIp = msg #TODO: define profobuf msg
        self.socket_pair.connect(controllerIp)

        msgType = "NEW_NODE_MSG"
        msg = self.myId
        newNodeMsg = [msgType, msg]

        self.log.debug("Agent sends context-setup request to controller")
        self.socket_pair.send_multipart(newNodeMsg)

    def send_driver_response_to_controller(self, msgContainer):
        self.socket_pair.send_multipart(msgContainer)

    def setup_connection_to_controller_complete(self, msgContainer):
        assert len(msgContainer)
        msgType = msgContainer[0]
        msg = msgContainer[1]

        self.log.debug("Controller confirms creation of context for Agent with msg: {0}::{1}".format(msgType,msg))

        self.log.debug("Agent connect its SUB to Controller's PUT socket and subscribe for topics")
        self.socket_sub.setsockopt(zmq.SUBSCRIBE,  self.myId)
        topicfilter = "RADIO"
        self.socket_sub.setsockopt(zmq.SUBSCRIBE, topicfilter)
        topicfilter = "PERFORMANCE_TEST"
        self.socket_sub.setsockopt(zmq.SUBSCRIBE, topicfilter)

        self.socket_sub.connect(msg)

    def processAgentManagementMsg(self, msgContainer):
        assert len(msgContainer)
        msgType = msgContainer[0]
        msg = msgContainer[1]

        if msgType == "NEW_NODE_ACK":
            self.setup_connection_to_controller_complete(msgContainer)
        else:
            pass

    def send_msg_now(self, msgContainer):
        msgType = msgContainer[0]
        msg = msgContainer[1]
        self.log.debug("Agent sends message: {0}::{1} to driver".format(msgType, msg))
        self.send_msg_to_driver_group(msgType, msgContainer)

    def send_scheduled_msg(self, msgContainer):
        msgType = msgContainer[0]
        msg = msgContainer[1]
        self.log.debug("Agent sends scheduled message: {0}::{1} to driver".format(msgType, msg))
        self.send_msg_to_driver_group(msgType, msgContainer)

    def schedule_msg(self, delay, msgContainer):
        msgType = msgContainer[0]
        msg = msgContainer[1]
        self.log.debug("Agent schedule task for message: {0}::{1} in {2}s".format(msgType, msg, delay))

        execTime = (datetime.datetime.now() + datetime.timedelta(seconds=delay))
        self.jobScheduler.add_job(self.send_scheduled_msg, 'date', run_date=execTime, kwargs={'msgContainer' : msgContainer})

    def process_msgs(self):
        # Work on requests from both controller and drivers
        while True:
            socks = dict(self.poller.poll())

            for name, driver in self.drivers.iteritems():
                if driver.socket in socks and socks[driver.socket] == zmq.POLLIN:
                    msgContainer = driver.socket.recv_multipart()

                    assert len(msgContainer)
                    msgType = msgContainer[0]
                    msg = msgContainer[1]

                    self.log.debug("Agent received message: {0}::{1} from driver: {2}".format(msgType, msg, name))
                    if msgType == "CONTROLLER_DISCOVERED":
                        self.log.debug("Agent {0} discovered controller: {1} and connects to it".format(name, msg))
                        self.setup_connection_to_controller(msg)
                    else:
                        self.log.debug("Agent sends message to Controller: {0}::{1}".format(msgType, msg))
                        self.send_driver_response_to_controller(msgContainer)

            if self.socket_pair in socks and socks[self.socket_pair] == zmq.POLLIN:
                msgContainer = self.socket_pair.recv_multipart()

                assert len(msgContainer)
                msgType = msgContainer[0]
                msg = msgContainer[1]
                delay = int(msgContainer[3])
                self.log.debug("Agent received message: {0}::{1} from controller using PAIR".format(msgType, msg))
                self.processAgentManagementMsg(msgContainer)

            if self.socket_sub in socks and socks[self.socket_sub] == zmq.POLLIN:
                msgContainer = self.socket_sub.recv_multipart()

                assert len(msgContainer)
                msgType = msgContainer[0]
                msg = msgContainer[1]
                delay = int(msgContainer[3])
                self.log.debug("Agent received message: {0}::{1} from controller using SUB".format(msgType, msg))

                self.log.debug("Agent serves command: {0}::{1} from controller".format(msgType, msg))
                if delay == 0:
                    self.send_msg_now(msgContainer)
                else:
                    self.schedule_msg(delay, msgContainer)


    def run(self):
        self.log.debug("Agent starting".format())
        try:
            self.process_msgs()

        except KeyboardInterrupt:
            self.log.debug("Agent exits")
            self.log.debug("Kills all drivers' subprocesses")
            for name, driver in self.drivers.iteritems():
                driver.kill_driver_subprocess()
            self.jobScheduler.shutdown()
            self.socket_sub.close()
            self.socket_pair.close()
            self.context.term()

        except:
            self.log.debug("Unexpected error:".format(sys.exc_info()[0]))
            self.log.debug("Kills all drivers' subprocesses")
            for name, driver in self.drivers.iteritems():
                driver.kill_driver_subprocess()
            self.jobScheduler.shutdown()
            self.socket_sub.close()
            self.socket_pair.close()
            self.context.term()