from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.runtime.tool_registry import registry

router = APIRouter(tags=["tools"])


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict


class ToolExecuteRequest(BaseModel):
    tool: str
    args: dict = {}


class ToolExecuteResponse(BaseModel):
    result: str
    tool: str


@router.get("/tools", response_model=list[ToolInfo])
async def list_tools():
    return [ToolInfo(**t) for t in registry.list_tools()]


@router.post("/tools/execute", response_model=ToolExecuteResponse)
async def execute_tool(body: ToolExecuteRequest):
    tool = registry.get(body.tool)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {body.tool}")
    try:
        result = await registry.execute(body.tool, **body.args)
        return ToolExecuteResponse(result=str(result), tool=body.tool)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
