import time
import logging
from .common import ModuleProxy
from .modules import DeviceModule, ControllerModule, Application
import uniflex.msgs as msgs

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz}@tkn.tu-berlin.de"


class DeviceProxy(ModuleProxy):
    def __str__(self):
        string = super().__str__()
        desc = ("    Device: {} \n"
                .format(self.name))
        string = string + desc
        return string


class ProtocolProxy(ModuleProxy):
    """docstring for ProtocolProxy"""
    pass


class ApplicationProxy(ModuleProxy):
    """docstring for ApplicationProxy"""
    pass


class Node(object):
    def __init__(self, uuid):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.uuid = uuid
        self.ip = None
        self.name = None
        self.hostname = None
        self.info = None
        self.nodeManager = None
        self.local = True  # Local or remote
        self.all_modules = {}
        self.apps = {}
        self.modules = {}
        self.devices = {}

    @staticmethod
    def create_node_from_msg(msg):
        node = Node(str(msg.agent_uuid))
        node.local = False
        node.ip = str(msg.ip)
        node.name = str(msg.name)
        node.hostname = str(msg.hostname)
        node.info = str(msg.info)

        node._stop = False
        node._helloTimeout = 9
        node._timerCallback = None

        for module in msg.modules:
            moduleProxy = None
            if module.type == msgs.Module.APPLICATION:
                moduleProxy = ApplicationProxy()
                node.apps[module.uuid] = moduleProxy
                moduleProxy.name = str(module.name)
            elif module.type == msgs.Module.DEVICE:
                moduleProxy = DeviceProxy()
                if module.HasField('device'):
                    moduleProxy.name = module.device.name
                node.devices[module.uuid] = moduleProxy
            else:
                moduleProxy = ModuleProxy()
                node.modules[module.uuid] = moduleProxy
                moduleProxy.name = str(module.name)

            node.all_modules[module.uuid] = moduleProxy
            moduleProxy.node = node
            moduleProxy.uuid = module.uuid
            moduleProxy.type = str(module.name)

            for attr in module.attributes:
                moduleProxy.attributes.append(str(attr.name))

            for func in module.functions:
                moduleProxy.functions.append(str(func.name))

            for event in module.in_events:
                moduleProxy.in_events.append(str(event.name))

            for event in module.out_events:
                moduleProxy.out_events.append(str(event.name))

            for service in module.services:
                moduleProxy.services.append(str(service.name))

        return node

    def __str__(self):
        string = ("\nNode Description:\n" +
                  " UUID:{}\n"
                  " Hostname:{}\n"
                  " Type:{}\n"
                  " IP:{}\n"
                  .format(self.uuid, self.hostname, self.type, self.ip))

        string = string + " Devices:\n"
        for uuid, device in self.devices.items():
            string = string + "  {}\n".format(device)

        string = string + " Modules:\n"
        for uuid, module in self.modules.items():
            moduleString = module.__str__()
            string = string + moduleString

        string = string + " Applications:\n"
        for uuid, app in self.apps.items():
            appString = app.__str__()
            string = string + appString

        return string

    def add_module_proxy(self, module):
        moduleProxy = None
        if isinstance(module, DeviceModule) or module.device:
            moduleProxy = DeviceProxy()
            moduleProxy.deviceName = module.device
            self.devices[module.uuid] = moduleProxy
        elif (isinstance(module, ControllerModule) or
              isinstance(module, Application)):
            moduleProxy = ApplicationProxy()
            self.apps[module.uuid] = moduleProxy
        else:
            moduleProxy = ModuleProxy()
            self.modules[module.uuid] = moduleProxy

        self.all_modules[module.uuid] = moduleProxy

        moduleProxy.node = self
        moduleProxy.uuid = module.uuid
        moduleProxy.name = module.name

        moduleProxy.attributes = module.attributes
        moduleProxy.functions = module.functions
        moduleProxy.in_events = module.in_events
        moduleProxy.out_events = module.out_events
        moduleProxy.services = module.services

        moduleProxy._currentNode = self

    def get_devices(self):
        return self.devices.values()

    def get_device(self, devId):
        return list(self.devices.values())[devId]

    def get_device_by_name(self, name):
        for dev in self.devices:
            if dev.name == name:
                return dev
        return None

    def get_modules(self):
        return self.modules.values()

    def get_module_by_uuid(self, uuid):
        return self.all_modules.get(uuid, None)

    def get_apps(self):
        return self.apps.values()

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

    def send_event(self, event):
        self.log.debug()

    def send_cmd_event(self, event):
        event.dstNode = self.uuid
        ctx = event.ctx
        self.log.debug("{}:{}".format(ctx._type, ctx._name))

        response = self.nodeManager.send_event_cmd(event, self)

        if ctx._blocking:
            self.log.debug("Waiting for return value for {}:{}"
                           .format(ctx._type, ctx._name))
            returnValue = event.responseQueue.get()
            if issubclass(returnValue.__class__, Exception):
                raise returnValue
            else:
                return returnValue

        return response
