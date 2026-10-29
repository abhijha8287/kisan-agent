"""Entry point for Hugging Face Spaces.

Free Spaces run `python app.py` and route traffic to port 7860. The Space uses the Gradio
SDK only as a Python runtime; the application served is the regular FastAPI app.
"""

import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from kisan_agent.main import create_app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(create_app(), host="0.0.0.0", port=7860)
