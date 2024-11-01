
class ShaderBatchStop(Exception):
    """Whenever the batch processing should stop (ran out of inputs, manual stop, etc.)"""
    pass
