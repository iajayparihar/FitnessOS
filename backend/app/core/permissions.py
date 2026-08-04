PERMISSION_READ = "read"
PERMISSION_WRITE = "write"


def require_permission(permission: str):
    def dependency():
        raise NotImplementedError

    return dependency
