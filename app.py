import base64
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
import gradio as gr
import requests

OLLAMA_BASE = "http://localhost:11434"
MODEL       = "gemma4:e4b"
STARTER_CODE = """\
# Write your code here
print("Hello, Gemma 4!")
\
"""

LANGUAGES = [
    "python", "javascript", "typescript", "bash", "sql",
    "rust", "go", "java", "c", "cpp", "html", "css",
    "json", "yaml", "markdown", "plaintext",
]
TEXT_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
    ".json", ".yaml", ".yml", ".toml", ".md", ".txt",
    ".csv", ".sql", ".sh", ".bash", ".rs", ".go",
    ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".php",
}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
DEFAULT_SYSTEM = """\
You are an expert coding assistant. When you write code:
- Always wrap it in a markdown code block with the language tag
- Write complete, working code — not fragments
- Briefly explain what the code does
You have a code-runner tool. Use it to validate logic when helpful.\
"""
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": (
                "Execute Python code in a sandboxed subprocess and return "
                "stdout + stderr. Use this to validate, test, or demonstrate code."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to run (max ~50 lines, 5 s timeout).",
                    }
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a mathematical expression precisely.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Python-compatible math expression, e.g. 'math.sqrt(2) * 100'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]

def _run_python(code: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        r = subprocess.run(
            ["python3", tmp],
            capture_output=True, text=True, timeout=5,
        )
        out = (r.stdout + r.stderr).strip()
        return out[:3000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "⏱ Timed out (>5 s)"
    except Exception as e:
        return f"Error: {e}"
    finally:
        os.unlink(tmp)

def _calculate(expr: str) -> str:
    ns = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    ns.update({"abs": abs, "round": round})
    try:
        return str(eval(expr, {"__builtins__": {}}, ns))  # noqa: S307
    except Exception as e:
        return f"Error: {e}"

def execute_tool(name: str, args: dict) -> str:
    if name == "run_code":
        return _run_python(args.get("code", ""))
    if name == "calculate":
        return _calculate(args.get("expression", ""))
    return f"Unknown tool: {name}"

def encode_image(path: str) -> str | None:
    if not path:
        return None
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

def file_as_context(path: str) -> str | None:
    if not path:
        return None
    p = Path(path)
    if p.suffix.lower() not in TEXT_EXTS:
        return None
    try:
        content = p.read_text(encoding="utf-8", errors="replace")[:8000]
        lang = p.suffix.lstrip(".")
        return f"\n\n**Attached file — {p.name}:**\n```{lang}\n{content}\n```"
    except Exception:
        return None

def resolve_gradio_path(val) -> str | None:
    if val is None:
        return None
    if isinstance(val, Path):
        s = str(val)
        return s if s.strip() else None
    if isinstance(val, str):
        s = val.strip()
        return s if s else None
    if isinstance(val, dict):
        p = val.get("path")
        if isinstance(p, str) and p.strip():
            return p.strip()
        nested = val.get("file")
        if isinstance(nested, dict):
            np = nested.get("path")
            if isinstance(np, str) and np.strip():
                return np.strip()
        return None
    name = getattr(val, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None

def is_image_path(path: str | None) -> bool:
    return bool(path) and Path(path).suffix.lower() in IMAGE_EXTS

def extract_last_code_block(text: str) -> tuple[str | None, str]:
    blocks = re.findall(r"```(\w*)\n(.*?)```", text, re.DOTALL)
    if blocks:
        lang, code = blocks[-1]
        return code.strip(), lang.strip() or "python"
    return None, "python"

def ollama_ok() -> bool:
    try:
        requests.get(f"{OLLAMA_BASE}/", timeout=2)
        return True
    except Exception:
        return False

def _gradio_content_to_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif "text" in block:
                    parts.append(str(block["text"]))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)

def _append_chat_turn(
    history: list | None, user_text: str, assistant_text: str
) -> list:
    base = list(history) if history else []
    return base + [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": assistant_text},
    ]

def run_code_btn(code: str) -> str:
    if not code.strip():
        return "Nothing to run."
    result = _run_python(code)
    return result

def chat(
    message, history, image_path, file_path,
    editor_code, language, system_prompt,
    agentic, thinking, temperature,
):
    messages = [{"role": "system", "content": system_prompt}]
    for h in history or []:
        if not isinstance(h, dict):
            continue
        role = h.get("role")
        if role not in ("user", "assistant"):
            continue
        messages.append(
            {"role": role, "content": _gradio_content_to_text(h.get("content"))}
        )
    
    content = message
    
    # Add image context
    image_path = resolve_gradio_path(image_path)
    if image_path and is_image_path(image_path):
        b64 = encode_image(image_path)
        if b64:
            content += f"\n\n**[Image attached: {Path(image_path).name}]**"
    
    # Add file context
    file_path = resolve_gradio_path(file_path)
    if file_path:
        file_ctx = file_as_context(file_path)
        if file_ctx:
            content += file_ctx
    
    # Add editor code
    if editor_code.strip() and editor_code.strip() != STARTER_CODE.strip():
        content += (
            f"\n\n**Current code in editor ({language}):**\n"
            f"```{language}\n{editor_code}\n```"
        )
    
    messages.append({"role": "user", "content": content})
    
    # Build request payload
    options = {
        "temperature": temperature,
        "top_k": 40,
        "top_p": 0.9,
    }
    
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "options": options,
    }

    if agentic:
        payload["tools"] = TOOLS

    # Stream response
    full_response = ""
    new_code = None
    
    try:
        with requests.post(
            f"{OLLAMA_BASE}/api/chat",
            json=payload,
            stream=True,
            timeout=60,
        ) as resp:
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    if chunk.get("message", {}).get("content"):
                        full_response += chunk["message"]["content"]
                    
                    # Handle tool calls
                    if agentic and chunk.get("message", {}).get("tool_calls"):
                        for tc in chunk["message"]["tool_calls"]:
                            fn_name = tc["function"]["name"]
                            fn_args = tc["function"]["arguments"]
                            result = execute_tool(fn_name, fn_args)
                            if fn_name == "run_code" and fn_args.get("code"):
                                new_code = fn_args["code"]
                            messages.append({"role": "assistant", "content": full_response})
                            messages.append({"role": "tool", "content": result})
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        full_response = f"Error: {e}"
    
    # Extract code from response
    extracted, _ = extract_last_code_block(full_response)
    if extracted:
        new_code = extracted
    
    # Update history and return
    new_history = _append_chat_turn(history, message, full_response)
    
    return new_history, new_code or editor_code, ""

CSS = """\
gradio-app {
    --body-background-fill:   #f0f3f7;
    --block-background-fill:  #ffffff;
    --body-text-color:        #1f2328;
    --button-primary-background-fill: #1a7f37;
}

body.dark gradio-app {
    --body-background-fill:   #0d1117;
    --block-background-fill:  #1c2128;
    --body-text-color:        #e6edf3;
    --button-primary-background-fill: #238636;
}
\
"""

THEME = gr.Theme(
    primary_hue   = "blue",
    secondary_hue = "slate",
    neutral_hue   = "slate",
    font      = ["system-ui", "sans-serif"],
    font_mono = ["monospace"],
)

def respond(message, history, image_path, file_path, editor_code, language, system_prompt, agentic, thinking, temperature):
    new_history, new_code, cleared_input = chat(
        message, history, image_path, file_path,
        editor_code, language, system_prompt,
        agentic, thinking, temperature,
    )
    return new_history, new_code, cleared_input

with gr.Blocks(title="Gemma 4 · Code Assistant") as demo:
    with gr.Row(equal_height=False):
        # LEFT: Code Editor
        with gr.Column(scale=11):
            with gr.Row():
                lang_sel = gr.Dropdown(choices=LANGUAGES, value="python", label="Language")
                run_btn  = gr.Button("Run Code", elem_classes=["run-btn"])
                clear_ed = gr.Button("Clear")
            code_editor = gr.Code(
                value=STARTER_CODE,
                language="python",
                label="Editor",
                lines=24,
                interactive=True,
            )
            run_output = gr.Textbox(
                label="Output",
                lines=6,
                interactive=False,
                elem_id="run-output",
            )
            run_btn.click(fn=run_code_btn, inputs=[code_editor], outputs=[run_output])
            clear_ed.click(fn=lambda: STARTER_CODE, outputs=[code_editor])
        
        # RIGHT: Chat
        with gr.Column(scale=9):
            chatbot = gr.Chatbot(value=[], elem_id="chatbot", height=430)
            with gr.Row():
                image_upload = gr.Image(label="Image (vision)", type="filepath")
                file_upload  = gr.File(label="Code / text file")
            with gr.Row():
                msg_input = gr.Textbox(placeholder="Ask the agent...", scale=6)
                send_btn  = gr.Button("Send", variant="primary")
            with gr.Row():
                agentic_cb  = gr.Checkbox(label="Enable Agentic", value=True)
                thinking_cb = gr.Checkbox(label="Enable Thinking", value=False)
                clear_chat  = gr.Button("Clear chat")
            with gr.Accordion("Settings", open=False):
                sys_prompt  = gr.Textbox(value=DEFAULT_SYSTEM, label="System prompt")
                temperature = gr.Slider(minimum=0.0, maximum=2.0, value=0.7)
        
        _inputs = [
            msg_input, chatbot, image_upload, file_upload,
            code_editor, lang_sel,
            sys_prompt, agentic_cb, thinking_cb, temperature,
        ]
        _outputs = [chatbot, code_editor, msg_input]
        
        send_btn.click(fn=respond, inputs=_inputs, outputs=_outputs)
        msg_input.submit(fn=respond, inputs=_inputs, outputs=_outputs)
        clear_chat.click(fn=lambda: [], outputs=[chatbot])

if __name__ == "__main__":
    print(f"Model  : {MODEL}")
    print(f"Ollama : {OLLAMA_BASE}")
    if not ollama_ok():
        print("Ollama not detected — run ollama serve before chatting")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        theme=THEME,
        css=CSS,
    )