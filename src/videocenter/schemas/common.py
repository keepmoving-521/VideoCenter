from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class ApiRequestModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


PositiveId = Annotated[int, Field(gt=0)]
NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
