from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin


@dataclass
class CognitoPool(DataClassJSONMixin):
    app_client_id: str = field(metadata=field_options(alias="appClientId"))
    domain: str
    pool_id: str = field(metadata=field_options(alias="poolId"))
    region: str


@dataclass
class Credentials(DataClassJSONMixin):
    access_key_id: str = field(metadata=field_options(alias="AccessKeyId"))
    secret_key: str = field(metadata=field_options(alias="SecretKey"))
    session_token: str = field(metadata=field_options(alias="SessionToken"))
    expiration: datetime = field(metadata=field_options(alias="Expiration"))
    identity_id: str = field(metadata=field_options(alias="IdentityId"))


@dataclass
class UserPoolOAuth(DataClassJSONMixin):
    id_token: str = field(metadata=field_options(alias="IdToken"))
    access_token: str | None = field(
        default=None, metadata=field_options(alias="AccessToken")
    )
    expires_in: int | None = field(
        default=None, metadata=field_options(alias="ExpiresIn")
    )
    token_type: str | None = field(
        default=None, metadata=field_options(alias="TokenType")
    )
    refresh_token: str | None = field(
        default=None, metadata=field_options(alias="RefreshToken")
    )


@dataclass
class LoginResponse(DataClassJSONMixin):
    # Fields used by application code — required.
    id: int
    authentication_token: str
    session_id: str
    user_pool_o_auth: UserPoolOAuth = field(
        metadata=field_options(alias="userPoolOAuth")
    )
    # Remaining spec fields — optional so minimal test fixtures still parse.
    username: str = ""
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    address: str = ""
    address_1: str = ""
    address_2: str | None = None
    city: str = ""
    state: str | None = None
    country: str = ""
    postal_code: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    time_zone: str | None = None
    phone: str = ""
    opt_in_1: bool = False
    opt_in_2: bool = False
    role: str = ""
    cognito_pool: CognitoPool | None = field(
        default=None, metadata=field_options(alias="cognitoPool")
    )
    credentials: Credentials | None = None


@dataclass
class DevicesResponseElement(DataClassJSONMixin):
    # Fields used by application code — required.
    device_type: str
    serial_number: str
    # Remaining spec fields — optional so minimal test fixtures still parse.
    id: int = 0
    name: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    owner_id: int | None = None
    updating: bool = False
    firmware_version: str | None = None
    target_firmware_version: str | None = None
    update_firmware_start_at: str | None = None
    last_activity_at: datetime | None = None


DevicesResponse = List[DevicesResponseElement]
