from pydantic import BaseModel


class LastUpdateResponse(BaseModel):
    last_update: str | None
    status: str
    source_file_name: str | None = None
    source_file_last_modified: str | None = None
