
class RunFailureException(Exception):
    # should count as a final failure
    pass

class RunErrorException(Exception):
    # env failure, deserves a retry
    pass

class RunRefusedException(Exception):
    # api safety refusal, should count as a failure
    pass
