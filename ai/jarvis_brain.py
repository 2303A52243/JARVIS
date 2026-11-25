"""Intelligent Hybrid AI Brain for JARVIS.

Combines the OpenAI API (when configured) with an extensive,
natural offline NLP and Windows laptop command engine.
JARVIS can answer questions, execute real laptop actions, inspect hardware,
and converse in English, Telugu, and Hindi.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Callable, Dict, Any, Optional, Tuple

from app.config import get_settings
from core.tool_registry import get_tool_registry
from memory.database import save_message, get_history, add_note, search_notes, get_all_notes
from system.system_info import get_system_summary
from system.application_manager import launch_app, terminate_app, list_installed_apps, is_app_running
import system.pc_controller as pc_ctrl  # noqa: F401 - registers full PC control tools
from files.file_search import search_files
from files.document_parser import parse_document
from browser.web_search import web_search


_WAKE_PREFIX_RE = re.compile(
    r"^(?:hey\s+|ok\s+|okay\s+|hi\s+)?j\.?a\.?r\.?v\.?i\.?s\.?[\s,:\-]+(.+)$",
    re.IGNORECASE,
)

_TOOL_HINT_RE = re.compile(
    r"\b(open|launch|start|run|show|close|terminate|kill|quit|exit|volume|mute|unmute|"
    r"brightness|screenshot|capture|window|minimize|maximize|switch|lock|sleep|restart|"
    r"shutdown|power|clipboard|copy|paste|file|files|folder|folders|directory|dir|desktop|"
    r"downloads|documents|read|write|create|delete|move|rename|search|find|google|youtube|"
    r"browse|website|url|process|processes|cpu|ram|memory|battery|disk|storage|cmd|"
    r"powershell|command|click|mouse|type|press|shortcut|hotkey|settings|wifi|bluetooth|"
    r"app|apps|program|installed|note|notes|remember|play|pause|next|previous|track|song)\b",
    re.IGNORECASE,
)


def _strip_wake_prefix(text: str) -> str:
    """Strip leading 'Jarvis ...' / 'Hey Jarvis, ...' wake prefix when followed by a command."""
    m = _WAKE_PREFIX_RE.match(text.strip())
    if m:
        remainder = m.group(1).strip()
        if remainder:
            return remainder
    return text.strip()


def _try_fast_local_command(text: str, language: str = "en") -> Optional[str]:
    """Execute clear deterministic local PC/greeting/diagnostic commands without LLM latency."""
    effective = _strip_wake_prefix(text)
    lower = effective.lower().strip()

    # Greetings / language checks / clock
    if re.search(r"^(hello|hi|hey|greetings|good\s+(morning|afternoon|evening)|yo)(\s+jarvis)?[\s!.]*$", text.lower().strip()):
        return _handle_offline_query(text, language=language)
    if any(p in lower for p in ("know telugu", "speak telugu", "understand telugu", "know hindi", "speak hindi", "understand hindi")):
        return _handle_offline_query(effective, language=language)
    if re.search(r"^(what\s+time\s+is\s+it|current\s+time|time\??)$", lower):
        return f"The current time is {time.strftime('%I:%M %p')}."
    if re.search(r"^(today'?s\s+date|what\s+is\s+(?:the\s+)?date|date\??)$", lower):
        return f"Today is {time.strftime('%A, %B %d, %Y')}."

    # Volume / brightness / media / lock / screenshot
    vol_set = re.search(r"(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})", lower)
    if vol_set:
        return pc_ctrl.control_volume("set", int(vol_set.group(1)))
    if "volume up" in lower or "increase volume" in lower:
        return pc_ctrl.control_volume("up")
    if "volume down" in lower or "decrease volume" in lower:
        return pc_ctrl.control_volume("down")
    if "mute volume" in lower or "mute audio" in lower or lower in ("mute", "unmute"):
        return pc_ctrl.control_volume("mute" if "unmute" not in lower else "unmute")

    bright_set = re.search(r"brightness\s+(?:to\s+)?(\d{1,3})", lower)
    if bright_set:
        return pc_ctrl.control_brightness(int(bright_set.group(1)))
    if "screenshot" in lower or "capture screen" in lower:
        return pc_ctrl.take_screenshot()
    if "minimize all" in lower or "show desktop" in lower:
        return pc_ctrl.control_window("minimize_all")
    if "lock pc" in lower or "lock screen" in lower or "lock my laptop" in lower:
        return pc_ctrl.system_power_action("lock")
    if lower in ("play pause", "pause music", "resume music", "pause video", "play music"):
        return pc_ctrl.control_media("play_pause")
    if lower in ("next track", "next song"):
        return pc_ctrl.control_media("next")
    if lower in ("previous track", "previous song"):
        return pc_ctrl.control_media("previous")

    # Quick system metrics
    if any(k in lower for k in ("tell me about my laptop", "system info", "laptop info", "system status")):
        return _handle_offline_query(effective, language=language)
    if re.search(r"\bbattery\b", lower) and len(lower.split()) <= 7:
        return _handle_offline_query(effective, language=language)
    if re.search(r"\b(ram usage|memory usage|cpu usage)\b", lower):
        return _handle_offline_query(effective, language=language)

    # YouTube / URLs
    yt_match = re.search(r"^(?:play|search)\s+(.+?)\s+on\s+youtube$", lower)
    if yt_match:
        return pc_ctrl.open_url_or_search(yt_match.group(1), site="youtube")
    if lower in ("open youtube", "launch youtube"):
        return pc_ctrl.open_url_or_search("https://www.youtube.com")
    if lower in ("open google", "launch google"):
        return pc_ctrl.open_url_or_search("https://www.google.com")

    # Direct open / launch app or folder (if FileNotFoundError, fall through to LLM)
    open_match = re.search(r"^(?:open|launch|start|show)\s+(.+)$", lower)
    if open_match:
        target = open_match.group(1).strip()
        if not any(w in target for w in ("file ", "document ", "website ", "url ", "http", ".com", ".org")):
            cleaned_target = re.sub(r"^(?:the|my)\s+", "", target)
            cleaned_target = re.sub(r"\s+app$", "", cleaned_target).strip()
            if cleaned_target:
                try:
                    return launch_app(cleaned_target)
                except FileNotFoundError:
                    pass

    # Direct close / terminate app
    close_match = re.search(r"^(?:close|terminate|kill|exit)\s+(.+)$", lower)
    if close_match:
        target = re.sub(r"^(?:the|my)\s+", "", close_match.group(1).strip())
        target = re.sub(r"\s+app$", "", target).strip()
        if target and len(target.split()) <= 3:
            try:
                return terminate_app(target)
            except Exception:
                pass

    return None


def process_user_query(
    query: str,
    language: str = "en",
    on_sentence: Optional[Callable[[str], None]] = None,
) -> Tuple[str, bool]:
    """Process a user's natural language input.

    Args:
        query: User's command or question.
        language: ISO code ('en', 'te', 'hi').
        on_sentence: Optional callback invoked as soon as each complete sentence streams in
                     during cloud chat (enables pipelined TTS while LLM finishes generating).

    Returns:
        (response_text, should_speak)
    """
    settings = get_settings()
    cleaned = query.strip()
    if not cleaned:
        return ("At your service, Boss. How may I assist you?", True)

    # Save user message to memory
    save_message(role="user", content=cleaned, language=language)

    # 0. Fast Local Router (<20ms) — handles obvious PC commands, folders, apps, diagnostics locally
    fast_reply = _try_fast_local_command(cleaned, language=language)
    if fast_reply:
        save_message(role="assistant", content=fast_reply, language=language)
        if on_sentence:
            try:
                on_sentence(fast_reply)
            except Exception:
                pass
        return (fast_reply, True)

    effective_query = _strip_wake_prefix(cleaned)

    # 1. Cloud AI (OpenAI / OpenRouter) — stream plain chat for fast TTFT, or pass tools when needed
    if settings.is_api_key_configured:
        try:
            from ai.openai_client import get_openai_client
            client = get_openai_client()
            use_tools = bool(_TOOL_HINT_RE.search(effective_query))
            tools = None
            if use_tools:
                registry = get_tool_registry()
                tools = [
                    t for t in registry.get_openai_tools()
                    if t["function"]["name"] not in ("synthesize_speech", "transcribe_audio")
                ]

            history = get_history(limit=4)
            lang_name = "Telugu" if language == "te" else ("Hindi" if language == "hi" else "English")
            system_prompt = (
                "You are JARVIS, a fast, loyal personal AI assistant on the user's Windows PC.\n"
                + (
                    "You have full PC control tools (apps, folders, volume, brightness, screenshots, windows, "
                    "keyboard/mouse, power, URLs, clipboard, processes, PowerShell/CMD, files, web search). "
                    "Call the right tool immediately when asked to act.\n"
                    if use_tools
                    else ""
                )
                + f"Answer in {lang_name} cleanly and concisely (1-3 brief spoken-friendly sentences unless asked for detail). "
                "Address the user respectfully as Boss."
            )
            messages: list[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
            for h in history:
                if h["role"] == "user" and h["content"] == cleaned:
                    continue
                messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": effective_query})

            # Streaming fast path for conversational / knowledge answers (no tools overhead!)
            if not use_tools:
                stream_resp = client.chat_complete(
                    messages, stream=True, max_tokens=320
                )
                full_chunks: list[str] = []
                pending_buf = ""
                for chunk in stream_resp:
                    delta = chunk.choices[0].delta.content if getattr(chunk, "choices", None) else None
                    if delta:
                        full_chunks.append(delta)
                        if on_sentence:
                            pending_buf += delta
                            # Trigger speech on the first sentence boundary (. ! ? \n)
                            m = re.search(r"^(.+?[.!?\n]+)\s+(.*)$", pending_buf, re.DOTALL)
                            if m and len(m.group(1).strip()) >= 8:
                                first_part = m.group(1).strip()
                                pending_buf = m.group(2)
                                try:
                                    on_sentence(first_part)
                                except Exception:
                                    pass
                reply = "".join(full_chunks).strip()
                if reply:
                    if on_sentence and pending_buf.strip():
                        try:
                            on_sentence(pending_buf.strip())
                        except Exception:
                            pass
                    save_message(role="assistant", content=reply, language=language)
                    return (reply, True)

            # Tool-calling path when PC/file/web actions are hinted
            reply = ""
            for _ in range(4):
                resp = client.chat_complete(messages, stream=False, tools=tools, max_tokens=320)
                msg = resp.choices[0].message if hasattr(resp, "choices") else resp["choices"][0]["message"]
                tool_calls = getattr(msg, "tool_calls", None)
                if not tool_calls:
                    reply = (getattr(msg, "content", None) or "").strip()
                    break

                messages.append({
                    "role": "assistant",
                    "content": getattr(msg, "content", None) or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in tool_calls
                    ],
                })
                last_tool_output = ""
                for tc in tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        fn_args = {}
                    try:
                        tool_result = registry.execute_tool(fn_name, fn_args)
                    except Exception as tool_err:
                        tool_result = f"Tool execution error: {tool_err}"
                    last_tool_output = str(tool_result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": last_tool_output[:3000],
                    })

            if reply:
                save_message(role="assistant", content=reply, language=language)
                if on_sentence:
                    try:
                        on_sentence(reply)
                    except Exception:
                        pass
                return (reply, True)
        except Exception as api_exc:
            from security.audit_logger import get_audit_logger
            get_audit_logger().warning(f"Cloud chat failed ({api_exc}); using offline NLP engine.")

    # 2. Offline Intelligent NLP Engine (strip wake prefix so 'Jarvis ...' matches cleanly)
    reply = _handle_offline_query(effective_query, language=language)
    save_message(role="assistant", content=reply, language=language)
    if on_sentence:
        try:
            on_sentence(reply)
        except Exception:
            pass
    return (reply, True)


def _handle_offline_query(text: str, language: str = "en") -> str:
    lower = text.lower().strip()

    # ── TELUGU INQUIRIES & SCRIPT ───────────────────────────────────────────
    if (
        "telugu" in lower
        or any(c in text for c in ["తెలుగు", "నమస్కారం", "బాగున్నావా", "ఎలా ఉన్నావు", "జార్విస్", "ల్యాప్‌టాప్", "సహాయం", "చెప్పు"])
    ):
        if "know telugu" in lower or "speak telugu" in lower or "understand telugu" in lower:
            return (
                "అవును బాస్! నాకు తెలుగు వచ్చు. నేను మీతో తెలుగులో మాట్లాడగలను మరియు మీ ల్యాప్‌టాప్‌ను నియంత్రించగలను. "
                "మీకు ఏమి సహాయం కావాలి? (Yes Boss, I am fluent in Telugu and ready to assist you.)"
            )
        if "నమస్కారం" in text or "బాగున్నావా" in text or "ఎలా ఉన్నావు" in text or "hello" in lower or "hi" in lower:
            return "నమస్కారం బాస్! నేను చాలా బాగున్నాను. మీ ల్యాప్‌టాప్‌లో మీకు ఏ సహాయం కావాలి?"
        if "ల్యాప్‌టాప్" in text or "సిస్టమ్" in text or "పరిస్థితి" in text or "battery" in lower or "బ్యాటరీ" in text:
            info = get_system_summary()
            return (
                f"మీ ల్యాప్‌టాప్ వివరాలు:\n"
                f"• కంప్యూటర్ పేరు: {info.get('computer_name')}\n"
                f"• CPU వినియోగం: {info.get('cpu_usage_percent')}%\n"
                f"• RAM వినియోగం: {info.get('ram_usage_percent')}%\n"
                f"• బ్యాటరీ: {info.get('battery_percent')}%"
            )
        return "నేను మీ జార్విస్ సహాయకుడిని. యాప్‌లను తెరవడం, సిస్టమ్ తనిఖీ మరియు ఫైల్ సెర్చ్ చేయగలను."

    # ── HINDI INQUIRIES & SCRIPT ─────────────────────────────────────────────
    if (
        "hindi" in lower
        or any(c in text for c in ["हिन्दी", "हिंदी", "नमस्ते", "कैसे हो", "जार्विस", "लैपटॉप", "मदद", "बताओ"])
    ):
        if "know hindi" in lower or "speak hindi" in lower or "understand hindi" in lower:
            return (
                "हाँ बॉस! मुझे हिन्दी बहुत अच्छे से आती है। मैं आपके साथ हिन्दी में बातचीत कर सकता हूँ और आपके लैपटॉप के कार्य कर सकता हूँ। "
                "(Yes Boss, I am fluent in Hindi and ready to assist you.)"
            )
        if "नमस्ते" in text or "कैसे हो" in text or "हाल" in text or "hello" in lower:
            return "नमस्ते बॉस! मैं बिल्कुल ठीक हूँ। आपकी लैपटॉप में मैं क्या सहायता कर सकता हूँ?"
        if "लैपटॉप" in text or "सिस्टम" in text or "बैटरी" in text:
            info = get_system_summary()
            return (
                f"आपके लैपटॉप की स्थिति:\n"
                f"• नाम: {info.get('computer_name')}\n"
                f"• CPU उपयोग: {info.get('cpu_usage_percent')}%\n"
                f"• RAM उपयोग: {info.get('ram_usage_percent')}%\n"
                f"• बैटरी: {info.get('battery_percent')}%"
            )
        return "मैं आपका निजी सहायक जार्विस हूँ। मैं ऐप्स खोल सकता हूँ, सिस्टम जाँच सकता हूँ और फ़ाइलें ढूंढ सकता हूँ।"

    # ── GREETINGS & CASUAL CONVERSATION ──────────────────────────────────────
    if re.search(r"^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening)|yo)\b", lower):
        return (
            "Hello, Boss. JARVIS at your service. All laptop systems are fully operational. "
            "How may I assist you today?"
        )

    if "how are you" in lower or "how're you" in lower:
        return "I am functioning at peak efficiency, Boss. All diagnostics report nominal status. How can I help you today?"

    if "who are you" in lower or "what are you" in lower or "your name" in lower:
        return (
            "I am JARVIS — Just A Rather Very Intelligent System. "
            "I am your personal AI assistant running directly on your Windows laptop."
        )

    if "who made you" in lower or "who created you" in lower:
        return "I was engineered as your personal AI laptop assistant, inspired by Tony Stark's JARVIS architecture."

    if "thank you" in lower or "thanks" in lower:
        return "Always at your service, Boss. Glad I could help."

    if "tell me a joke" in lower or "joke" in lower:
        return (
            "Why do programmers prefer dark mode?\n"
            "Because light attracts bugs! 😄"
        )

    if "time" in lower or "what time is it" in lower or "current time" in lower:
        return f"The current time is {time.strftime('%I:%M %p (%Z)')}."

    if "date" in lower or "today's date" in lower:
        return f"Today is {time.strftime('%A, %B %d, %Y')}."

    if "what can you do" in lower or "help" in lower or "capabilities" in lower:
        return (
            "Here is what I can do for you on this laptop, Boss:\n"
            "• 🖥 System Diagnostics: CPU, RAM, battery, drives, and performance\n"
            "• 📱 Application Control: Launching and closing apps (Notepad, Chrome, VS Code, folders)\n"
            "• 📁 File Management: Searching files, reading documents, and file operations\n"
            "• 🌐 Web Assistant: Live search on DuckDuckGo and reading web pages\n"
            "• 🧠 Memory: Storing and retrieving your personal notes and tasks\n"
            "• 👨‍💻 Developer Assistant: Project scanner, code linting, and Git status\n"
            "• 🎙 Voice: Real-time speech synthesis and microphone transcription\n"
            "• 🌐 Multilingual: English, Telugu, and Hindi"
        )

    # ── FULL PC CONTROLS (OFFLINE FAST PATH) ────────────────────────────────
    vol_set = re.search(r"(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})", lower)
    if vol_set:
        return pc_ctrl.control_volume("set", int(vol_set.group(1)))
    if "volume up" in lower or "increase volume" in lower:
        return pc_ctrl.control_volume("up")
    if "volume down" in lower or "decrease volume" in lower:
        return pc_ctrl.control_volume("down")
    if "mute volume" in lower or "mute audio" in lower or lower == "mute":
        return pc_ctrl.control_volume("mute")
    if "unmute" in lower:
        return pc_ctrl.control_volume("unmute")

    bright_set = re.search(r"brightness\s+(?:to\s+)?(\d{1,3})", lower)
    if bright_set:
        return pc_ctrl.control_brightness(int(bright_set.group(1)))

    if "screenshot" in lower or "capture screen" in lower:
        return pc_ctrl.take_screenshot()

    if "minimize all" in lower or "show desktop" in lower:
        return pc_ctrl.control_window("minimize_all")
    if "switch window" in lower or "alt tab" in lower:
        return pc_ctrl.control_window("switch_window")
    if "lock pc" in lower or "lock screen" in lower or "lock my laptop" in lower:
        return pc_ctrl.system_power_action("lock")
    if "cancel shutdown" in lower or "abort shutdown" in lower:
        return pc_ctrl.system_power_action("cancel_shutdown")

    if "play pause" in lower or "pause music" in lower or "resume music" in lower or "pause video" in lower:
        return pc_ctrl.control_media("play_pause")
    if "next track" in lower or "next song" in lower:
        return pc_ctrl.control_media("next")
    if "previous track" in lower or "previous song" in lower:
        return pc_ctrl.control_media("previous")

    yt_match = re.search(r"(?:play|search)\s+(.+?)\s+on\s+youtube", lower)
    if yt_match:
        return pc_ctrl.open_url_or_search(yt_match.group(1), site="youtube")
    if lower in ("open youtube", "launch youtube"):
        return pc_ctrl.open_url_or_search("https://www.youtube.com")

    # ── APPLICATION & FOLDER LAUNCHING ───────────────────────────────────────
    open_match = re.search(r"^(?:open|launch|start|run|show)\s+(.+)$", lower)
    if open_match:
        target = open_match.group(1).replace("the", "").replace("app", "").strip()
        try:
            res = launch_app(target)
            return res
        except Exception as e:
            return f"Could not launch {target}: {e}"

    close_match = re.search(r"^(?:close|terminate|kill|stop|exit)\s+(.+)$", lower)
    if close_match:
        target = close_match.group(1).replace("the", "").replace("app", "").strip()
        try:
            res = terminate_app(target)
            return res
        except Exception as e:
            return f"Could not close {target}: {e}"

    if "list apps" in lower or "installed apps" in lower or "applications installed" in lower:
        apps = list_installed_apps()
        sample = [a["name"] for a in apps[:12]]
        return f"Found {len(apps)} installed applications on your laptop. Here are some of them:\n• " + "\n• ".join(sample)

    # ── SYSTEM MONITORING & TELEMETRY ────────────────────────────────────────
    if any(k in lower for k in ["tell me about my laptop", "system info", "laptop info", "specs", "system status", "my pc"]):
        info = get_system_summary()
        return (
            f"Here is your laptop's current status, Boss:\n"
            f"• Machine: {info.get('computer_name')} running Windows {info.get('windows_version')}\n"
            f"• Processor: {info.get('cpu_count_logical')} logical cores @ {info.get('cpu_usage_percent')}%\n"
            f"• Memory: {info.get('ram_used_gb')} GB used of {info.get('ram_total_gb')} GB ({info.get('ram_usage_percent')}%)\n"
            f"• Battery: {info.get('battery_percent')}% ({'Plugged in / Charging' if info.get('battery_plugged_in') else 'On Battery'})\n"
            f"• System Uptime: {info.get('uptime_human')}\n"
            f"All internal diagnostics report nominal operation."
        )

    if "ram" in lower or "memory usage" in lower:
        info = get_system_summary()
        return f"Current RAM usage: {info.get('ram_usage_percent')}% ({info.get('ram_used_gb')} GB used out of {info.get('ram_total_gb')} GB total)."

    if "cpu" in lower or "processor" in lower:
        info = get_system_summary()
        return f"Current CPU utilization is at {info.get('cpu_usage_percent')}% across {info.get('cpu_count_logical')} logical cores."

    if "battery" in lower or "charge" in lower:
        info = get_system_summary()
        charging = "Plugged in and charging" if info.get('battery_plugged_in') else "Discharging"
        return f"Battery is at {info.get('battery_percent')}% ({charging})."

    if "storage" in lower or "disk" in lower or "hard drive" in lower or "free space" in lower:
        info = get_system_summary()
        drives = info.get("drives", [])
        drive_strs = [f"{d.get('device')}: {d.get('free_gb')} GB free ({d.get('percent_used')}% used)" for d in drives]
        return "Storage status:\n" + ("\n".join(drive_strs) if drive_strs else "Storage details nominal.")

    if "is my laptop slow" in lower or "running slow" in lower or "performance" in lower:
        info = get_system_summary()
        cpu = info.get("cpu_usage_percent", 0)
        ram = info.get("ram_usage_percent", 0)
        if cpu > 80 or ram > 85:
            return f"Yes Boss, your laptop is under heavy load: CPU is at {cpu}% and RAM is at {ram}%. Consider closing resource-intensive background applications."
        return f"Negative Boss. Your laptop is operating smoothly. CPU is at {cpu}% and RAM is at {ram}%."

    # ── FILE SEARCH ──────────────────────────────────────────────────────────
    search_file_match = re.search(r"(?:search|find|look for)\s+(?:file|files)?\s*(.+)", lower)
    if search_file_match and "web" not in lower and "internet" not in lower:
        q = search_file_match.group(1).strip()
        results = search_files(query=q, max_depth=4)
        if results:
            preview = [os.path.basename(p) for p in results[:8]]
            return f"Found {len(results)} matching file(s) for '{q}':\n• " + "\n• ".join(preview)
        return f"No files matching '{q}' were found inside authorized folders."

    # ── WEB SEARCH ───────────────────────────────────────────────────────────
    web_match = re.search(r"(?:search\s+(?:the\s+)?web|google|duckduckgo|browse)\s+(?:for\s+)?(.+)", lower)
    if web_match:
        q = web_match.group(1).strip()
        res = web_search(q, max_results=3)
        if res and res[0].get("url"):
            formatted = [f"• {r['title']}: {r['snippet']}" for r in res]
            return f"Web search results for '{q}':\n" + "\n".join(formatted)
        return f"Search for '{q}' returned no immediate results."

    # ── NOTES & MEMORY ───────────────────────────────────────────────────────
    note_match = re.search(r"(?:note|remember|save note)\s*:\s*(.+)", lower) or re.search(r"(?:note|remember that)\s+(.+)", lower)
    if note_match:
        body = note_match.group(1).strip()
        nid = add_note(title=f"Note: {body[:25]}", body=body)
        return f"Saved to memory: '{body}' (Note #{nid})."

    if "my notes" in lower or "show notes" in lower or "list notes" in lower:
        notes = get_all_notes()
        if notes:
            items = [f"• #{n['id']} {n['title']}: {n['body'][:60]}" for n in notes[:6]]
            return "Here are your saved notes:\n" + "\n".join(items)
        return "You have no saved notes in memory."

    # ── DEFAULT NATURAL RESPONSE ─────────────────────────────────────────────
    if get_settings().is_api_key_configured:
        return (
            f"Understood, Boss. Regarding '{text}':\n"
            "The cloud AI model could not be reached right now (check internet/OpenRouter status), "
            "but all local PC control tools (apps, volume, brightness, files, diagnostics, shortcuts) remain ready."
        )
    return (
        f"Understood, Boss. Regarding '{text}':\n"
        "All local laptop tools (opening apps, volume, brightness, file search, diagnostics, web search, memory) are ready. "
        "For generative AI discussion, add your OpenRouter or OpenAI key via the '🔑 API KEY' button."
    )
