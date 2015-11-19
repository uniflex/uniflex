import logging
import time
import sys
import yaml
from agent_module import *
import zmq
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import uuid
import wishful_upis.msgs.management_pb2 as msgMgmt
from wishful_upis.msgs.msg_helper import get_msg_type

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
        self.agent_info = {}

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

        self.agent_info = config['agent_info']

        inproc_modules = config['inproc_modules']
        for module_name, module_parameters in inproc_modules.iteritems():
            self.add_inproc_module(
                module_parameters['message_type'],
                self.exec_inproc_module(
                        name=module_name,
                        py_module=module_parameters['import'],
                        class_name=module_parameters['class_name'],
                        args=module_parameters['args'],
                        msg_proc_func_name=module_parameters['function'],
                )
            )

        modules = config['modules']
        for module_name, module_parameters in modules.iteritems():
            self.add_module(
                module_parameters['message_type'],
                self.exec_module(
                        name=module_name,
                        path=module_parameters['path'],
                        args=module_parameters['args']
                )
            )
        pass

    def exec_inproc_module(self, name, py_module, class_name, args, msg_proc_func_name):
        new_module = AgentInProcModule(name, py_module, class_name, args, msg_proc_func_name)
        return new_module

    def exec_module(self, name, path, args):
        new_module = AgentModule(name, path, args)
        return new_module

    def add_inproc_module(self, message_types, module):
        self.log.debug("Adding new inproc module: {0}".format(module))
        self.modules[module.name] = module

        for message_type in message_types:
            if message_type in self.module_groups.keys():
                self.module_groups[message_type].append(module.name)
            else:
                self.module_groups[message_type] = [module.name]

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
        return self.modules[module_name].send_msg_to_module(msgContainer)

    def send_msg_to_module_group(self, msgContainer):
        msgDesc = msgMgmt.MsgDesc()
        msgDesc.ParseFromString(msgContainer[1])

        response = []
        module_name_list = self.module_groups[msgDesc.msg_type]
        for module_name in module_name_list:
            tmp = self.send_msg_to_module(module_name, msgContainer)
            if tmp:
                response.append(tmp)
        return response

    def setup_connection_to_controller(self, msgContainer):
        msgDesc= msgMgmt.MsgDesc()
        msgDesc.ParseFromString(msgContainer[1])
        msg = msgMgmt.ControllerDiscoveredMsg()
        msg.ParseFromString(msgContainer[2])

        self.log.debug("Agent connects controller: DL:{0}, UL:{1}".format(msg.down_link, msg.up_link))
        self.socket_pub.connect(msg.down_link)
        self.socket_sub.connect(msg.up_link)

        group = "NEW_NODE"
        msgDesc.Clear()
        msgDesc.msg_type = get_msg_type(msgMgmt.NewNodeMsg)
        msg = msgMgmt.NewNodeMsg()
        msg.agent_uuid =  self.myId
        msg.name = self.agent_info['name']
        msg.info = self.agent_info['info']

        msgContainer = [group, msgDesc.SerializeToString(), msg.SerializeToString()]

        self.log.debug("Agent sends context-setup request to controller")
        time.sleep(1) # TODO: are we waiting for connection?
        self.socket_pub.send_multipart(msgContainer)

    def setup_connection_to_controller_complete(self, msgContainer):
        msgDesc = msgMgmt.MsgDesc()
        msgDesc.ParseFromString(msgContainer[1])
        msg = msgMgmt.NewNodeAck()
        msg.ParseFromString(msgContainer[2])

        self.log.debug("Controller received msgType: {0} with status: {1}".format(msgDesc.msg_type, msg.status))

        self.log.debug("Agent connects to controller and subscribes to received topics")
        self.socket_sub.setsockopt(zmq.SUBSCRIBE,  self.myId)
        for topic in msg.topics:
            self.log.debug("Agent subscribes to topic: {0}".format(topic))
            self.socket_sub.setsockopt(zmq.SUBSCRIBE, str(topic))


    def process_msgs(self):
        # Work on requests from both controller and modules
        while True:
            socks = dict(self.poller.poll())

            for name, module in self.modules.iteritems():
                if module.socket in socks and socks[module.socket] == zmq.POLLIN:
                    msgContainer = module.socket.recv_multipart()

                    assert len(msgContainer) == 3
                    group = msgContainer[0]
                    msgDesc = msgMgmt.MsgDesc()
                    msgDesc.ParseFromString(msgContainer[1])
                    msg = msgContainer[2]

                    if not group:
                        self.log.debug("Field group not set -> set UUID".format())
                        msgContainer[0] = self.myId

                    self.log.debug("Agent received message of type: {0} from module: {1}".format(msgDesc.msg_type, name))

                    if msgDesc.msg_type == get_msg_type(msgMgmt.ControllerDiscoveredMsg):
                        self.log.debug("Agent {0} discovered controller".format(name))
                        self.setup_connection_to_controller(msgContainer)
                    else:
                        self.log.debug("Agent sends message to Controller: {0}".format(msgDesc.msg_type))
                        self.socket_pub.send_multipart(msgContainer)

            if self.socket_sub in socks and socks[self.socket_sub] == zmq.POLLIN:
                msgContainer = self.socket_sub.recv_multipart()

                assert len(msgContainer) == 3
                group = msgContainer[0]
                msgDesc = msgMgmt.MsgDesc()
                msgDesc.ParseFromString(msgContainer[1])
                msg = msgContainer[2]
                
                self.log.debug("Agent received message: {0} from controller".format(msgDesc.msg_type))

                if msgDesc.msg_type == get_msg_type(msgMgmt.NewNodeAck):
                    self.setup_connection_to_controller_complete(msgContainer)
                else:
                    self.log.debug("Agent serves command: {0}::{1} from controller".format(msgDesc.msg_type, msg))
                    if not msgDesc.exec_time or msgDesc.exec_time == 0:
                        self.log.debug("Agent sends message: {0}::{1} to module".format(msgDesc.msg_type, msg))
                        responses = self.send_msg_to_module_group(msgContainer)
                        if responses:
                            self.log.debug("InProcModule sends message to controller".format())
                            for msgContainer in responses:
                                self.socket_pub.send_multipart(msgContainer)

                    else:
                        execTime = datetime.datetime.strptime(msgDesc.exec_time, "%Y-%m-%d %H:%M:%S.%f")
                        self.log.debug("Agent schedule task for message: {0}::{1} at {2}".format(msgDesc.msg_type, msg, execTime))
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