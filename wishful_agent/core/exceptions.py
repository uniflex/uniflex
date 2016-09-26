'''
Base class for all exceptions.
'''


class WishfulException(Exception):
    message = 'An unknown exception'

    def __init__(self, msg=None, **kwargs):
        self.kwargs = kwargs
        if msg is None:
            msg = self.message

        try:
            msg = msg % kwargs
        except Exception:
            msg = self.message

        super(WishfulException, self).__init__(msg)


class AgentNotAvailable(WishfulException):
    message = 'agent %(id)s not available'


class InvalidArgumentException(WishfulException):
    message = 'function %(func_name)s called with wrong arguments'


class UnsupportedUPIFunctionException(WishfulException):
    message = ("function %(func_name)s is not supported" +
               "by connector_module %(conn_module)s")


class SchedulingFunctionCallsInThePastException(WishfulException):
    message = 'function %(func_name)s was scheduled in the past for execution'


class UPIFunctionExecutionFailedException(WishfulException):
    message = ("function %(func_name)s was not correctly executed;" +
               " error msg: %(err_msg)s")


UPIFunctionExecutionFailed = UPIFunctionExecutionFailedException
