import logging
import copy
import inspect
import threading
from importlib import import_module
from queue import Queue, Empty
from .node import Device
import wishful_upis as upis

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
        self.deviceIdGen = 0
        self.eventQueue = Queue()

        self.modules = {}
        self._event_handlers = {}
        self._function_handlers = {}
        self._event_enable_handlers = {}
        self._event_disable_handlers = {}
        self._service_start_handlers = {}
        self._service_stop_handlers = {}

    def my_import(self, module_name):
        pyModule = import_module(module_name)
        globals()[module_name] = pyModule
        return pyModule

    def generate_new_module_id(self):
        newId = self.moduleIdGen
        self.moduleIdGen = self.moduleIdGen + 1
        return newId

    def generate_new_device_id(self):
        newId = self.deviceIdGen
        self.deviceIdGen = self.deviceIdGen + 1
        return newId

    def register_module(self, moduleName, pyModuleName,
                        className, device=None, kwargs={}):
        self.log.debug("Add new module: {}:{}:{}:{}".format(
            moduleName, pyModuleName, className, device))

        pyModule = self.my_import(pyModuleName)
        wishful_module_class = getattr(pyModule, className)
        wishfulModule = wishful_module_class(**kwargs)

        wishfulModule = self.add_module_obj(moduleName, wishfulModule)
        node = self.agent.nodeManager.get_local_node()
        wishfulModule.localNode = node
        node.modules[wishfulModule.id] = wishfulModule
        if device:
            devId = self.generate_new_device_id()
            dev = Device()
            dev._id = devId
            dev.name = device
            dev.node = node
            wishfulModule.set_device(dev)
            node.devices[devId] = dev
        return wishfulModule

    def add_module_obj(self, moduleName, wishfulModule):
        self.log.debug("Add new module: {}:{}"
                       .format(moduleName, wishfulModule))

        moduleId = self.generate_new_module_id()
        wishfulModule.id = moduleId
        wishfulModule.set_module_manager(self)
        wishfulModule.set_agent(self.agent)

        self.subscribe_for_event(wishfulModule)

        self.register_event_handlers(wishfulModule)
        self.register_function_handlers(wishfulModule)

        self.register_event_enable_handlers(wishfulModule)
        self.register_event_disable_handlers(wishfulModule)

        self.register_service_start_handlers(wishfulModule)
        self.register_service_stop_handlers(wishfulModule)

        self.modules[moduleId] = wishfulModule
        return wishfulModule

    def start(self):
        self.log.debug("Notify START to modules".format())
        self.send_event(upis.mgmt.AgentStartEvent())
        # send new node event to interested control programs
        self.eventServeThread = threading.Thread(target=self.serve_event_queue)
        self.eventServeThread.setDaemon(True)
        self.eventServeThread.start()

    def exit(self):
        self.log.debug("Notify EXIT to modules".format())
        self.send_event(upis.mgmt.AgentExitEvent())
        # send node exit event to all interested control programs
        self.send_event(upis.mgmt.NodeExitEvent(0))

    def register_event_handlers(self, i):
        for _k, handler in inspect.getmembers(i, inspect.ismethod):
            if hasattr(handler, 'callers'):
                for ev_cls, c in handler.callers.items():
                    self._event_handlers.setdefault(ev_cls, [])
                    self._event_handlers[ev_cls].append(handler)
                    i.in_events.append(ev_cls.__name__)

    def subscribe_for_event(self, i):
        events = set()
        filterEvents = set(["AgentStartEvent", "AgentExitEvent",
                            "NewNodeEvent", "NodeExitEvent", "NodeLostEvent",
                            "BrokerDiscoveredEvent",
                            "ConnectionEstablishedEvent",
                            "ConnectionLostEvent",
                            "SendHelloMsgTimeEvent", "HelloMsgTimeoutEvent",
                            "ReturnValueEvent", "CommandEvent"])

        for _k, handler in inspect.getmembers(i, inspect.ismethod):
            if hasattr(handler, 'callers'):
                for ev_cls, c in handler.callers.items():
                    events.add(ev_cls.__name__)

        events = events - filterEvents
        events = list(events)
        if self.agent.transport:
            for e in events:
                self.agent.transport.subscribe_to(e)

    def get_event_handlers(self, ev, state=None):
        ev_cls = ev.__class__
        handlers = self._event_handlers.get(ev_cls, [])
        return handlers

    def send_event_locally(self, event):
        self.eventQueue.put(event)

    def send_event(self, event):
        self.eventQueue.put(event)
        # quick hack to sent events also through transport channel
        # TODO: improve it
        if self.agent.transport:
            # do not change original event that was sent to event queue
            eventCopy = copy.copy(event)
            self.agent.transport.send_event_outside(eventCopy)

    def serve_event_queue(self):
        while True:
            try:
                event = self.eventQueue.get(0.5)
            except Empty:
                continue
            handlers = self.get_event_handlers(event)
            self.log.debug("Serving event: {}"
                           .format(event.__class__.__name__))
            for handler in handlers:
                module = handler.__self__
                try:
                    if hasattr(handler, '_run_in_thread_'):
                        if handler._run_in_thread_:
                            t = None
                            if len(inspect.getargspec(handler)[0]) == 1:
                                t = threading.Thread(target=handler)
                            else:
                                t = threading.Thread(target=handler,
                                                     args=(event))
                            t.setDaemon(True)
                            t.start()

                    else:
                        self.log.debug("Add task: {} to worker"
                                       .format(handler.__name__))
                        if len(inspect.getargspec(handler)[0]) == 1:
                            module.worker.add_task(handler, None)
                        else:
                            module.worker.add_task(handler, event)
                except:
                    self.log.exception('Exception occurred during handler '
                                       'processing. Backtrace from offending '
                                       'handler [%s] servicing event [%s]'
                                       'follows',
                                       handler.__name__,
                                       event.__class__.__name__)

    def register_function_handlers(self, i):
        for _k, handler in inspect.getmembers(i, inspect.ismethod):
            if hasattr(handler, '_upiFunc_'):
                if handler._upiFunc_:
                    self._function_handlers.setdefault(handler._upiFunc_, [])
                    self._function_handlers[handler._upiFunc_].append(handler)
                    i.functions.append(handler._upiFunc_)

    def get_function_handlers(self, upiFunc, state=None):
        handlers = self._function_handlers.get(upiFunc, [])
        return handlers

    def register_event_enable_handlers(self, i):
        for _k, handler in inspect.getmembers(i, inspect.ismethod):
            if hasattr(handler, '_event_enable_'):
                if handler._event_enable_:
                    self._event_enable_handlers.setdefault(
                        handler._event_enable_, [])
                    self._event_enable_handlers[handler._event_enable_].append(
                        handler)
                    i.out_events.append(handler._event_enable_)

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

    def get_event_disable_handlers(self, event, state=None):
        handlers = self._event_disable_handlers.get(event, [])
        return handlers

    def register_service_start_handlers(self, i):
        for _k, handler in inspect.getmembers(i, inspect.ismethod):
            if hasattr(handler, '_service_start_'):
                if handler._service_start_:
                    self._service_start_handlers.setdefault(
                        handler._service_start_, [])
                    self._service_start_handlers[handler._service_start_].append(
                        handler)
                    i.services.append(handler._service_start_)

    def get_service_start_handlers(self, service, state=None):
        handlers = self._service_start_handlers.get(service, [])
        return handlers

    def register_service_stop_handlers(self, i):
        for _k, handler in inspect.getmembers(i, inspect.ismethod):
            if hasattr(handler, '_service_stop_'):
                if handler._service_stop_:
                    self._service_stop_handlers.setdefault(
                        handler._service_stop_, [])
                    self._service_stop_handlers[handler._service_stop_].append(
                        handler)

    def get_service_stop_handlers(self, service, state=None):
        handlers = self._service_stop_handlers.get(service, [])
        return handlers
