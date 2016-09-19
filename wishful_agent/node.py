import copy
import time
import logging
from queue import Queue
from .common import ControllableUnit
import wishful_upis as upis

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz}@tkn.tu-berlin.de"


class Device(ControllableUnit):
    def __init__(self, devId, name, node):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self._id = devId
        self.name = name
        self.node = node

    def send_msg(self, ctx):
        self.log.debug("{}:{}".format(ctx._upi_type, ctx._upi))
        ctx._iface = self.name
        ctx._device = self.name
        response = self.node.send_msg(ctx)
        self._clear_call_context()
        return response


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
                    .format(self.device._id, self.device.name))
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
    def __init__(self, uuid):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.uuid = uuid
        self.ip = None
        self.name = None
        self.info = None
        self.nodeManager = None
        self.local = True  # Local or remote
        self.devices = {}
        self.modules = {}

    @staticmethod
    def create_node_from_msg(msg):
        node = Node(str(msg.agent_uuid))
        node.local = False
        node.ip = str(msg.ip)
        node.name = str(msg.name)
        node.info = str(msg.info)

        node._stop = False
        node._helloTimeout = 9
        node._timerCallback = None

        for module in msg.modules:
            moduleDesc = ModuleDescriptor()
            moduleDesc.id = module.id
            moduleDesc.name = str(module.name)

            if module.HasField('device'):
                deviceDesc = Device(module.device.id, module.device.name, node)
                moduleDesc.device = deviceDesc
                node.devices[deviceDesc._id] = deviceDesc

            for attr in module.attributes:
                moduleDesc.attributes.append(str(attr.name))

            for func in module.functions:
                moduleDesc.functions.append(str(func.name))

            for event in module.events:
                moduleDesc.events.append(str(event.name))

            for service in module.services:
                moduleDesc.services.append(str(service.name))

            node.modules[moduleDesc.name] = moduleDesc

        return node

    def __str__(self):
        string = ("\nNode Description:\n" +
                  " UUID:{}\n"
                  " Name:{}\n"
                  " IP:{}\n"
                  .format(self.uuid, self.name, self.ip))

        string = string + " Devices:\n"
        for devId, device in self.devices.items():
            string = string + "  {}:{}\n".format(devId, device)

        string = string + " Modules:\n"
        for name, module in self.modules.items():
            moduleString = module.__str__()
            string = string + moduleString

        return string

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

    def get_devices(self):
        return self.devices.values()

    def get_device(self, devId):
        return self.devices.get(devId, None)

    def get_device_by_name(self, name):
        for dev in self.devices:
            if dev.name == name:
                return dev
        return None

    def set_timer_callback(self, cb):
        self._timerCallback = cb

    def hello_timer(self):
        while not self._stop and self._helloTimeout:
            time.sleep(1)
            self._helloTimeout = self._helloTimeout - 1
        # remove node
        self._timerCallback(self)

    def refresh_hello_timer(self):
        self._helloTimeout = 9

    def send_msg(self, ctx):
        self.log.debug("{}:{}".format(ctx._upi_type, ctx._upi))
        if ctx._callback:
            app = ctx._callback.__self__
            app._register_callback(ctx)

        ctxCopy = copy.copy(ctx)
        self._clear_call_context()

        event = upis.mgmt.CtxCommandEvent(ctx=ctxCopy)
        if ctxCopy._blocking:
            event.responseQueue = Queue()

        response = self.nodeManager.send_event_cmd(event, self)

        if ctxCopy._blocking:
            self.log.debug("Waiting for return value for {}:{}"
                           .format(ctxCopy._upi_type, ctxCopy._upi))
            returnValue = event.responseQueue.get()
            if issubclass(returnValue.__class__, Exception):
                raise returnValue
            else:
                return returnValue

        return response


class NodeGroup(object):
    """docstring for NodeGroup"""

    def __init__(self):
        super(NodeGroup, self).__init__()
