import logging
import datetime
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

    def _execute_command(self, cmdDesc, upiFunc, device=None,
                         args=(), kwargs={}):

        returnValue = None
        exception = False
        try:
            returnValue = self.moduleManager.execute_function(
                upiFunc, device, args, kwargs)
        except Exception as e:
            self.log.debug("Exception: {}".format(e))
            exception = True
            returnValue = e

        dest = "controller"
        rvDesc = msgs.CmdDesc()
        rvDesc.type = cmdDesc.type
        rvDesc.func_name = cmdDesc.func_name
        rvDesc.call_id = cmdDesc.call_id
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
