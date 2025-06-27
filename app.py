from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
import subprocess
import os
import uuid
import asyncio

app = FastAPI()

LOG_DIR = "step_logs"
os.makedirs(LOG_DIR, exist_ok=True)


# -------------------------------
# Models
# -------------------------------

class Step(BaseModel):
    name: str
    command: str
    depends_on: List[str] = []


class Stage(BaseModel):
    name: str
    steps: List[Step]


class ActionPlan(BaseModel):
    action_plan_name: str
    stages: List[Stage]


# -------------------------------
# Helper: Step Executor
# -------------------------------

async def execute_step(stage_name: str, step: Step, completed_steps: set):
    log_file = os.path.join(LOG_DIR, f"{step.name}_{uuid.uuid4().hex}.log")
    start_time = datetime.utcnow()

    # Wait until dependencies are complete
    for dep in step.depends_on:
        while dep not in completed_steps:
            await asyncio.sleep(0.2)

    try:
        with open(log_file, "w") as log:
            log.write(f"Step: {step.name}\nStage: {stage_name}\nStart: {start_time}\n\n")
            log.flush()

            result = subprocess.run(step.command, shell=True, capture_output=True, text=True)
            log.write(result.stdout)
            if result.stderr:
                log.write("\nERROR:\n" + result.stderr)

            end_time = datetime.utcnow()
            log.write(f"\nEnd: {end_time}\n")

        completed_steps.add(step.name)

    except Exception as e:
        raise RuntimeError(f"Failed step {step.name}: {str(e)}")


# -------------------------------
# Main ActionPlan Executor
# -------------------------------

async def run_action_plan(action_plan: ActionPlan):
    completed_steps = set()

    for stage in action_plan.stages:
        step_tasks = []

        for step in stage.steps:
            task = asyncio.create_task(execute_step(stage.name, step, completed_steps))
            step_tasks.append(task)

        await asyncio.gather(*step_tasks)


# -------------------------------
# API Route
# -------------------------------

@app.post("/run-action-plan/")
async def run_plan(plan: ActionPlan):
    try:
        asyncio.create_task(run_action_plan(plan))
        return {"message": f"Action plan '{plan.action_plan_name}' started."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
