__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class FunctionBase(object):
    # Nothing yet
    pass

class ParameterBase(object):
    """ base class for all data object parameters """
    # Nothing yet
    pass


class EventBase(object):
    """ event cannot be parametrized, user may only start it once"""

    def __init__(self):
        super().__init__()
        self.srcNode = None
        self.srcModule = None
        self.node = None
        self.device = None


class AgentStartEvent(EventBase):
    def __init__(self):
        super().__init__()


class AgentExitEvent(EventBase):
    def __init__(self):
        super().__init__()


class BrokerDiscoveredEvent(EventBase):
    def __init__(self, dlink, ulink):
        super().__init__()
        self.dlink = dlink
        self.ulink = ulink


class ConnectionEstablishedEvent(EventBase):
    def __init__(self):
        super().__init__()


class ConnectionLostEvent(EventBase):
    def __init__(self):
        super().__init__()


class NewNodeEvent(EventBase):
    def __init__(self):
        super().__init__()


class NodeExitEvent(EventBase):
    def __init__(self, reason):
        super().__init__()
        self.reason = reason


class NodeLostEvent(EventBase):
    def __init__(self, reason):
        super().__init__()
        self.reason = reason


class HelloTimeoutEvent(EventBase):
    def __init__(self):
        super().__init__()


class HelloMsgEvent(EventBase):
    def __init__(self):
        super().__init__()


class ExceptionEvent(EventBase):
    def __init__(self, dest, cmdDesc, msg):
        super().__init__()
        self.dest = dest
        self.cmdDesc = cmdDesc
        self.msg = msg


class CommandEvent(EventBase):
    def __init__(self, ctx):
        super().__init__()
        self.dstNode = None
        self.dstModule = None
        self.ctx = ctx
        self.responseQueue = None


class ReturnValueEvent(EventBase):
    def __init__(self, ctx, msg):
        super().__init__()
        self.dstNode = None
        self.dstModule = None
        self.ctx = ctx
        self.msg = msg

    def to_string(self):
        return str(self.dstNode) + ', ' + str(self.ctx) + ', ' + str(self.msg)


class TimeEvent(EventBase):
    """docstring for TimeEvent"""

    def __init__(self):
        super().__init__()
