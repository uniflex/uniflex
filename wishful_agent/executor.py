import logging
import datetime
import threading
from apscheduler.schedulers.background import BackgroundScheduler

from .core import wishful_module
import wishful_upis as upis

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


@wishful_module.build_module
class CommandExecutor(wishful_module.AgentModule):
    def __init__(self, agent):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        apscheduler_logger = logging.getLogger('apscheduler')
        apscheduler_logger.setLevel(logging.CRITICAL)
        self.jobScheduler = BackgroundScheduler()
        self.jobScheduler.start()

    def stop(self):
        self.jobScheduler.shutdown()

    def _serve_ctx_command_event(self, event):
        ctx = event.ctx
        handlers = []
        callNumber = 0
        returnValue = None
        runInThread = False

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

        args = ()
        kwargs = {}
        if ctx._kwargs:
            args = ctx._kwargs["args"]
            kwargs = ctx._kwargs["kwargs"]

        for handler in handlers:
            try:
                module = handler.__self__
                mdevice = module.get_device()
                self.log.debug("Execute function: {} in module: {}"
                               " handler: {}; mdev: {}, cdev: {}"
                               .format(ctx._upi, module.__class__.__name__,
                                       handler.__name__, mdevice, ctx._device))

                # filter based on device present:
                # if device is not required execute function
                execute = False
                if (mdevice is None and ctx._device is None):
                    self.log.debug("Execute function: {} in module: {}"
                                   " without device; handler: {}"
                                   .format(ctx._upi, module.__class__.__name__,
                                           handler.__name__))
                    execute = True
                # if devices match execute function
                elif mdevice == ctx._device:
                    self.log.debug("Execute function: {} in module: {}"
                                   " with device: {} ; handler: {}"
                                   .format(ctx._upi, module.__class__.__name__,
                                           ctx._device, handler.__name__))
                    execute = True

                if execute:
                    # if there is function that has to be
                    # called before UPI function, call
                    if hasattr(handler, '_before_call_'):
                        before_func = getattr(handler, "_before_call_")
                        before_func(module)

                    if runInThread:
                        thread = threading.Thread(target=handler,
                                                  args=args, kwargs=kwargs)
                        thread.setDaemon(True)
                        thread.start()
                        callNumber = callNumber + 1
                    else:
                        returnValue = handler(*args, **kwargs)
                        callNumber = callNumber + 1

                    # if there is function that has to be
                    # called after UPI function, call
                    if hasattr(handler, '_after_call_'):
                        after_func = getattr(handler, "_after_call_")
                        after_func(module)

                    # create and send return value event
                    if ctx._blocking:
                        self.log.debug("synchronous call")
                        event.responseQueue.put(returnValue)
                    else:
                        self.log.debug("asynchronous call device: {}"
                                       .format(module.device))
                        event = upis.mgmt.CtxReturnValueEvent(ctx, returnValue)
                        event.device = module.devObj
                        self.send_event(event)

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
                               '[%s] follows',
                               handler.__name__, ctx._upi)

                # create exception event and send it back to controller
                if ctx._blocking:
                    event.responseQueue.put(e)
                else:
                    pass

        self.log.debug("UPI: {} was called {} times"
                       .format(ctx._upi, callNumber))
        # TODO: if callNum == 0 rise an exeption?

    @wishful_module.on_event(upis.mgmt.CtxCommandEvent)
    def serve_ctx_command_event(self, event):
        ctx = event.ctx

        if not ctx._exec_time or ctx._exec_time == 0:
            # execute now
            self.log.debug("Serves Cmd Event: Type: {} UPI: {}".format(
                           ctx._upi_type, ctx._upi))
            self._serve_ctx_command_event(event)
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
                                      kwargs={"event": event})
