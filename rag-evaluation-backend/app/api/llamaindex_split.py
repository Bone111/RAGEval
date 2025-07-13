from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.services.llm_service import llamaindex_split_files

router = APIRouter()

class FileContent(BaseModel):
    name: str
    content: str

class SplitRequest(BaseModel):
    files: List[FileContent]
    chunk_size: int = 2048
    chunk_overlap: int = 50
    include_metadata: bool = False

@router.post("/api/llamaindex_split")
async def llamaindex_split(req: SplitRequest):
    return llamaindex_split_files(
        [file.dict() for file in req.files],
        req.chunk_size,
        req.chunk_overlap,
        req.include_metadata
    ) 