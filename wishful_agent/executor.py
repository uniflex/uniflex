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
        # called before UPI function, call
        if hasattr(handler, '_before_call_'):
            before_func = getattr(handler, "_before_call_")
            before_func(module)

        returnValue = handler(*args, **kwargs)

        # if there is function that has to be
        # called after UPI function, call
        if hasattr(handler, '_after_call_'):
            after_func = getattr(handler, "_after_call_")
            after_func(module)

        return returnValue

    def _execute_thread(self, module, handler, args, kwargs):
        # if there is function that has to be
        # called before UPI function, call
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
        # called after UPI function, call
        if hasattr(handler, '_after_call_'):
            after_func = getattr(handler, "_after_call_")
            after_func(module)

    def _serve_ctx_command_event(self, event, local):
        ctx = event.ctx
        handlers = []
        runInThread = False
        retValue = None

        if ctx._upi_type == "function":
            handlers = self.moduleManager.get_function_handlers(ctx._upi)
        elif ctx._upi_type == "event_enable":
            handlers = self.moduleManager.get_event_enable_handlers(ctx._upi)
            runInThread = True
        elif ctx._upi_type == "event_disable":
            handlers = self.moduleManager.get_event_disable_handlers(ctx._upi)
        elif ctx._upi_type == "service_start":
            handlers = self.moduleManager.get_service_start_handlers(ctx._upi)
            runInThread = True
        elif ctx._upi_type == "service_stop":
            handlers = self.moduleManager.get_service_stop_handlers(ctx._upi)
        else:
            self.log.debug("UPI Type not supported")

        self.log.debug("UPI: {} {} THREAD:{}".format(ctx._upi, ctx._upi_type,
                                                     runInThread))

        args = ()
        kwargs = {}
        if ctx._kwargs:
            args = ctx._kwargs["args"]
            kwargs = ctx._kwargs["kwargs"]

        for handler in handlers:
            try:
                module = handler.__self__
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
                            #print("SRC NODE", module.uuid, event.srcNode, moduleProxy)
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
                    self.log.debug("UPI: {} in module: {}"
                                   " handler: {} was not executed"
                                   .format(ctx._upi, module.__class__.__name__,
                                           handler.__name__))
                    # go to check next module
                    continue

            except Exception as e:
                self.log.debug('Exception occurred during handler '
                               'processing. Backtrace from offending '
                               'handler [%s] servicing UPI function '
                               '[%s] follows [%s]',
                               handler.__name__, ctx._upi, e)
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
            self.log.debug("Serves Cmd Event: Type: {} UPI: {}".format(
                           ctx._upi_type, ctx._upi))
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
                           .format(ctx._upi_type, ctx._upi, execTime))
            self.jobScheduler.add_job(self._serve_ctx_command_event,
                                      'date', run_date=execTime,
                                      kwargs={"event": event,
                                              "local": local})
