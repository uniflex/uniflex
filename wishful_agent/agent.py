import logging
import time
import sys
import yaml
from agent_module import *
import zmq
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import uuid

__author__ = "Piotr Gawlowicz, Mikolaj Chwalisz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz, chwalisz}@tkn.tu-berlin.de"

class Agent(object):
    def __init__(self, controller):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.log.debug("Controller: {0}".format(controller))
        self.config = None
        self.myUuid = uuid.uuid4()
        self.myId = str(self.myUuid)

        self.jobScheduler = BackgroundScheduler()
        self.jobScheduler.start()

        self.poller = zmq.Poller()
        self.context = zmq.Context()
        self.socket_sub = self.context.socket(zmq.SUB) # for downlink communication with controller
        self.socket_sub.setsockopt(zmq.SUBSCRIBE,  self.myId)
        self.socket_pub = self.context.socket(zmq.PUB) # for uplink communication with controller

        #register module socket in poller
        self.poller.register(self.socket_sub, zmq.POLLIN)

    modules = {}
    module_groups = {}

    def read_config_file(self, path=None):
        self.log.debug("Path to module: {0}".format(path))

        with open(path, 'r') as f:
           config = yaml.load(f)

        return config

    def load_modules(self, config):
        self.log.debug("Config: {0}".format(config))

        for module_name, module_parameters in config.iteritems():
            self.add_module(
                module_parameters['message_type'],
                self.exec_module(
                        name=module_name,
                        path=module_parameters['path'],
                        args=module_parameters['args']
                )
            )
        pass


    def exec_module(self, name, path, args):
        new_module = AgentModule(name, path, args)
        return new_module

    def add_module(self, message_types, module):
        self.log.debug("Adding new module: {0}".format(module))
        self.modules[module.name] = module

        for message_type in message_types:
            if message_type in self.module_groups.keys():
                self.module_groups[message_type].append(module.name)
            else:
                self.module_groups[message_type] = [module.name]

        #register module socket in poller
        self.poller.register(module.socket, zmq.POLLIN)
        pass

    def send_msg_to_module(self, module_name, msgContainer):
        self.modules[module_name].send_msg_to_module(msgContainer)
        pass

    def send_msg_to_module_group(self, msgContainer):
        group = msgContainer[0]
        msgType = msgContainer[1]
        msg = msgContainer[2]
        module_name_list = self.module_groups[msgType]
        for module_name in module_name_list:
            self.send_msg_to_module(module_name, msgContainer)
        pass

    def setup_connection_to_controller(self, msgContainer):
        group = msgContainer[0]
        msgType = msgContainer[1]
        msg = msgContainer[2]
        controllerIp = msg #TODO: define profobuf msg
        self.socket_pub.connect(controllerIp)
        self.socket_sub.connect("tcp://127.0.0.1:8990") # TODO: downlink and uplink in config file

        group = "NEW_NODE_MSG"
        msgType = "NEW_NODE_MSG"
        msg = self.myId
        msgContainer = [group, msgType, msg]

        self.log.debug("Agent sends context-setup request to controller")
        time.sleep(1) # TODO: are we waiting for connection?
        self.socket_pub.send_multipart(msgContainer)

    def setup_connection_to_controller_complete(self, msgContainer):
        assert len(msgContainer)
        group = msgContainer[0]
        msgType = msgContainer[1]
        msg = msgContainer[2]

        self.log.debug("Controller confirms creation of context for Agent with msg: {0}::{1}".format(msgType,msg))

        #TODO: subscribe to reveiced topics
        self.log.debug("Agent connect its SUB to Controller's PUT socket and subscribe for topics")
        self.socket_sub.setsockopt(zmq.SUBSCRIBE,  self.myId)
        topicfilter = "RADIO"
        self.socket_sub.setsockopt(zmq.SUBSCRIBE, topicfilter)
        topicfilter = "PERFORMANCE_TEST"
        self.socket_sub.setsockopt(zmq.SUBSCRIBE, topicfilter)


    def process_msgs(self):
        # Work on requests from both controller and modules
        while True:
            socks = dict(self.poller.poll())

            for name, module in self.modules.iteritems():
                if module.socket in socks and socks[module.socket] == zmq.POLLIN:
                    msgContainer = module.socket.recv_multipart()

                    assert len(msgContainer) == 3
                    group = msgContainer[0]
                    msgType = msgContainer[1]
                    msg = msgContainer[2]

                    if not group:
                        self.log.debug("Field group not set -> set UUID".format())
                        msgContainer[0] = self.myId

                    self.log.debug("Agent received message: {0}::{1} from module: {2}".format(msgType, msg, name))
                    if msgType == "CONTROLLER_DISCOVERED":
                        self.log.debug("Agent {0} discovered controller: {1} and connects to it".format(name, msg))
                        self.setup_connection_to_controller(msgContainer)
                    else:
                        self.log.debug("Agent sends message to Controller: {0}::{1}".format(msgType, msg))
                        self.socket_pub.send_multipart(msgContainer)

            if self.socket_sub in socks and socks[self.socket_sub] == zmq.POLLIN:
                msgContainer = self.socket_sub.recv_multipart()
                self.log.debug("Agent received message: from controller using SUB")
                
                assert len(msgContainer)
                group = msgContainer[0]
                msgType = msgContainer[1]
                msg = msgContainer[2]
                delay = int(msgContainer[3])
                
                self.log.debug("Agent received message: {0}::{1} from controller using SUB".format(msgType, msg))

                if msgType == "NEW_NODE_ACK":
                    self.setup_connection_to_controller_complete(msgContainer)
                else:
                    self.log.debug("Agent serves command: {0}::{1} from controller".format(msgType, msg))
                    if delay == 0:
                        self.log.debug("Agent sends message: {0}::{1} to module".format(msgType, msg))
                        self.send_msg_to_module_group(msgContainer)
                    else:
                        self.log.debug("Agent schedule task for message: {0}::{1} in {2}s".format(msgType, msg, delay))
                        execTime = (datetime.datetime.now() + datetime.timedelta(seconds=delay))
                        self.jobScheduler.add_job(self.send_msg_to_module_group, 'date', run_date=execTime, kwargs={'msgContainer' : msgContainer})



    def run(self):
        self.log.debug("Agent starting".format())
        try:
            self.process_msgs()

        except KeyboardInterrupt:
            self.log.debug("Agent exits")

        finally:
            self.log.debug("Unexpected error:".format(sys.exc_info()[0]))
            self.log.debug("Kills all modules' subprocesses")
            for name, module in self.modules.iteritems():
                module.kill_module_subprocess()
            self.jobScheduler.shutdown()
            self.socket_sub.close()
            self.socket_pub.close()
            self.context.term()