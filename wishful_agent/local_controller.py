import uuid
import logging
import threading
import datetime

from wishful_framework import upis_builder
from wishful_framework import rule_manager
from wishful_framework import generator_manager
import wishful_framework as wishful_module
import wishful_framework as msgs
import wishful_upis as upis


__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz}@tkn.tu-berlin.de"


@wishful_module.build_module
class LocalController(wishful_module.AgentModule):
    def __init__(self):
        super(LocalController, self).__init__()
        self.log = logging.getLogger('localcontroller')

        self.agent = None
        self.uuid = str(uuid.uuid4())
        self.id = None

        self.default_callback = None
        self.callbacks = {}
        self.call_id_gen = 0

        # UPIs
        builder = upis_builder.UpiBuilder(self)
        self.radio = builder.create_upi(upis.radio.Radio, "radio")
        self.net = builder.create_upi(upis.net.Network, "net")
        self.mgmt = builder.create_upi(upis.mgmt.Mgmt, "mgmt")

        # Rule manager
        self.rule = rule_manager.LocalRuleManager(self)

        # Generator manager
        self.generator = generator_manager.LocalGeneratorManager(self)

        # function call context
        self._iface = None
        self._exec_time = None
        self._delay = None
        self._timeout = None
        self._blocking = True
        self._callback = None
        # container for blocking calls
        self._asyncResults = {}

    def fire_callback(self, callback, *args, **kwargs):
        self._clear_call_context()
        callback(*args, **kwargs)

    def add_callback(self, function, **options):
        def decorator(callback):
            self.log.debug("Register callback for: ", function.__name__)
            self.callbacks[function.__name__] = callback
            return callback
        return decorator

    def set_default_callback(self, **options):
        def decorator(callback):
            self.log.debug("Setting default callback")
            self.default_callback = callback
            return callback
        return decorator

    def iface(self, iface):
        self._iface = iface
        return self

    def exec_time(self, exec_time):
        self._exec_time = exec_time
        return self

    def delay(self, delay):
        self._delay = delay
        return self

    def timeout(self, value):
        self._timeout = value
        return self

    def blocking(self, value=True):
        self._blocking = value
        return self

    def callback(self, callback):
        self._callback = callback
        return self

    def _clear_call_context(self):
        self._iface = None
        self._exec_time = None
        self._delay = None
        self._timeout = None
        self._blocking = True
        self._callback = None

    def generate_call_id(self):
        self.call_id_gen = self.call_id_gen + 1
        return self.call_id_gen

    def exec_cmd(self, upi_type, fname, *args, **kwargs):
        self.log.debug("Controller executes cmd: {}.{} with args:{}, kwargs:{}"
                       .format(upi_type, fname, args, kwargs))

        # get function call context
        # TODO: setting and getting function call
        # context is not thread-safe, improve it
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
            exec_time = (datetime.datetime.now() +
                         datetime.timedelta(seconds=delay))
            blocking = False

        if exec_time:
            cmdDesc.exec_time = str(exec_time)
            blocking = False

        # call check
        if exec_time and exec_time < datetime.datetime.now():
            raise Exception("Scheduling function: {}:{} call in past"
                            .format(upi_type, fname))

        if not self.agent.is_upi_supported(iface=iface,
                                           upi_type=upi_type, fname=fname):
            raise Exception("UPI Function: {}:{} not supported for iface: {}."
                            "Please install proper modules"
                            .format(upi_type, fname, iface))

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
        self.agent.process_cmd(msgContainer)

        return None

    def recv_cmd_response(self, msgContainer):
        cmdDesc = msgContainer[1]
        msg = msgContainer[2]

        self.log.debug("Controller received message: {}:{} from agent"
                       .format(cmdDesc.type, cmdDesc.func_name))

        if cmdDesc.type == "wishful_rule":
            self.rule._receive(msg)
            return

        if cmdDesc.type == "wishful_generator":
            self.generator._receive(msg)
            return

        callId = cmdDesc.call_id
        if cmdDesc.call_id in self.callbacks:
            callback = self.callbacks[cmdDesc.call_id]
            t = threading.Thread(target=self.fire_callback, args=(callback, msg), name="callback")
            t.daemon = True
            t.start()
            # TODO: is it safe to remove it now?
            del self.callbacks[cmdDesc.call_id]

        elif cmdDesc.func_name in self.callbacks:
            callback = self.callbacks[cmdDesc.func_name]
            t = threading.Thread(target=self.fire_callback, args=(callback, msg), name="callback")
            t.daemon = True
            t.start()

        elif self.default_callback:
            t = threading.Thread(target=self.fire_callback, args=(self.default_callback, cmdDesc.func_name, msg), name="callback")
            t.daemon = True
            t.start()

        else:
            self.log.debug("Response to: {}:{} not served".format(cmdDesc.type, cmdDesc.func_name))
