from typing import Optional, List

from pydantic import BaseModel, Field


class Conditions(BaseModel):
    Authorization: List[str]
    CurrentTime: List[str]
    EpochTime: List[str]
    Referer: List[str]
    SecureTransport: List[str]
    SourceIp: List[str]
    User_Agent: List[str] = Field(..., alias="User-Agent")
    UserAgent: List[str]
    X_Amz_Content_Sha256: List[str] = Field(..., alias="X-Amz-Content-Sha256")
    X_Amz_Date: List[str] = Field(..., alias="X-Amz-Date")
    X_Amz_Security_Token: Optional[List[str]] = Field(None, alias="X-Amz-Security-Token")
    X_Forwarded_For: Optional[List[str]] = Field(None, alias="X-Forwarded-For")
    accesskey: List[str]
    authType: List[str]
    parent: List[str]
    principaltype: List[str]
    signatureversion: List[str]
    userid: List[str]
    username: List[str]
    versionid: List[str]

    class Config:
        populate_by_name = True


class Claims(BaseModel):
    accessKey: str
    parent: str
    exp: Optional[int] = None


class InputData(BaseModel):
    account: str
    groups: Optional[str] = None
    action: str
    originalAction: str
    bucket: str
    conditions: Conditions
    owner: bool
    object: str
    claims: Claims
    denyOnly: bool


class RequestBody(BaseModel):
    input: InputData