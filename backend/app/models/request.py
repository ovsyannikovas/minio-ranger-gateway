
from pydantic import BaseModel, Field


class Conditions(BaseModel):
    Authorization: list[str]
    CurrentTime: list[str]
    EpochTime: list[str]
    Referer: list[str]
    SecureTransport: list[str]
    SourceIp: list[str]
    User_Agent: list[str] = Field(..., alias="User-Agent")
    UserAgent: list[str]
    X_Amz_Content_Sha256: list[str] = Field(..., alias="X-Amz-Content-Sha256")
    X_Amz_Date: list[str] = Field(..., alias="X-Amz-Date")
    X_Amz_Security_Token: list[str] | None = Field(None, alias="X-Amz-Security-Token")
    X_Forwarded_For: list[str] | None = Field(None, alias="X-Forwarded-For")
    accesskey: list[str]
    authType: list[str]
    parent: list[str]
    principaltype: list[str]
    signatureversion: list[str]
    userid: list[str]
    username: list[str]
    versionid: list[str]

    class Config:
        populate_by_name = True


class Claims(BaseModel):
    accessKey: str
    parent: str
    exp: int | None = None


class InputData(BaseModel):
    account: str
    groups: str | None = None
    action: str
    originalAction: str
    bucket: str
    conditions: Conditions
    owner: bool
    object: str | None = None
    claims: Claims
    denyOnly: bool


class RequestBody(BaseModel):
    input: InputData
