import threading

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class Timer(object):
    def __init__(self, handler_):
        assert callable(handler_)
        super().__init__()
        self._handler = handler_
        self._event = threading.Event()
        self._thread = None

    def start(self, interval):
        """interval is in seconds"""
        if self._thread:
            self.cancel()
        self._event.clear()
        self._thread = threading.Thread(target=self._timer, args=[interval])
        self._thread.setDaemon(True)
        self._thread.start()

    def cancel(self):
        if not self._thread.is_alive():
            return
        self._event.set()
        # self._thread.join()
        self._thread = None

    def is_running(self):
        return self._thread is not None

    def _timer(self, interval):
        # Avoid cancellation during execution of self._callable()
        cancel = self._event.wait(interval)
        if cancel:
            return

        self._handler()


class TimerEventSender(Timer):
    # timeout handler is called by timer thread context.
    # So in order to actual execution context to application's event thread,
    # post the event to the application
    def __init__(self, app, ev_cls):
        super(TimerEventSender, self).__init__(self._timeout)
        self._app = app
        self._ev_cls = ev_cls

    def _timeout(self):
        self._app.send_event(self._ev_cls())
