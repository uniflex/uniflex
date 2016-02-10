import inspect

def get_msg_type(msg):
    if inspect.isclass(msg):
        return msg.__name__
    else:
        return msg.__class__.__name__
