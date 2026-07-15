import os
import shutil
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

# Add workspace directory to python path
sys.path.append(str(Path(__file__).resolve().parent))

from src.config import settings
from src.utils.logger import logger
from src.workflow.graph import app as workflow_app
from src.models.state import AgentState

app = FastAPI(
    title="AI Agent MVP Tracker - Web Server",
    description="FastAPI backend to run Multi-Agent Dev Status tracking pipeline using LangGraph."
)

# Ensure the static folder exists
Path("static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class PathRequest(BaseModel):
    path: str
    max_revisions: int = 3

def run_workflow_for_file(file_path: Path, max_revisions: int) -> dict:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
        
    # Initialize agent state
    initial_state: AgentState = {
        "raw_filepath": str(file_path.absolute()),
        "github_data": None,
        "jira_data": None,
        "metrics": None,
        "analysis": None,
        "report": None,
        "validation": None,
        "revision_count": 0,
        "max_revisions": max_revisions,
        "logs": [],
        "errors": []
    }
    
    logger.info(f"[Server] Running pipeline for file: {file_path} with max_revisions: {max_revisions}")
    
    try:
        final_state = workflow_app.invoke(initial_state)
        
        # Helper to dump pydantic models to dicts
        def dump_model(obj):
            if obj is None:
                return None
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            return obj
            
        serialized_state = {
            "raw_filepath": final_state.get("raw_filepath"),
            "github_data": dump_model(final_state.get("github_data")),
            "jira_data": dump_model(final_state.get("jira_data")),
            "metrics": dump_model(final_state.get("metrics")),
            "analysis": dump_model(final_state.get("analysis")),
            "report": final_state.get("report"),
            "validation": dump_model(final_state.get("validation")),
            "revision_count": final_state.get("revision_count"),
            "max_revisions": final_state.get("max_revisions"),
            "logs": final_state.get("logs", []),
            "errors": final_state.get("errors", [])
        }
        return serialized_state
    except Exception as e:
        logger.critical(f"[Server] Pipeline run crashed: {e}")
        raise e

@app.get("/", response_class=HTMLResponse)
async def serve_home():
    html_file = Path("static/index.html")
    if not html_file.exists():
        return HTMLResponse(
            content="<html><body><h1>static/index.html not found! Please create it.</h1></body></html>",
            status_code=404
        )
    with open(html_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/samples")
async def get_samples():
    data_dir = Path("data")
    if not data_dir.exists():
        return []
    # List all JSON files in the data folder
    files = [f.name for f in data_dir.glob("*.json")]
    return sorted(files)

@app.post("/api/analyze/path")
async def analyze_path(req: PathRequest):
    file_path = Path(req.path)
    # Check if the path exists directly or as a relative path under data/
    if not file_path.exists() and (Path("data") / req.path).exists():
        file_path = Path("data") / req.path
        
    if not file_path.exists():
        raise HTTPException(
            status_code=404, 
            detail=f"File not found on server at: {req.path}"
        )
        
    try:
        result = run_workflow_for_file(file_path, req.max_revisions)
        return JSONResponse(content=jsonable_encoder(result))
    except Exception as e:
        return JSONResponse(
            status_code=500, 
            content={"error": str(e), "message": "Failed to complete workflow run"}
        )

@app.post("/api/analyze/file")
async def analyze_file(
    file: UploadFile = File(...),
    max_revisions: int = Form(3)
):
    temp_dir = Path("data/temp_uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_file_path = temp_dir / f"upload_{timestamp}_{file.filename}"
    
    try:
        # Save file to temporary workspace path
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        result = run_workflow_for_file(temp_file_path, max_revisions)
        return JSONResponse(content=jsonable_encoder(result))
    except Exception as e:
        return JSONResponse(
            status_code=500, 
            content={"error": str(e), "message": "Failed to complete workflow run from uploaded file"}
        )
    finally:
        # Cleanup temp file
        if temp_file_path.exists():
            try:
                temp_file_path.unlink()
            except Exception as unlink_err:
                logger.warning(f"[Server] Failed to delete temp file {temp_file_path}: {unlink_err}")

if __name__ == "__main__":
    import uvicorn
    # Check if OPENAI_API_KEY is configured
    if not settings.openai_api_key:
        print("[Configuration Error] OPENAI_API_KEY is not configured in .env or environment variables.")
        sys.exit(1)
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
