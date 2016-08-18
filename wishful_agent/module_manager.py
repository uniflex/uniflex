import logging
import inspect
from .node import Node
from .node import Device
import wishful_upis as upis
from queue import Queue

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class ModuleManager(object):
    def __init__(self, agent):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self.moduleIdGen = 0
        self.node = Node(agent.uuid)
        self.node.moduleManager = self

        self.eventQueue = Queue()

        self.modules = {}
        self._event_handlers = {}
        self._function_handlers = {}
        self._event_enable_handlers = {}
        self._event_disable_handlers = {}
        self._service_start_handlers = {}
        self._service_stop_handlers = {}

    def my_import(self, module_name):
        pyModule = __import__(module_name)
        globals()[module_name] = pyModule
        return pyModule

    def generate_new_module_id(self):
        newId = self.moduleIdGen
        self.moduleIdGen = self.moduleIdGen + 1
        return newId

    def register_module(self, moduleName, pyModuleName,
                        className, device=None, kwargs={}):
        self.log.debug("Add new module: {}:{}:{}:{}".format(
            moduleName, pyModuleName, className, device))

        pyModule = self.my_import(pyModuleName)
        wishful_module_class = getattr(pyModule, className)
        wishfulModule = wishful_module_class(**kwargs)
        wishfulModule.set_device(device)

        wishfulModule = self.add_module_obj(moduleName, wishfulModule)
        if device:
            dev = Device(device, self.node)
            self.node.devices.append(dev)
        return wishfulModule

    def add_module_obj(self, moduleName, wishfulModule):
        self.log.debug("Add new module: {}:{}"
                       .format(moduleName, wishfulModule))

        moduleId = self.generate_new_module_id()
        wishfulModule.id = moduleId
        wishfulModule.set_module_manager(self)
        wishfulModule.set_agent(self.agent)
        self.register_event_handlers(wishfulModule)
        self.register_function_handlers(wishfulModule)

        self.register_event_enable_handlers(wishfulModule)
        self.register_event_disable_handlers(wishfulModule)

        self.modules[moduleId] = wishfulModule
        return wishfulModule

    # TODO: can be integrated with new event passing mechanism
    def start(self):
        self.log.debug("Notify START to modules".format())
        for module in list(self.modules.values()):
            module.start()

        # send new node event to interested control programs
        self.send_event(upis.mgmt.NewNodeEvent())
        self.serve_event_queue()

    def exit(self):
        self.log.debug("Notify EXIT to modules".format())
        for module in list(self.modules.values()):
            module.exit()

        # send node exit event to all interested control programs
        self.send_event(upis.mgmt.NodeExitEvent(0))

    def connected(self):
        self.log.debug("Notify CONNECTED to modules".format())
        for module in list(self.modules.values()):
            module.connected()

    def disconnected(self):
        self.log.debug("Notify DISCONNECTED to modules".format())
        for module in list(self.modules.values()):
            module.disconnected()

    def register_event_handlers(self, i):
        for _k, handler in inspect.getmembers(i, inspect.ismethod):
            if hasattr(handler, 'callers'):
                for ev_cls, c in handler.callers.items():
                    self._event_handlers.setdefault(ev_cls, [])
                    self._event_handlers[ev_cls].append(handler)
                    i.events.append(handler.__name__)

    def get_event_handlers(self, ev, state=None):
        ev_cls = ev.__class__
        handlers = self._event_handlers.get(ev_cls, [])
        return handlers

    def send_event(self, event):
        # stamp event with node if not present
        # if event from transport channel, then node is present
        if not event.node:
            event.node = self.node
        self.eventQueue.put(event)

    def serve_event_queue(self):
        while True:
            event = self.eventQueue.get()
            handlers = self.get_event_handlers(event)
            for handler in handlers:
                try:
                    handler(event)
                except:
                    self.log.exception('Exception occurred during handler '
                                       'processing. Backtrace from offending '
                                       'handler [%s] servicing event [%s] follows',
                                       handler.__name__, event.__class__.__name__)

    def register_function_handlers(self, i):
        for _k, handler in inspect.getmembers(i, inspect.ismethod):
            if hasattr(handler, '_upiFunc_'):
                if handler._upiFunc_:
                    self._function_handlers.setdefault(handler._upiFunc_, [])
                    self._function_handlers[handler._upiFunc_].append(handler)
                    i.functions.append(handler.__name__)

    def get_function_handlers(self, upiFunc, state=None):
        handlers = self._function_handlers.get(upiFunc, [])
        return handlers

    def send_cmd(self, ctx):
        self.log.info("{}:{}".format(ctx._upi_type, ctx._upi))
        event = upis.mgmt.CtxCommandEvent(ctx=ctx)
        self.send_event(event)

    def register_event_enable_handlers(self, i):
        for _k, handler in inspect.getmembers(i, inspect.ismethod):
            if hasattr(handler, '_event_enable_'):
                if handler._event_enable_:
                    self._event_enable_handlers.setdefault(
                        handler._event_enable_, [])
                    self._event_enable_handlers[handler._event_enable_].append(
                        handler)
                    # i.events.append(handler.__name__)

    def get_event_enable_handlers(self, event, state=None):
        handlers = self._event_enable_handlers.get(event, [])
        return handlers

    def register_event_disable_handlers(self, i):
        for _k, handler in inspect.getmembers(i, inspect.ismethod):
            if hasattr(handler, '_event_disable_'):
                if handler._event_disable_:
                    self._event_disable_handlers.setdefault(
                        handler._event_disable_, [])
                    self._event_disable_handlers[handler._event_disable_].append(
                        handler)
                    # i.events.append(handler.__name__)

    def get_event_disable_handlers(self, event, state=None):
        handlers = self._event_disable_handlers.get(event, [])
        return handlers

    def get_service_start_handlers(self, service, state=None):
        handlers = []
        return handlers

    def get_service_stop_handlers(self, service, state=None):
        handlers = []
        return handlers
