import logging
import copy
import inspect
import threading
from importlib import import_module
from queue import Queue, Empty
from .cmd_executor import CommandExecutor
from . import events

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class ModuleManager(object):
    def __init__(self, agent):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self._transportChannel = None
        self._nodeManager = None

        self.commandExecutor = CommandExecutor(agent, self)
        self.synchronousCalls = {}
        self.callCallbacks = {}

        self.moduleIdGen = 0
        self.deviceIdGen = 0
        self.eventQueue = Queue()

        self.modules = {}
        self._event_handlers = {}

    def my_import(self, module_name):
        pyModule = import_module(module_name)
        globals()[module_name] = pyModule
        return pyModule

    def register_module(self, moduleName, pyModuleName,
                        className, device=None, kwargs={}):
        self.log.debug("Add new module: {}:{}:{}:{}".format(
            moduleName, pyModuleName, className, device))

        pyModule = self.my_import(pyModuleName)
        uniflex_module_class = getattr(pyModule, className)
        uniflexModule = uniflex_module_class(**kwargs)

        if device:
            uniflexModule.device = device

        uniflexModule = self.add_module_obj(moduleName, uniflexModule)

        localNode = self.agent.nodeManager.get_local_node()
        uniflexModule.localNode = localNode

        localNode.add_module_proxy(uniflexModule)

        return uniflexModule

    def add_module_obj(self, moduleName, uniflexModule):
        self.log.debug("Add new module: {}:{}"
                       .format(moduleName, uniflexModule))

        uniflexModule.set_module_manager(self)
        uniflexModule.set_agent(self.agent)

        self.subscribe_for_event(uniflexModule)
        self.register_event_handlers(uniflexModule)

        self.modules[uniflexModule.uuid] = uniflexModule
        return uniflexModule

    def get_module_by_uuid(self, uuid):
        for m in self.modules.values():
            if m.uuid == uuid:
                return m
        return None

    def start(self):
        self.log.debug("Notify START to modules".format())
        self.send_event_locally(events.AgentStartEvent())
        # send new node event to interested control programs
        self.eventServeThread = threading.Thread(target=self.serve_event_queue)
        self.eventServeThread.setDaemon(True)
        self.eventServeThread.start()

    def exit(self):
        self.log.debug("Notify EXIT to modules".format())
        event = events.AgentExitEvent()
        event.node = self.agent.nodeManager.get_local_node()
        self.send_event_locally(event)

        # send node exit event to all interested control programs
        event = events.NodeExitEvent(0)
        event.node = self.agent.nodeManager.get_local_node()
        self.send_event_outside(event)

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

    def send_event_outside(self, event, dstNode=None):
        if self.agent.transport:
            # do not change original event that was sent to event queue
            eventCopy = copy.copy(event)
            self.agent.transport.send_event_outside(eventCopy, dstNode)

    def send_event(self, event, dstNode=None):
        self.eventQueue.put(event)
        # quick hack to sent events also through transport channel
        # TODO: improve it
        if self.agent.transport:
            # do not change original event that was sent to event queue
            eventCopy = copy.copy(event)
            self.agent.transport.send_event_outside(eventCopy, dstNode)

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
                    self.log.debug("Add task: {} to worker in module {}"
                                   .format(handler.__name__, module.name))
                    if len(inspect.getargspec(handler)[0]) == 1:
                        module.worker.add_task(handler, None)
                    else:
                        module.worker.add_task(handler, event)
                except:
                    self.log.debug('Exception occurred during handler '
                                   'processing. Backtrace from offending '
                                   'handler [%s] servicing event [%s]'
                                   'follows',
                                   handler.__name__,
                                   event.__class__.__name__)

    def send_cmd_event(self, event, dstNode):
        if dstNode.local:
            if event.ctx._blocking:
                event.responseQueue = Queue()
            self.commandExecutor.serve_ctx_command_event(event, True)
        else:
            if event.ctx._blocking:
                # save reference to response queue
                self.synchronousCalls[event.ctx._callId] = Queue()
            elif event.ctx._callback:
                # save reference to callback
                module = event.ctx._callback.__self__
                self.callCallbacks[event.ctx._callId] = [module, event.ctx._callback]
                event.ctx._callback = None

            self._transportChannel.send_event_outside(event, dstNode)

            if event.ctx._blocking:
                event.responseQueue = self.synchronousCalls[event.ctx._callId]

    def serve_event_msg(self, event):
        srcNodeUuid = event.srcNode
        srcModuleUuid = event.srcModule

        # quick fix for receiving msg from node-red
        # TODO: improve it!!
        if "node-red" in srcNodeUuid:
            event.srcNode = srcNodeUuid
            event.node = srcNodeUuid
            event.srcModule = srcNodeUuid
            event.device = srcNodeUuid
            self.send_event_locally(event)
            return
        # fix ends here

        event.srcNode = self._nodeManager.get_node_by_uuid(event.srcNode)
        # alias
        event.node = event.srcNode

        if event.srcNode is None:
            self.log.debug("Unknown node: {}"
                           .format(srcNodeUuid))
            self._nodeManager.send_node_info_request(srcNodeUuid)
            return

        self.log.debug("received event from node: {}, module: {}"
                       .format(srcNodeUuid, srcModuleUuid))

        if event.srcModule is not None and isinstance(event.srcModule, str):
            event.srcModule = event.node.all_modules.get(event.srcModule, None)
            # alias
            event.device = event.srcModule

        if not event.srcModule:
            return

        self.log.debug("received event {} from node: {}, module: {}"
                       .format(event.__class__.__name__, event.srcNode.uuid,
                               event.srcModule.uuid))

        if isinstance(event, events.CommandEvent):
            self.commandExecutor.serve_ctx_command_event(event)

        elif isinstance(event, events.ReturnValueEvent):
            if event.ctx._callId in self.synchronousCalls:
                queue = self.synchronousCalls[event.ctx._callId]
                queue.put(event.msg)
            elif event.ctx._callId in self.callCallbacks:
                self.log.debug("received cmd: {}".format(event.ctx._name))
                [module, callback] = self.callCallbacks[event.ctx._callId]
                module.worker.add_task(callback, event)

        else:
            self.send_event_locally(event)
