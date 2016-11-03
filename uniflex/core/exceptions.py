'''
Base class for all exceptions.
'''


class UniFlexException(Exception):
    message = 'An unknown exception'

    def __init__(self, msg=None, **kwargs):
        self.kwargs = kwargs
        if msg is None:
            msg = self.message

        try:
            msg = msg % kwargs
        except Exception:
            msg = self.message

        super(UniFlexException, self).__init__(msg)


class AgentNotAvailable(UniFlexException):
    message = 'agent %(id)s not available'


class InvalidArgumentException(UniFlexException):
    message = 'function %(func_name)s called with wrong arguments'


class UnsupportedFunctionException(UniFlexException):
    message = ("function %(func_name)s is not supported" +
               "by connector_module %(conn_module)s")


class SchedulingFunctionCallsInThePastException(UniFlexException):
    message = 'function %(func_name)s was scheduled in the past for execution'


class FunctionExecutionFailedException(UniFlexException):
    message = ("function %(func_name)s was not correctly executed;" +
               " error msg: %(err_msg)s")


FunctionExecutionFailed = FunctionExecutionFailedException
