from enum import Enum


class AuditResult(Enum):
    ALLOWED = 1
    DENIED = 0


class S3AccessType(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    LIST = "list"
    ADMIN = "admin"


class S3ResourceType(Enum):
    BUCKET = 1
    OBJECT = 2


DEFAULT_POLICY_VERSION = 1
