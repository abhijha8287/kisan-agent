"""Entry point for Hugging Face Spaces.

Spaces run `python app.py` and route traffic to port 7860. The Space uses the Gradio SDK only
as a Python runtime; the application served is the regular FastAPI app.

Free accounts can host Python Spaces only on ZeroGPU hardware, which refuses to start without
at least one `@spaces.GPU` function. KisanAgent does all inference through Nebius Token
Factory, so the decorated function below is a placeholder that is never called and never
requests a GPU.
"""

import sys
from pathlib import Path

import spaces
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from kisan_agent.main import create_app  # noqa: E402


@spaces.GPU(duration=1)
def _zerogpu_placeholder() -> None:
    """Satisfies the ZeroGPU startup check. Never called."""


if __name__ == "__main__":
    uvicorn.run(create_app(), host="0.0.0.0", port=7860)
