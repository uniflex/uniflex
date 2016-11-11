import time
import logging
from .modules import DeviceModule, ControlApplication
from .module_proxy import ModuleProxy, DeviceProxy, ApplicationProxy
import uniflex.msgs as msgs

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz}@tkn.tu-berlin.de"


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

    def _set_timer_callback(self, cb):
        self._timerCallback = cb

    def _hello_timer(self):
        while not self._stop and self._helloTimeout:
            time.sleep(1)
            self._helloTimeout = self._helloTimeout - 1
        # remove node
        self._timerCallback(self)

    def _refresh_hello_timer(self):
        self._helloTimeout = 9

    def __str__(self):
        string = ("\nNode Description:\n" +
                  " UUID:{}\n"
                  " Hostname:{}\n"
                  " IP:{}\n"
                  .format(self.uuid, self.hostname, self.ip))

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

            for func in module.functions:
                moduleProxy.functions.append(str(func.name))

            for event in module.in_events:
                moduleProxy.in_events.append(str(event.name))

            for event in module.out_events:
                moduleProxy.out_events.append(str(event.name))

        return node

    def add_module_proxy(self, module):
        moduleProxy = None
        if isinstance(module, DeviceModule) or module.device:
            moduleProxy = DeviceProxy()
            moduleProxy.deviceName = module.device
            self.devices[module.uuid] = moduleProxy
        elif isinstance(module, ControlApplication):
            moduleProxy = ApplicationProxy()
            self.apps[module.uuid] = moduleProxy
        else:
            moduleProxy = ModuleProxy()
            self.modules[module.uuid] = moduleProxy

        self.all_modules[module.uuid] = moduleProxy

        moduleProxy.node = self
        moduleProxy.uuid = module.uuid
        moduleProxy.name = module.name

        moduleProxy.functions = module.functions
        moduleProxy.in_events = module.in_events
        moduleProxy.out_events = module.out_events

        moduleProxy._currentNode = self

    def get_modules(self):
        """
        Get proxy objects for all modules installed
        in remote node.
        Returns list of Module Proxy objects
        """
        return self.modules.values()

    def get_module_by_uuid(self, uuid):
        """
        Get Module proxy object by its UUID.
        Returns ModuleProxy object.
        """
        return self.all_modules.get(uuid, None)

    def get_devices(self):
        """
        Get proxy objects for all device modules installed
        in remote node.
        Returns list of Device Module Proxy objects
        """
        return self.devices.values()

    def get_device_by_uuid(self, uuid):
        """
        Get Device Module proxy object by its UUID.
        Returns DeviceModuleProxy object.
        """
        pass

    def get_device(self, devId):
        return list(self.devices.values())[devId]

    def get_device_by_name(self, name):
        for dev in self.devices:
            if dev.name == name:
                return dev
        return None

    def get_protocols(self):
        """
        Get proxy objects for all protocol modules installed
        in remote node.
        Returns list of Protocol Module Proxy objects.
        """
        pass

    def get_protocol(self, uuid):
        """
        Get Protocol Module proxy object by its UUID.
        Returns ProtocolModuleProxy object.
        """
        pass

    def get_control_applications(self):
        """
         Get proxy objects for all control
        applications installed in remote node.
        Returns list of ControlApplicationProxy objects.
        """
        return self.apps.values()

    def get_control_application(self, uuid):
        """
        Get Control Application proxy object by its UUID.
        Returns ControlApplicationProxy object.
        """
        pass

    def send_event(self, event):
        """
        Send event to remote node in node-broadcast
        mode, i.e. event is delivered to node and broadcasted
        to all subscribed Control Applications.
        Returns True if succeeded; otherwise False
        """
        self.log.debug()

    def subscribe_for_events(self, eventType, callback):
        """
        Subscribe for events of given type generated in
        remote node. If event type is not given, subscribe
        for all events generated in remote node. The callback
        function will be called on reception of event.
        Returns True if succeeded; otherwise False
        """
        pass

    def unsubscribe_from_events(self, eventType):
        """
        Unsubscribe from events of given type generated
        in remote node. If event type is not given unsubscribe
        from all events generated in remote node.
        Returns True if succeeded; otherwise False
        """
        pass

    def get_time(self):
        """
        Get time of remote node.
        Returns UNIX time of remote node.
        """
        pass

    def is_synchronizing(self):
        """
        Check if remote node is synchronizing with some
        time server.
        Returns True is remote node runs time synchronization
        process; False otherwise
        """
        pass

    def get_time_synchronization_source(self):
        """
        Get time synchronization source of remote node.
        Note: we need to check if remote node synchronizes
        with the same source as application’s local
        node.
        Returns name of synchronization source
        """
        pass

    def get_time_synchronization_accuracy(self):
        """
        Get time synchronization accuracy.
        Returns time synchronization accuracy in milliseconds.
        """
        pass

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
