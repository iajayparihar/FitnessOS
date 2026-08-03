def encode_jwt(payload: dict) -> str:
    raise NotImplementedError


def decode_jwt(token: str) -> dict:
    raise NotImplementedError
