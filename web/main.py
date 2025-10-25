"""
FastAPI backend for Blender AI Simulation Generator.

Provides:
- REST API for simulation generation
- Server-Sent Events (SSE) for real-time progress
- Static file serving for frontend
- Result download endpoints
"""

import asyncio
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
import uuid

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src import SimulationOrchestrator
from src.models.schemas import SimulationResult


# Pydantic models for API
class GenerationRequest(BaseModel):
    """Request model for simulation generation."""
    prompt: str = Field(..., description="Natural language simulation description", min_length=3)
    enable_refinement: bool = Field(default=False, description="Enable quality-based refinement")
    max_refinement_iterations: int = Field(default=2, ge=1, le=5, description="Max refinement attempts")


class GenerationResponse(BaseModel):
    """Response model for simulation generation."""
    job_id: str
    status: str
    message: str


class StatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str
    status: str
    progress: float
    current_step: str
    result: Optional[dict] = None
    errors: list[str] = Field(default_factory=list)


# Create FastAPI app
app = FastAPI(
    title="Blender AI Simulation Generator API",
    description="Generate Blender simulations from natural language using Claude AI",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
orchestrator = SimulationOrchestrator()
active_jobs = {}  # job_id -> job info


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    print("=" * 70)
    print("  Blender AI Simulation Generator API")
    print("=" * 70)

    # Check system readiness
    is_ready, issues = orchestrator.check_system_ready()
    if not is_ready:
        print("\n⚠️  WARNING: System not fully ready:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nSome API endpoints may not work correctly.\n")
    else:
        print("\n✓ System ready!")
        print(f"Output directory: {orchestrator.output_dir}")
        print()

    print("API Documentation: http://localhost:8000/docs")
    print("=" * 70)
    print()


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main frontend page."""
    static_dir = Path(__file__).parent / "static"
    index_file = static_dir / "index.html"

    if index_file.exists():
        with open(index_file, 'r') as f:
            return HTMLResponse(content=f.read())
    else:
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Blender AI Simulation Generator</title>
</head>
<body>
    <h1>Blender AI Simulation Generator</h1>
    <p>API is running! Visit <a href="/docs">/docs</a> for API documentation.</p>
</body>
</html>
"""


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    is_ready, issues = orchestrator.check_system_ready()

    return {
        "status": "healthy" if is_ready else "degraded",
        "ready": is_ready,
        "issues": issues,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/materials")
async def list_materials():
    """List available materials."""
    materials = orchestrator.list_available_materials()
    return {
        "categories": materials,
        "total_count": sum(len(mats) for mats in materials.values())
    }


@app.post("/generate", response_model=GenerationResponse)
async def generate_simulation(
    request: GenerationRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a new simulation generation job.

    Returns immediately with a job_id. Use /status/{job_id} or /stream/{job_id}
    to track progress.
    """
    # Create job ID
    job_id = str(uuid.uuid4())

    # Initialize job info
    active_jobs[job_id] = {
        "status": "queued",
        "progress": 0.0,
        "current_step": "Queued",
        "result": None,
        "errors": [],
        "created_at": datetime.now().isoformat()
    }

    # Start generation in background
    background_tasks.add_task(
        run_generation,
        job_id=job_id,
        prompt=request.prompt,
        enable_refinement=request.enable_refinement,
        max_refinement_iterations=request.max_refinement_iterations
    )

    return GenerationResponse(
        job_id=job_id,
        status="queued",
        message="Generation started. Use /status/{job_id} to track progress."
    )


async def run_generation(
    job_id: str,
    prompt: str,
    enable_refinement: bool,
    max_refinement_iterations: int
):
    """Run generation in background."""
    try:
        # Update status
        active_jobs[job_id]["status"] = "running"

        # Progress callback
        def progress_callback(step: str, progress: float):
            active_jobs[job_id]["current_step"] = step
            active_jobs[job_id]["progress"] = progress

        # Generate simulation
        result = orchestrator.generate_simulation(
            user_prompt=prompt,
            progress_callback=progress_callback,
            enable_refinement=enable_refinement,
            max_refinement_iterations=max_refinement_iterations
        )

        # Update job with result
        if result.success:
            active_jobs[job_id]["status"] = "completed"
            active_jobs[job_id]["progress"] = 1.0
            active_jobs[job_id]["result"] = {
                "blend_file": result.blend_file,
                "quality_score": result.quality_metrics.quality_score if result.quality_metrics else None,
                "total_time": result.total_time_seconds,
                "agent_times": result.agent_times,
                "refinement_count": result.refinement_count
            }
        else:
            active_jobs[job_id]["status"] = "failed"
            active_jobs[job_id]["errors"] = result.errors

    except Exception as e:
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["errors"] = [str(e)]


@app.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    """Get current status of a generation job."""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = active_jobs[job_id]

    return StatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        current_step=job["current_step"],
        result=job.get("result"),
        errors=job.get("errors", [])
    )


@app.get("/stream/{job_id}")
async def stream_progress(job_id: str):
    """
    Stream progress updates using Server-Sent Events (SSE).

    Connects to this endpoint to receive real-time updates as the simulation generates.
    """
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        """Generate SSE events."""
        last_progress = -1

        while True:
            if job_id not in active_jobs:
                break

            job = active_jobs[job_id]

            # Send update if progress changed
            if job["progress"] != last_progress:
                last_progress = job["progress"]

                event_data = {
                    "status": job["status"],
                    "progress": job["progress"],
                    "step": job["current_step"],
                }

                # Include result if completed
                if job["status"] == "completed" and job["result"]:
                    event_data["result"] = job["result"]

                # Include errors if failed
                if job["status"] == "failed":
                    event_data["errors"] = job["errors"]

                yield f"data: {json.dumps(event_data)}\n\n"

            # Stop if job is complete
            if job["status"] in ["completed", "failed"]:
                break

            # Wait before checking again
            await asyncio.sleep(0.5)

        # Send final event
        yield f"data: {json.dumps({'status': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/download/{job_id}")
async def download_result(job_id: str):
    """Download the generated .blend file."""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = active_jobs[job_id]

    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")

    if not job["result"] or not job["result"].get("blend_file"):
        raise HTTPException(status_code=404, detail="Blend file not found")

    blend_file = Path(job["result"]["blend_file"])

    if not blend_file.exists():
        raise HTTPException(status_code=404, detail="Blend file not found on disk")

    return FileResponse(
        blend_file,
        media_type="application/octet-stream",
        filename=blend_file.name
    )


@app.get("/jobs")
async def list_jobs():
    """List all jobs (for debugging)."""
    return {
        "jobs": [
            {
                "job_id": job_id,
                "status": job["status"],
                "progress": job["progress"],
                "created_at": job["created_at"]
            }
            for job_id, job in active_jobs.items()
        ],
        "total": len(active_jobs)
    }


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job from memory."""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    del active_jobs[job_id]

    return {"message": "Job deleted successfully"}


# Run server
if __name__ == "__main__":
    import uvicorn

    print("\nStarting Blender AI API Server...")
    print("Press Ctrl+C to stop\n")

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )
