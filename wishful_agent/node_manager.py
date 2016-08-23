import logging
import time
import uuid
import threading

import wishful_framework as msgs
import wishful_framework as wishful_module
import wishful_upis as upis
from .common import ControllableUnit
from .interface import Device

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class Group(object):
    def __init__(self, name):
        self.name = name
        self.uuid = str(uuid.uuid4())
        self.nodes = []

    def add_node(self, node):
        self.nodes.append(node)

    def remove_node(self, node):
        self.nodes.remove(node)


class ModuleDescriptor(object):
    """docstring for ModuleDescriptor"""

    def __init__(self):
        super(ModuleDescriptor, self).__init__()
        self.id = None
        self.name = None
        self.device = None
        self.attributes = []
        self.functions = []
        self.events = []
        self.services = []

    def __str__(self):
        string = ("  Module: {}\n"
                  "    ID: {} \n"
                  .format(self.name, self.id))

        if self.device:
            desc = ("    Device: {}:{} \n"
                    .format(self.device._id, self.device._name))
            string = string + desc

        string = string + "    Attributes:\n"
        for k in self.attributes:
            string = string + "      {}\n".format(k)
        string = string + "    Functions:\n"
        for k in self.functions:
            string = string + "      {}\n".format(k)
        string = string + "    Events:\n"
        for k in self.events:
            string = string + "      {}\n".format(k)
        string = string + "    Services:\n"
        for k in self.services:
            string = string + "      {}\n".format(k)
        return string


class Node(ControllableUnit):
    def __init__(self, msg):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.id = str(msg.agent_uuid)
        self.ip = str(msg.ip)
        self.name = str(msg.name)
        self.info = str(msg.info)
        self.devices = {}
        self.modules = {}

        self._stop = False
        self._helloTimeout = 9
        self._timerCallback = None

        for module in msg.modules:
            moduleDesc = ModuleDescriptor()
            moduleDesc.id = module.id
            moduleDesc.name = str(module.name)

            if module.HasField('device'):
                deviceDesc = Device(module.device.id, module.device.name, self)
                moduleDesc.device = deviceDesc
                self.devices[deviceDesc._id] = deviceDesc._name

            for attr in module.attributes:
                moduleDesc.attributes.append(str(attr.name))

            for func in module.functions:
                moduleDesc.functions.append(str(func.name))

            for event in module.events:
                moduleDesc.events.append(str(event.name))

            for service in module.services:
                moduleDesc.services.append(str(service.name))

            self.modules[moduleDesc.name] = moduleDesc

    def __str__(self):
        string = ("Node Description:\n" +
                  " ID:{}\n"
                  " Name:{}\n"
                  " IP:{}\n"
                  .format(self.id, self.name, self.ip))

        string = string + " Devices:\n"
        for devId, device in self.devices.items():
            string = string + "  {}:{}\n".format(devId, device)

        string = string + " Modules:\n"
        for name, module in self.modules.items():
            moduleString = module.__str__()
            string = string + moduleString

        return string

    def get_device(self, devId):
        return self.devices[devId]

    def set_timer_callback(self, cb):
        self._timerCallback = cb

    def hello_timer(self):
        while not self._stop and self._helloTimeout:
            print("runnig")
            time.sleep(1)
            self._helloTimeout = self._helloTimeout - 1
        # remove node
        print("remove node")
        self._timerCallback(self)

    def refresh_hello_timer(self):
        self._helloTimeout = 9

    def get_device_id(self, name):
        for k, v in self.device.items():
            if v == name:
                return k
        return None

    def send_msg(self, ctx):
        #ctx._scope = self
        #response = self._controller.send_msg(ctx)
        #self._clear_call_context()
        #return response
        pass

    def is_upi_supported(self, device, upiType, upiName):
        self.log.debug("Checking call: {}.{} for device {} in node {}"
                       .format(upiType, upiName, device, self.name))

        for module in self.modules.items():
            mdevice = module._deviceName
            if mdevice == device:
                if upiName in module._functions:
                    return True
            elif mdevice is None and device is None:
                if upiName in module._functions:
                    return True
            else:
                return False


class NodeManager(wishful_module.AgentModule):
    def __init__(self, agent):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self.nodes = []
        self.groups = []

        self.helloMsgInterval = 3
        self.helloTimeout = 3 * self.helloMsgInterval

    def get_node_by_id(self, nid):
        node = None
        for n in self.nodes:
            if n.id == nid:
                node = n
                break
        return node

    def get_node_by_ip(self, ip):
        node = None
        for n in self.nodes:
            if n.ip == ip:
                node = n
                break
        return node

    def get_node_by_str(self, string):
        if isinstance(string, Node):
            return string

        node = None
        node = self.get_node_by_ip(string)
        if node:
            return node

        node = self.get_node_by_id(string)
        return node

    @wishful_module.on_event(upis.mgmt.NewNodeDiscoveredEvent)
    def add_node(self, event):
        cmdDesc = event.cmdDesc
        msg = msgs.NewNodeMsg()
        msg.ParseFromString(event.msg)
        agentId = str(msg.agent_uuid)
        agentName = msg.name
        agentInfo = msg.info

        for n in self.nodes:
            if agentId == n.id:
                self.log.debug("Already known Node UUID: {},"
                               " Name: {}, Info: {}"
                               .format(agentId, agentName, agentInfo))
                return

        node = Node(msg)
        self.nodes.append(node)
        self.log.debug("New node with UUID: {}, Name: {},"
                       " Info: {}".format(agentId, agentName, agentInfo))
        self.send_event(upis.mgmt.SubscribeTopicEvent(agentId))

        # start hello timeout timer
        node.set_timer_callback(self.remove_node_hello_timer)
        d = threading.Thread(target=node.hello_timer)
        d.setDaemon(True)
        d.start()

        event = upis.mgmt.NewNodeEvent(node)

        dest = agentId
        cmdDesc.Clear()
        cmdDesc.type = msgs.get_msg_type(msgs.NewNodeAck)
        cmdDesc.func_name = msgs.get_msg_type(msgs.NewNodeAck)
        cmdDesc.serialization_type = msgs.CmdDesc.PROTOBUF

        msg = msgs.NewNodeAck()
        msg.status = True
        msg.controller_uuid = self.agent.uuid
        msg.agent_uuid = agentId
        msg.topics.append("ALL")

        msgContainer = [dest, cmdDesc, msg]

        time.sleep(1)  # wait until zmq agrees on topics
        event = upis.mgmt.SendMgsEvent(msgContainer)
        self.send_event(event)
        return node

    def remove_node_hello_timer(self, node):
        reason = "HelloTimeout"
        self.log.debug("Controller removes node with UUID: {},"
                       " Reason: {}".format(node.id, reason))

        if node and node in self.nodes:
            self.nodes.remove(node)

            event = upis.mgmt.NodeLostEvent(node, reason)
            self.send_event(event)

    @wishful_module.on_event(upis.mgmt.NodeExitEvent)
    def remove_node(self, msgContainer):
        topic = msgContainer[0]
        cmdDesc = msgContainer[1]
        msg = msgs.NodeExitMsg()
        msg.ParseFromString(msgContainer[2])
        agentId = str(msg.agent_uuid)
        reason = msg.reason

        node = self.get_node_by_id(agentId)

        if not node:
            return

        self.log.debug("Controller removes node with UUID: {},"
                       " Reason: {}".format(agentId, reason))

        if node and node in self.nodes:
            self.nodes.remove(node)

            event = upis.mgmt.NodeExitEvent(node, reason)
            self.send_event(event)

    def send_hello_msg_to_node(self, nodeId):
        self.log.debug("Controller sends HelloMsg to agent")
        dest = nodeId
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msgs.get_msg_type(msgs.HelloMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.HelloMsg)
        cmdDesc.serialization_type = msgs.CmdDesc.PROTOBUF

        msg = msgs.HelloMsg()
        msg.uuid = str(self.agent.uuid)
        msg.timeout = self.helloTimeout
        msgContainer = [dest, cmdDesc, msg]
        event = upis.mgmt.SendMgsEvent(msgContainer)
        self.send_event(event)

    @wishful_module.on_event(upis.mgmt.HelloMsgEvent)
    def serve_hello_msg(self, event):
        msgContainer = event
        self.log.debug("Controller received HELLO MESSAGE from agent".format())
        msg = msgs.HelloMsg()
        msg.ParseFromString(msgContainer[2])

        self.send_hello_msg_to_node(str(msg.uuid))

        node = self.get_node_by_id(str(msg.uuid))
        node.refresh_hello_timer()
