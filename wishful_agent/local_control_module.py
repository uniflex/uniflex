import logging
import datetime
import wishful_framework as wishful_module
import wishful_framework as msgs
import wishful_upis as upis
from .local_controller import LocalController
import threading
import queue


__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz}@tkn.tu-berlin.de"


class LocalControlProgram(LocalController):
    def __init__(self, agent, ctrProgId, name, func):
        super(LocalControlProgram, self).__init__()
        self.log = logging.getLogger('LocalControlProgram_{}'.format(ctrProgId))
        self._stop = threading.Event()
        self.agent = agent
        self.id = ctrProgId
        self.controlProgram = func
        self.name = name
        self.recvQueue = queue.Queue()

    def start(self):
        self.controlProgramThread = threading.Thread(target=self.controlProgram, args=(self,), name="local_control_program")
        self.controlProgramThread.setDaemon(True)
        self.controlProgramThread.start()

    def stop(self):
        self._stop.set()

    def is_stopped(self):
        return self._stop.isSet()

    def _receive(self, msg):
        self.recvQueue.put(msg)

    def recv(self, block=True, timeout=None):
        try:
            self.log.debug("Waiting for msg in blocking call")
            msg = self.recvQueue.get(block=block, timeout=timeout)
            return msg
        except queue.Empty:
            return None

    def send_upstream(self, msg):
        dest = "controller"
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = "hierarchical_control"
        cmdDesc.func_name = "hierarchical_control"
        cmdDesc.call_id = str(0)
        cmdDesc.serialization_type = msgs.CmdDesc.PICKLE

        encapsulatedMsg = {"node_uuid": self.agent.uuid,
                           "control_program_id": self.id, "msg": msg}
        msgContainer = [dest, cmdDesc, encapsulatedMsg]
        self.agent.send_upstream(msgContainer)

    def exec_cmd(self, upi_type, fname, *args, **kwargs):
        self.log.debug("Controller executes cmd: {}.{} with args:{}, kwargs:{}"
                       .format(upi_type, fname, args, kwargs))

        # get function call context
        iface = self._iface
        exec_time = self._exec_time
        delay = self._delay
        timeout = self._timeout
        blocking = self._blocking
        callback = self._callback
        self._clear_call_context()

        # TODO: support timeout, on controller and agent sides?
        callId = str(self.generate_call_id())

        # build cmd desc message
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = upi_type
        cmdDesc.func_name = fname
        cmdDesc.call_id = callId

        if iface:
            cmdDesc.interface = iface

        if delay:
            exec_time = datetime.datetime.now() + datetime.timedelta(seconds=delay)
            blocking = False

        if exec_time:
            cmdDesc.exec_time = str(exec_time)
            blocking = False

        # call check
        if exec_time and exec_time < datetime.datetime.now():
            raise Exception("Scheduling function: {}:{} call in past".format(upi_type,fname))

        if not self.agent.is_upi_supported(iface=iface, upi_type=upi_type, fname=fname):
            raise Exception("UPI Function: {}:{} not supported for iface: {}, please install proper modules".format(upi_type,fname,iface))

        # set callback for this function call
        if callback:
            self.callbacks[callId] = callback
            blocking = False

        msgContainer = ["agent", cmdDesc, kwargs]

        # if blocking call, return response
        if blocking:
            # send command to execution engine
            response = self.agent.moduleManager.send_cmd_to_module_blocking(msgContainer)
            cmdDesc = response[1]
            retVal = response[2]
            return retVal

        # send command to execution engine (non-blocking)
        self.agent.process_cmd(msgContainer=msgContainer, localControllerId=self.id)

        return None


@wishful_module.build_module
class LocalControlModule(wishful_module.AgentModule):
    def __init__(self, agent):
        super(LocalControlModule, self).__init__()
        self.log = logging.getLogger('LocalControlModule')

        self.ctrProgramIdGen = 0
        self.controlPrograms = {}

    def generate_new_ctr_program_id(self):
        self.ctrProgramIdGen = self.ctrProgramIdGen + 1
        return self.ctrProgramIdGen

    @wishful_module.bind_function(upis.mgmt.start_local_control_program)
    def start_local_control_program(self, program_name, program_code):
        ctrProgramId = self.generate_new_ctr_program_id()
        self.log.debug("Starts new local control program,"
                       " name: {}, ID: {}".format(program_name, ctrProgramId))

        myGlobals = {}
        exec(program_code, myGlobals)
        programFunc = myGlobals[program_name]

        localControlProgram = LocalControlProgram(self.agent, ctrProgramId, program_name, programFunc)
        self.controlPrograms[ctrProgramId] = localControlProgram
        localControlProgram.start()
        return ctrProgramId


    @wishful_module.bind_function(upis.mgmt.stop_local_control_program)
    def stop_local_control_program(self, program_id):
        self.log.debug("Stop local control program, ID: {}".format(program_id))
        if program_id in self.controlPrograms:
            localControlProgram = self.controlPrograms[program_id]
            localControlProgram.stop()
            del self.controlPrograms[program_id]
            return "STOPPED"

        return "NOT_FOUND"


    @wishful_module.bind_function(upis.mgmt.send_msg_to_local_control_program)
    def send_msg_to_local_control_program(self, program_id, msg):
        if program_id in self.controlPrograms:
            localControlProgram = self.controlPrograms[program_id]
            localControlProgram._receive(msg)
            return "RECEIVED"
        return "NOT_FOUND"


    @wishful_module.on_exit()
    @wishful_module.on_disconnected()
    def kill_all_local_ctr_programs(self):
        self.log.debug("Kill all local control programs".format())
        for ctrProgId, ctrProg in list(self.controlPrograms.items()):
            ctrProg.stop()
        self.controlPrograms = {}
