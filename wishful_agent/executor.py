import logging
import datetime
import threading
from apscheduler.schedulers.background import BackgroundScheduler

import wishful_framework as msgs
import wishful_framework as wishful_module
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

    def _serve_ctx_command_event(self, ctx):
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

        print("handlers")
        for handler in handlers:
            print(handler)
            try:
                module = handler.__self__
                mdevice = module.get_device()
                self.log.info("Execute function: {} in module: {}"
                              " handler: {}; mdev: {}, cdev: {}"
                              .format(ctx._upi, module.__class__.__name__,
                                      handler.__name__, mdevice, ctx._device))

                # filter based on device present:
                # if device is not required execute function
                execute = False
                if (mdevice is None and ctx._device is None):
                    self.log.info("Execute function: {} in module: {}"
                                  " without device; handler: {}"
                                  .format(ctx._upi, module.__class__.__name__,
                                          handler.__name__))
                    execute = True
                # if devices match execute function
                elif mdevice == ctx._device:
                    self.log.info("Execute function: {} in module: {}"
                                  " with device: {} ; handler: {}"
                                  .format(ctx._upi, module.__class__.__name__,
                                          ctx._device, handler.__name__))
                    execute = True

                if execute:
                    # if there is function that has to be
                    # called before UPI function, call
                    if hasattr(handler, '_before'):
                        before_func = getattr(handler, "_before")
                        before_func()

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
                    if hasattr(handler, '_after'):
                        after_func = getattr(handler, "_after")
                        after_func()

                    # create and send return value event

                else:
                    self.log.info("UPI: {} in module: {}"
                                  " handler: {} was not executed"
                                  .format(ctx._upi, module.__class__.__name__,
                                          handler.__name__))
                    # go to check next module
                    continue

            except:
                self.log.debug('Exception occurred during handler '
                               'processing. Backtrace from offending '
                               'handler [%s] servicing UPI function '
                               '[%s] follows',
                               handler.__name__, ctx._upi)
                raise

        self.log.info("UPI: {} was called {} times"
                      .format(ctx._upi, callNumber))
        # TODO: if callNum == 0 rise an exeption?

    @wishful_module.on_event(upis.mgmt.CtxCommandEvent)
    def serve_ctx_command_event(self, event):
        ctx = event.ctx

        if not ctx._exec_time or ctx._exec_time == 0:
            # execute now
            self.log.debug("Serves Cmd Event: Type: {} UPI: {}".format(
                           ctx._upi_type, ctx._upi))
            self._serve_ctx_command_event(ctx)
        else:
            # schedule in future
            execTime = datetime.datetime.strptime(
                ctx.exec_time, "%Y-%m-%d %H:%M:%S.%f")

            if execTime < datetime.datetime.now():
                # send exception event
                pass

            self.log.debug("Schedule task for Cmd Event: {}:{} at {}"
                           .format(ctx._upi_type, ctx._upi, execTime))
            self.jobScheduler.add_job(self._serve_ctx_command_event,
                                      'date', run_date=execTime,
                                      kwargs={"ctx": ctx})

















    def _execute_command(self, ctx, upiFunc, device=None,
                         args=(), kwargs={}):
        returnValue = None
        exception = False
        try:
            returnValue = self.execute_function(
                upiFunc, device, args, kwargs)
        except Exception as e:
            self.log.debug("Exception: {}".format(e))
            exception = True
            returnValue = e

        dest = "controller"
        rvDesc = msgs.CmdDesc()
        rvDesc.type = ctx._upi_type
        rvDesc.func_name = ctx._upi
        rvDesc.call_id = ctx._callId
        # TODO: define new protobuf message for return values;
        # currently using repeat_number in CmdDesc
        # 0-executed correctly, 1-exception
        if exception:
            rvDesc.repeat_number = 1
        else:
            rvDesc.repeat_number = 0
        # Serialize return value
        rvDesc.serialization_type = msgs.CmdDesc.PICKLE

        event = upis.mgmt.ReturnValueEvent(dest, rvDesc, msg=returnValue)
        self.send_event(event)

    def serve_scheduled_cmd(self, cmdDesc, upiFunc,
                            device=None, args=(), kwargs={}):
        self.log.debug("Executor executed scheduled cmd: {} in device {},"
                       " args: {}, kwargs: {}".format(
                           upiFunc, device, args, kwargs))
        self._execute_command(cmdDesc, upiFunc, device, args, kwargs)

    @wishful_module.on_event(upis.mgmt.CommandEvent)
    def serve_command_event(self, event):
        dest = event.dest
        cmdDesc = event.cmdDesc
        kwargs = event.msg

        device = None
        if cmdDesc.HasField('interface'):
            device = cmdDesc.interface

        my_args = ()
        my_kwargs = {}
        if kwargs:
            my_args = kwargs['args']
            my_kwargs = kwargs['kwargs']

        self.log.debug("Executor received command: {} exec time {}".format(
                       cmdDesc.func_name, cmdDesc.exec_time))
        if not cmdDesc.exec_time or cmdDesc.exec_time == 0:
            self.log.debug("Executor serves command: {} with kwargs {}".format(
                cmdDesc.func_name, kwargs))
            self._execute_command(cmdDesc, cmdDesc.func_name,
                                  device, my_args, my_kwargs)

        else:
            execTime = datetime.datetime.strptime(
                cmdDesc.exec_time, "%Y-%m-%d %H:%M:%S.%f")

            if execTime < datetime.datetime.now():
                e = Exception("Node: {} tried to schedule function:"
                              " call in past. You may consider time"
                              " synchronization".format(self.name))

                dest = "controller"
                respDesc = msgs.CmdDesc()
                respDesc.type = cmdDesc.type
                respDesc.func_name = cmdDesc.func_name
                respDesc.call_id = cmdDesc.call_id
                # TODO: define new protobuf message for return values;
                # currently using repeat_number in CmdDesc
                # 0-executed correctly, 1-exception
                respDesc.repeat_number = 1
                respDesc.serialization_type = msgs.CmdDesc.PICKLE
                event = upis.mgmt.ExceptionEvent(dest, respDesc, e)
                self.send_event(event)
                return

            self.log.debug("Executor schedules task for cmd: {}:{} at {}"
                           .format(cmdDesc.type, cmdDesc.func_name, execTime))
            self.jobScheduler.add_job(self.serve_scheduled_cmd,
                                      'date', run_date=execTime,
                                      kwargs={"cmdDesc": cmdDesc,
                                              "upiFunc": cmdDesc.func_name,
                                              "device": device,
                                              "args": my_args,
                                              "kwargs": my_kwargs})
