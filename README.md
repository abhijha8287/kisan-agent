# KisanAgent

KisanAgent is a field advisor for smallholder farmers. A farmer sends a photo of a damaged
plant and a question, in their own language. KisanAgent identifies the problem from the photo,
looks up current treatment guidance, local market prices and the weather forecast, and writes a
short plan the farmer can act on today, with sources.

It runs on NVIDIA Nemotron models served by Nebius Token Factory, with live web research from
Tavily.

## The problem

India alone has more than 100 million smallholder farms. When a crop shows disease, the farmer
usually has a few days to act, and the advice they can get is either generic, out of date, or
from the shop that sells the pesticide. A good decision depends on three things at once:

- **What is wrong**, which needs someone who can recognise the disease.
- **What it costs**, because a ₹1,200 spray on a crop that will fetch ₹900 is a loss.
- **What the weather will do**, because spraying the day before rain wastes the chemical.

Extension officers combine these, but there are too few of them. KisanAgent does the same
combination in under a minute, in nine Indian languages, and shows its sources so the farmer or
an officer can check them.

## How it works

Each consultation goes through four stages. Every stage is routed to the model suited to it,
and the interface shows which model handled which stage and how long it took.

| Stage      | What happens                                                                 | Runs on                                         |
| ---------- | ---------------------------------------------------------------------------- | ----------------------------------------------- |
| Diagnose   | Reads the photo: crop, condition, confidence, visible symptoms               | Nemotron 3.5 Super VL, Token Factory            |
| Understand | Interprets the question in any language and plans three web searches        | Nemotron 3 Nano, Token Factory                  |
| Research   | Runs the treatment, market-price and weather searches in parallel            | Tavily Search API                               |
| Advise     | Combines diagnosis and research into a cited, step-by-step plan, streamed    | Nemotron 3 Ultra, Token Factory                 |

The routing follows the cost and latency profile of each task. Intake is a small structured
extraction and runs on Nano, so it returns in a second or two and costs very little. The final
plan has to weigh disease severity, chemical cost, market price and rain against each other,
which is where Ultra's reasoning is worth paying for.

The pipeline is built to degrade rather than fail. If the photo cannot be read, the agent
continues from the question alone. If intake returns malformed output, it falls back to
deterministic search queries. If one search fails, the others are still used. Only a failure of
the final model ends the consultation with an error.

The advisor prompt requires that prices, forecasts and scheme details come from the research
notes and are cited, and that the answer says so plainly when no price or forecast was found.
Chemical recommendations must include active ingredient, dose per litre and safety guidance.

## Repository layout

```
.
├── src/kisan_agent/          Application package
│   ├── main.py               Application factory: wires clients, routes and static files
│   ├── core/                 Cross-cutting code with no domain knowledge
│   │   ├── config.py         Settings loaded from environment variables or .env
│   │   ├── logging.py        Logging setup
│   │   └── text.py           Cleaning model output: JSON extraction, reasoning-tag removal
│   ├── integrations/         Thin clients for external services, one file per service
│   │   ├── token_factory.py  Nebius Token Factory (OpenAI-compatible) chat and streaming
│   │   └── tavily.py         Tavily search
│   ├── agent/                The advisory logic itself, independent of HTTP
│   │   ├── pipeline.py       The four-stage pipeline and its fallbacks
│   │   ├── prompts.py        System prompts and message builders for each stage
│   │   ├── schemas.py        Domain models passed between stages and emitted as events
│   │   └── languages.py      Supported answer languages and speech-recognition codes
│   └── api/                  HTTP layer
│       ├── routes.py         /api/health, /api/meta, /api/consult
│       ├── dependencies.py   FastAPI dependency providers
│       └── sse.py            Server-sent events encoding
├── web/                      Static frontend, served by the same FastAPI app
│   ├── index.html
│   └── assets/
│       ├── styles.css
│       └── js/
│           ├── app.js        Form handling and rendering of agent events
│           ├── stream.js     Parser for the server-sent events response
│           ├── markdown.js   Renderer for the advice text and citation links
│           └── image.js      Client-side photo downscaling before upload
├── tests/                    Unit and API tests, using in-memory fakes for both services
├── deploy/huggingface/       Entry point, Space header and script for Hugging Face Spaces
├── Dockerfile                Container image for Nebius Serverless Endpoints
├── pyproject.toml            Dependencies and tool configuration
└── .env.example              Template for local configuration
```

Why the code is split this way:

- **`integrations/` is separate from `agent/`** so the pipeline depends on two small interfaces
  (`ChatModel`, `WebSearch`) rather than on vendor SDKs. The tests replace both with fakes, and
  swapping a provider means changing one file.
- **`agent/` has no HTTP code.** The pipeline yields plain events. The API layer turns them into
  server-sent events, but the same pipeline could feed a WhatsApp bot or a batch job unchanged.
- **`core/` holds code that every layer uses but that knows nothing about farming.**
- **`web/` has no build step.** It is plain HTML, CSS and ES modules, served by the backend, so
  there is a single process to run and a single container to deploy.

## Running locally

Requirements: Python 3.11 or later and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env          # then fill in NEBIUS_API_KEY (and TAVILY_API_KEY)
uv sync
uv run uvicorn kisan_agent.main:create_app --factory --reload
```

Open http://localhost:8000.

- A Nebius Token Factory API key is available from https://tokenfactory.nebius.com.
- A Tavily API key is available from https://app.tavily.com. Without one, search runs in
  Tavily's keyless mode, which works but is rate-limited.

### Configuration

All settings are read from environment variables (or `.env`).

| Variable            | Default                                    | Purpose                                 |
| ------------------- | ------------------------------------------ | --------------------------------------- |
| `NEBIUS_API_KEY`    | required                                   | Token Factory API key                   |
| `TAVILY_API_KEY`    | optional                                   | Tavily API key; keyless mode if unset   |
| `NEBIUS_BASE_URL`   | `https://api.tokenfactory.nebius.com/v1/`  | Token Factory endpoint                  |
| `MODEL_FAST`        | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`    | Intake and search planning              |
| `MODEL_VISION`      | `nvidia/Nemotron-3.5-Super-VL`             | Photo diagnosis                         |
| `MODEL_REASONING`   | `nvidia/Nemotron-3-Ultra-550b-a55b`        | Final plan                              |
| `REQUEST_TIMEOUT_S` | `120`                                      | Timeout for each upstream call          |
| `LOG_LEVEL`         | `INFO`                                     |                                         |

## API

`POST /api/consult` accepts `multipart/form-data`:

| Field      | Required | Notes                                         |
| ---------- | -------- | --------------------------------------------- |
| `question` | yes      | 3 to 1000 characters, any language            |
| `language` | no       | One of the names returned by `/api/meta`      |
| `location` | no       | Village, district or state                    |
| `image`    | no       | JPEG, PNG or WebP, up to 8 MB                 |

The response is a `text/event-stream` with these events, in order:

| Event       | Payload                                                         |
| ----------- | --------------------------------------------------------------- |
| `step`      | `name`, `status`, `model`, `detail`, `elapsed_ms`               |
| `diagnosis` | Photo diagnosis (only when a photo was sent and read)           |
| `intake`    | Interpreted concern and the planned search queries              |
| `sources`   | Numbered research sources used for citations                    |
| `token`     | A fragment of the advice text                                   |
| `done`      | Total elapsed time                                              |
| `error`     | Sent instead of `done` if the advice could not be generated     |

Example:

```bash
curl -N http://localhost:8000/api/consult \
  -F question="Brown spots with yellow rings on tomato leaves" \
  -F language=Hindi -F location="Nashik, Maharashtra" \
  -F image=@leaf.jpg
```

`GET /api/meta` returns the supported languages and the configured models. `GET /api/health`
returns service status.

## Tests

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

The tests cover the pipeline's routing and every fallback path, model-output parsing (including
reasoning tags split across stream chunks), and the HTTP layer's validation and streaming. They
use in-memory fakes and make no network calls.

## Deploying

The app is a single stateless process, so it can run on free or CPU-only hosting.

### Hugging Face Spaces

Free Spaces use the Gradio SDK, which here serves only as a Python runtime: it installs
`requirements.txt` and runs `app.py` on port 7860, and `app.py` starts the regular FastAPI app.

1. Create a Space at https://huggingface.co/new-space with the **Gradio** SDK, **Blank**
   template and free CPU hardware.
2. In the Space settings, add `NEBIUS_API_KEY` and `TAVILY_API_KEY` as **secrets**.
3. Authenticate once with `hf auth login --add-to-git-credential`, then run:

```bash
deploy/huggingface/deploy.sh <hf-username>/<space-name>
```

The script pushes the current commit to the Space and adds the Space-only files (`app.py`,
`requirements.txt` exported from `uv.lock`, and the configuration header in `README.md`) to
the copy it pushes, so they do not clutter the repository.

### Nebius Serverless Endpoints

The app needs only a CPU endpoint.

```bash
docker build --platform linux/amd64 -t <registry>/kisan-agent:0.1.0 .
docker push <registry>/kisan-agent:0.1.0

nebius ai endpoint create \
  --name kisan-agent \
  --image <registry>/kisan-agent:0.1.0 \
  --platform cpu-d3 \
  --preset 4vcpu-16gb \
  --container-port 8000 \
  --env "NEBIUS_API_KEY=<key>,TAVILY_API_KEY=<key>" \
  --public \
  --subnet-id <subnet_id>
```

For a production deployment, store the keys in Nebius MysteryBox and pass them with
`--env-secret` instead of `--env`. Authentication is left off so the web interface is publicly
reachable. See the
[Nebius Serverless Endpoints documentation](https://docs.nebius.com/serverless/quickstart/endpoints)
for registry setup and the available platforms and presets.

## Use of NVIDIA and Nebius technology

- **NVIDIA Nemotron 3 Ultra** writes the final plan. This is the step that has to reason across
  diagnosis, cost, price and weather, and write it clearly in the farmer's language.
- **NVIDIA Nemotron 3 Nano** handles intake: understanding questions in nine languages and
  producing structured search plans as JSON.
- **NVIDIA Nemotron 3.5 Super VL** performs the photo diagnosis.
- **Nebius Token Factory** serves all three through one OpenAI-compatible endpoint, so routing
  between models is a change of model name, not a change of client or provider.
- **Nebius Serverless Endpoints** host the application container.

## Limitations

- Diagnosis from a single photo is an aid, not a laboratory test. The interface states this,
  and the advice tells the farmer when to contact an extension officer.
- Market-price coverage depends on what is published online for the farmer's area. When no
  price is found, the advice says so instead of estimating one.
- Voice input uses the browser's built-in speech recognition, which is available in Chrome,
  Edge and Safari but not Firefox.

## License

MIT. See [LICENSE](LICENSE).
