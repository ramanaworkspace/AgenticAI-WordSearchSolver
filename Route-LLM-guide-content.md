# Consolidated JPEG Content

This document transcribes and organizes the readable content from the JPEGs in this folder. Several photos show overlapping portions of the same on-screen Route-LLM guide; repeated lines and examples have been included only once. The animal worksheet is separate content and is recorded in its own section.

**Source coverage:** 9 JPEGs were reviewed: `Animal Image.jpeg` and eight `WhatsApp Image 2026-10-10...jpeg` screen photos. The overlapping guide excerpts are ordered by the visible document content, not by treating each photo as a separate document.

> **Credential warning:** One of the source photos visibly contains an API key. It is intentionally not reproduced here. Treat it as exposed: revoke or rotate it, and avoid sharing the unredacted image. Use a secret manager or environment variable for replacement credentials.

## 1. Route-LLM API Key Guide

### Key and endpoint details

- **Owner shown:** `qardlift_ai_assessment`
- **Base URL shown:** `http://13.206.171.236/v1`
- **Budget shown:** approximately **$50.00 USD**
- **API key:** redacted; the source image visibly contains the credential.
- The guide warns that the key should be stored securely and will not be shown again.

Use an HTTPS endpoint for requests carrying a bearer token whenever one is available. The URL above is transcribed as shown in the image; confirm the correct, secure endpoint with the gateway administrator before use.

### Models shown

| Model name | Type / note |
|---|---|
| `mistral-large-3` | Chat |
| `mistral.mistral-large-3-675b-instruct` | Bedrock model ID shown for Mistral |
| `kimi-k2-5` | Chat |
| `moonshotai.kimi-k2.5` | Bedrock model ID shown for Kimi |

The guide's examples call the gateway model names (`mistral-large-3` and `kimi-k2-5`); use the exact model identifier enabled for the account.

### Basic chat request

The service exposes an OpenAI-compatible chat-completions endpoint. The guide shows both `curl` and Python examples.

#### cURL

```bash
curl http://13.206.171.236/v1/chat/completions \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral-large-3",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 256
  }'
```

#### Python

```python
from openai import OpenAI

client = OpenAI(
    api_key="<YOUR_API_KEY>",
    base_url="http://13.206.171.236/v1",
)

response = client.chat.completions.create(
    model="mistral-large-3",
    messages=[{"role": "user", "content": "Hello!"}],
    max_tokens=256,
)

print(response.choices[0].message.content)
```

Replace the placeholder with a securely stored key; do not paste a real key into source code or shared documentation.

### Sending images (multimodal)

The guide says image requests require both of the following:

1. The selected model must accept image input. It names `mistral-large-3` and `kimi-k2-5` as image-capable models in the photographed guide.
2. Image input must also be enabled on the gateway for the key/account. The image setting is described as environment-dependent and is not visible to the caller.

The request example uses an OpenAI-style message with text and an `image_url` entry. The image is encoded as a Base64 data URL:

```python
import base64
from openai import OpenAI

client = OpenAI(
    api_key="<YOUR_API_KEY>",
    base_url="http://13.206.171.236/v1",
)

with open("chart.png", "rb") as image_file:
    encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

response = client.chat.completions.create(
    model="mistral-large-3",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What does this chart show?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{encoded_image}"
                    },
                },
            ],
        }
    ],
    max_tokens=512,
)

print(response.choices[0].message.content)
```

The guide also includes a cURL example that builds a JSON request containing the same `messages` content and posts it to `/v1/chat/completions`.

#### Image rules and limits visible in the guide

- Formats listed: PNG, JPEG, GIF, and WebP.
- Image input is shown as Base64 data URL only; ordinary image URLs are not accepted by the gateway in the described setup.
- Image messages must use the `user` role; images in a `system` message are rejected.
- The photographed limits appear to specify approximately **1.20 MB Base64 per image** and **800 px per side**. These figures are difficult to read in the photos; verify the exact limits with the gateway administrator.
- Images consume tokens. The guide says the gateway uses a flat per-image token estimate, so a request containing an image can use noticeably more budget than a similarly sized text request.

#### Image-related errors

| Status | Likely cause |
|---|---|
| `400` | Image input is disabled for the gateway/key, or the selected model does not accept images. |
| `400` | The image value is not a Base64 data URL, or the format is unsupported. |
| `413` | The request body is too large; send fewer or smaller images. |

### Calling tools (function calling)

The guide describes OpenAI-compatible function calling through the `tools` request parameter and `tool_calls` response field. The models listed as supporting tools are:

- `mistral-large-3`
- `kimi-k2-5`

The gateway does not execute a tool's implementation. The application must inspect the model's tool call, run the corresponding function, send the result back as a `tool` message, and ask the model for its final response.

#### Python tool-calling example

```python
import json
from openai import OpenAI

client = OpenAI(
    api_key="<YOUR_API_KEY>",
    base_url="http://13.206.171.236/v1",
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name.",
                    }
                },
                "required": ["city"],
            },
        },
    }
]

messages = [
    {"role": "user", "content": "What's the weather in Pune?"}
]

response = client.chat.completions.create(
    model="mistral-large-3",
    messages=messages,
    tools=tools,
    max_tokens=512,
)

tool_call = response.choices[0].message.tool_calls[0]
arguments = json.loads(tool_call.function.arguments)

# Run the application-owned function after validating its arguments.
result = "31 C, humid"  # Example result for the requested city.

# Replay the assistant message, then provide the matching tool result.
messages.append(response.choices[0].message)
messages.append(
    {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": result,
    }
)

final_response = client.chat.completions.create(
    model="mistral-large-3",
    messages=messages,
    tools=tools,
    max_tokens=512,
)

print(final_response.choices[0].message.content)
```

The guide also provides cURL examples for listing models (`GET /v1/models`) and sending a chat-completions request with a tool definition.

#### Tool-choice behavior

| `tool_choice` value | Behavior |
|---|---|
| Omitted or `"auto"` | The model decides whether to call a tool. |
| `"required"` | The model must make a tool call. |
| `{"type": "function", "function": {"name": "..."}}` | The model is directed to call the named function. |
| `"none"` | The model must not call a tool. Tool definitions can still be present. |

#### Tool rules and limits shown

- A tool name must be **1–64 characters** and use letters, digits, underscores, or hyphens.
- Duplicate tool names are rejected.
- `parameters` is optional for a function that takes no arguments; when present, it must be a JSON Schema object.
- `function.arguments` is returned as a JSON string. Parse it as JSON and validate it against the expected schema before using it.
- Every tool-result message must include the matching `tool_call_id` from the assistant's tool call.
- Parallel tool calls are supported; the application must handle every returned call and send each result with its matching ID.
- Streaming tool calls are not supported; the guide says a request with `stream: true` returns `400`.
- Send the `tools` definitions on every request in the tool-calling loop, including the follow-up request after returning tool results.
- Tool arguments are model output, not trusted input. Validate types and values before passing them to application code, a shell, a query, or an external service.

#### Tool-calling flow

1. Send the user message and the tool definitions.
2. The model replies with `finish_reason: "tool_calls"` and one or more tool calls.
3. Run the requested application function(s).
4. Append the assistant response and send each result as a `tool` message with the matching `tool_call_id`.
5. Send another chat-completions request so the model can respond using the results.

Tool calling therefore takes at least two model requests. The guide recommends sending the tool definitions on every request in the loop; omitting them may result in an error.

#### Tool-calling errors

| Status / behavior | Likely cause |
|---|---|
| `400` | The selected model does not support tool calling. |
| `400` | Tool history does not match the required call/result sequence, or `tools` were omitted from a request in the loop. |
| `400` | A tool name is invalid or duplicated, `tool_choice` is invalid, or arguments are not a JSON object. |
| `400` | A `tool` message is missing `tool_call_id`. |
| `400` | Streaming was requested for tool calls. |
| `200`, but no tool call | The model chose not to call a tool, or tool support was not enabled as expected. |

#### Budget and safety notes for tools

- Tool schemas are included in the prompt and consume input tokens. The guide estimates roughly 100 tokens per tool before the call; the actual amount depends on schema size.
- Use concise descriptions and include only the tools relevant to the current request.
- Validate tool arguments in the application; the gateway does not validate their meaning or safety.

### Common request headers

```http
Authorization: Bearer <YOUR_API_KEY>
Content-Type: application/json
```

### Listing models

The guide shows this cURL pattern:

```bash
curl http://13.206.171.236/v1/models \
  -H "Authorization: Bearer <YOUR_API_KEY>"
```

### General troubleshooting

- A `400` response usually indicates an unsupported model/feature, malformed request, invalid image input, or malformed tool-call history.
- A `413` response indicates that the request is too large.
- Confirm that the selected model and gateway configuration both support the requested capability.
- Keep API keys private and validate all model-generated tool arguments before acting on them.

## 2. Animal Word-Search Worksheet

One JPEG shows a worksheet titled **“4 Letter Word Search — Animals.”** Its directions say: **“Find and circle the words below in the grid.”**

### Letter grid

```text
J F R O G J Y I
D G O A T Y W M
M U X C B V O L
L S C I E J L I
B E A K A S F O
Q A E D R W D N
S L Y C R A B D
F I S H Z N J H
```

### Words to find

`BEAR`, `CRAB`, `DUCK`, `FISH`, `FROG`, `GOAT`, `LION`, `SEAL`, `SWAN`, `WOLF`

The worksheet includes animal illustrations and credits **SunCatcherStudio.com**. The photographs show the puzzle but do not show a completed/marked solution.
