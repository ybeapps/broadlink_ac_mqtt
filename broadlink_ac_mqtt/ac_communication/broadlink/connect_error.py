class ConnectError(Exception):
    """Base error class"""
    def __init__(self, code, host):
        self.code = code
        self.host = host
        super().__init__(f"Error Code: {code}, Host: {host}")
