import logging
import datetime
import threading
from apscheduler.schedulers.background import BackgroundScheduler

from .core import events

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class CommandExecutor(object):
    def __init__(self, agent, moduleManager):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self.moduleManager = moduleManager
        apscheduler_logger = logging.getLogger('apscheduler')
        apscheduler_logger.setLevel(logging.CRITICAL)
        self.jobScheduler = BackgroundScheduler()
        self.jobScheduler.start()

    def stop(self):
        self.jobScheduler.shutdown()

    def _execute_command(self, module, handler, args, kwargs):
        self.log.debug("Execute function: {} module: {} handler: {}"
                       .format(handler.__name__, module.__class__.__name__,
                               handler.__name__))
        returnValue = None
        # if there is function that has to be
        # called before function, call
        if hasattr(handler, '_before_call_'):
            before_func = getattr(handler, "_before_call_")
            before_func(module)

        returnValue = handler(*args, **kwargs)

        # if there is function that has to be
        # called after function, call
        if hasattr(handler, '_after_call_'):
            after_func = getattr(handler, "_after_call_")
            after_func(module)

        return returnValue

    def _execute_thread(self, module, handler, args, kwargs):
        # if there is function that has to be
        # called before function, call
        self.log.debug("Thread: {} {}".format(module.__class__.__name__,
                                              handler.__name__))

        if hasattr(handler, '_before_call_'):
            before_func = getattr(handler, "_before_call_")
            before_func(module)

        thread = threading.Thread(target=handler,
                                  args=args, kwargs=kwargs)
        thread.setDaemon(True)
        thread.start()

        # if there is function that has to be
        # called after function, call
        if hasattr(handler, '_after_call_'):
            after_func = getattr(handler, "_after_call_")
            after_func(module)

    def _serve_ctx_command_event(self, event, local):
        ctx = event.ctx
        retValue = None

        runInThread = False
        if ctx._type == "event_enable":
            runInThread = True
        elif ctx._type == "service_start":
            runInThread = True

        self.log.debug("Get module with UUID: {}".format(event.dstModule))
        module = self.moduleManager.get_module_by_uuid(event.dstModule)

        self.log.debug("Serving: {} {} THREAD:{}".format(ctx._type,
                                                         ctx._name,
                                                         runInThread))
        args = ()
        kwargs = {}
        if ctx._kwargs:
            args = ctx._kwargs["args"]
            kwargs = ctx._kwargs["kwargs"]

        try:
            handler = getattr(module, ctx._name)
            # filter based on module uuid
            if event.dstModule == module.uuid:
                if runInThread:
                    self._execute_thread(module, handler,
                                         args, kwargs)
                else:
                    retValue = self._execute_command(module, handler,
                                                     args, kwargs)
                    if local:
                        moduleProxy = event.srcNode.get_module_by_uuid(module.uuid)
                        retEvent = events.ReturnValueEvent(event.ctx, retValue)
                        retEvent.srcNode = event.srcNode
                        retEvent.srcModule = moduleProxy
                        retEvent.dstNode = event.srcNode
                        retEvent.dstModule = event.srcModule
                        # alias
                        retEvent.node = event.srcNode
                        retEvent.device = moduleProxy
                        if event.ctx._blocking:
                            event.responseQueue.put(retEvent.msg)
                        elif event.ctx._callback:
                            event.ctx._callback(retEvent)
                    else:
                        retEvent = events.ReturnValueEvent(event.ctx, retValue)
                        retEvent.srcNode = self.agent.nodeManager.get_local_node()
                        retEvent.srcModule = event.dstModule
                        self.log.debug("send response")
                        self.agent.transport.send_event_outside(retEvent,
                                                                event.srcNode)

            else:
                self.log.debug("Func: {} in module: {}"
                               "was not executed"
                               .format(ctx._name, module.__class__.__name__))

        except Exception as e:
            self.log.debug('Exception occurred during handler '
                           'processing. Backtrace from offending '
                           'handler servicing function '
                           '[%s] follows [%s]', ctx._name, e)

            if local:
                moduleProxy = event.srcNode.get_module_by_uuid(module.uuid)
                retEvent = events.ReturnValueEvent(event.ctx, retValue)
                retEvent.srcNode = event.srcNode
                retEvent.srcModule = moduleProxy
                retEvent.dstNode = event.srcNode
                retEvent.dstModule = event.srcModule
                # alias
                retEvent.node = event.srcNode
                retEvent.device = moduleProxy
                if event.ctx._blocking:
                    event.responseQueue.put(e)
                elif event.ctx._callback:
                    event.ctx._callback(e)
            else:
                retEvent = events.ReturnValueEvent(event.ctx, e)
                retEvent.srcNode = self.agent.nodeManager.get_local_node()
                retEvent.srcModule = event.dstModule
                self.log.debug("send response")
                self.agent.transport.send_event_outside(retEvent,
                                                        event.srcNode)

    def serve_ctx_command_event(self, event, local=False):
        ctx = event.ctx

        if not ctx._exec_time or ctx._exec_time == 0:
            # execute now
            self.log.debug("Serves Cmd Event: Type: {} Func: {}".format(
                           ctx._type, ctx._name))
            self._serve_ctx_command_event(event, local)
        else:
            # schedule in future
            if isinstance(ctx._exec_time, str):
                execTime = datetime.datetime.strptime(
                    ctx._exec_time, "%Y-%m-%d %H:%M:%S.%f")
            else:
                execTime = ctx._exec_time

            if execTime < datetime.datetime.now():
                # send exception event
                return

            self.log.debug("Schedule task for Cmd Event: {}:{} at {}"
                           .format(ctx._type, ctx._name, execTime))
            self.jobScheduler.add_job(self._serve_ctx_command_event,
                                      'date', run_date=execTime,
                                      kwargs={"event": event,
                                              "local": local})
