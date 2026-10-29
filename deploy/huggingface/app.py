"""Entry point for Hugging Face Spaces.

Spaces run `python app.py` and route traffic to port 7860. The Space uses the Gradio SDK only
as a Python runtime; the application served is the regular FastAPI app.

Free accounts can host Python Spaces only on ZeroGPU hardware. ZeroGPU refuses to start unless
at least one `@spaces.GPU` function is reported, and the report is sent from inside
`gr.Blocks.launch()`. KisanAgent does all inference through Nebius Token Factory, so this file
defines a placeholder GPU function that is never called and launches an empty Gradio app on a
loopback-only port purely to send that report.
"""

import sys
from pathlib import Path

# isort: off
import spaces  # must be imported before gradio so ZeroGPU can patch it
import gradio as gr

# isort: on
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from kisan_agent.main import create_app  # noqa: E402

PUBLIC_PORT = 7860
INTERNAL_GRADIO_PORT = 7861


@spaces.GPU(duration=1)
def _zerogpu_placeholder() -> None:
    """Satisfies the ZeroGPU startup check. Never called."""


def _report_to_zerogpu() -> None:
    with gr.Blocks() as placeholder:
        gr.Markdown("KisanAgent is served on the main port.")
    placeholder.launch(
        server_name="127.0.0.1",
        server_port=INTERNAL_GRADIO_PORT,
        prevent_thread_lock=True,
        show_error=False,
    )


if __name__ == "__main__":
    _report_to_zerogpu()
    uvicorn.run(create_app(), host="0.0.0.0", port=PUBLIC_PORT)
