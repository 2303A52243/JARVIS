"""Comprehensive Windows PC Control & Automation Tools for JARVIS.

Gives JARVIS full control over the Windows laptop when authorized:
- Audio Volume & Media Playback (Play/Pause/Next/Previous/Mute/Volume %)
- Screen Brightness & Desktop Screenshots
- Window Management (Minimize All, Switch, Close, Maximize, List, Focus)
- Keyboard Shortcuts, Unicode Typing, and Mouse Control
- System Power & Settings (Lock, Sleep, Display Off, Shutdown/Restart, Windows Settings)
- Browser URLs & YouTube/Google Direct Launch
- Clipboard Read/Write, Running Process Inspection/Termination, & PowerShell/CMD Execution
- Full PC Directory Listing, File Search, Read, Write, Copy, Move, and Delete
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import psutil
import win32api
import win32clipboard
import win32con
import win32gui

from app.config import get_settings
from core.permissions import PermissionLevel, get_permission_manager
from core.tool_registry import register_tool
from security.audit_logger import get_audit_logger


# Virtual-key table for shortcuts
_VK_MAP: Dict[str, int] = {
    "ctrl": win32con.VK_CONTROL,
    "control": win32con.VK_CONTROL,
    "alt": win32con.VK_MENU,
    "shift": win32con.VK_SHIFT,
    "win": win32con.VK_LWIN,
    "windows": win32con.VK_LWIN,
    "enter": win32con.VK_RETURN,
    "return": win32con.VK_RETURN,
    "esc": win32con.VK_ESCAPE,
    "escape": win32con.VK_ESCAPE,
    "tab": win32con.VK_TAB,
    "space": win32con.VK_SPACE,
    "backspace": win32con.VK_BACK,
    "delete": win32con.VK_DELETE,
    "del": win32con.VK_DELETE,
    "up": win32con.VK_UP,
    "down": win32con.VK_DOWN,
    "left": win32con.VK_LEFT,
    "right": win32con.VK_RIGHT,
    "home": win32con.VK_HOME,
    "end": win32con.VK_END,
    "pageup": win32con.VK_PRIOR,
    "pagedown": win32con.VK_NEXT,
    "prtsc": win32con.VK_SNAPSHOT,
    "printscreen": win32con.VK_SNAPSHOT,
    **{f"f{i}": getattr(win32con, f"VK_F{i}") for i in range(1, 13)},
}


def _check_perm(action: str, level: PermissionLevel, target: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
    pm = get_permission_manager()
    perm = pm.check_permission(action_name=action, level=level, target_resource=target, details=details or {})
    if not perm.allowed:
        raise PermissionError(f"Permission denied for '{action}': {perm.reason}")


def _tap_vk(vk_code: int, hold_sec: float = 0.01) -> None:
    win32api.keybd_event(vk_code, 0, 0, 0)
    time.sleep(hold_sec)
    win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)


# ── 1. Audio & Volume Control ───────────────────────────────────────────────

def control_volume(action: str, level: Optional[int] = None) -> str:
    """Control Windows master speaker volume ('up', 'down', 'mute', 'unmute', 'set')."""
    _check_perm("control_volume", PermissionLevel.CONTROL, details={"action": action, "level": level})
    act = action.lower().strip()

    if act == "mute" or act == "unmute" or act == "toggle_mute":
        _tap_vk(win32con.VK_VOLUME_MUTE)
        return "Toggled system audio mute."
    if act == "up":
        steps = max(1, min(25, (level or 10) // 2))
        for _ in range(steps):
            _tap_vk(win32con.VK_VOLUME_UP, 0.005)
        return f"Increased system volume by ~{steps * 2}%."
    if act == "down":
        steps = max(1, min(25, (level or 10) // 2))
        for _ in range(steps):
            _tap_vk(win32con.VK_VOLUME_DOWN, 0.005)
        return f"Decreased system volume by ~{steps * 2}%."
    if act == "set" and level is not None:
        pct = max(0, min(100, int(level)))
        for _ in range(50):
            _tap_vk(win32con.VK_VOLUME_DOWN, 0.002)
        for _ in range(pct // 2):
            _tap_vk(win32con.VK_VOLUME_UP, 0.002)
        return f"System volume set to {pct}%."
    return f"Unknown volume action '{action}'. Use up, down, mute, or set with level 0-100."


def control_media(action: str) -> str:
    """Control media playback ('play_pause', 'next', 'previous', 'stop')."""
    _check_perm("control_media", PermissionLevel.CONTROL, details={"action": action})
    act = action.lower().strip()
    mapping = {
        "play": win32con.VK_MEDIA_PLAY_PAUSE,
        "pause": win32con.VK_MEDIA_PLAY_PAUSE,
        "play_pause": win32con.VK_MEDIA_PLAY_PAUSE,
        "next": win32con.VK_MEDIA_NEXT_TRACK,
        "previous": win32con.VK_MEDIA_PREV_TRACK,
        "prev": win32con.VK_MEDIA_PREV_TRACK,
        "stop": win32con.VK_MEDIA_STOP,
    }
    vk = mapping.get(act)
    if not vk:
        return f"Unsupported media action: {action}"
    _tap_vk(vk)
    return f"Executed media command: {act}."


# ── 2. Screen Brightness & Screenshot ───────────────────────────────────────

def control_brightness(level: int) -> str:
    """Set laptop display brightness (0 to 100)."""
    _check_perm("control_brightness", PermissionLevel.CONTROL, details={"level": level})
    pct = max(0, min(100, int(level)))
    cmd = (
        f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
        f".WmiSetBrightness(1, {pct})"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True,
        text=True,
        timeout=8,
    )
    if proc.returncode != 0:
        return f"Brightness adjustment not supported or failed: {proc.stderr.strip()}"
    return f"Display brightness set to {pct}%."


def take_screenshot(filename: Optional[str] = None) -> str:
    """Capture a full-screen screenshot and save it to Pictures/Screenshots."""
    _check_perm("take_screenshot", PermissionLevel.CONTROL, details={"filename": filename})
    shots_dir = Path.home() / "Pictures" / "Screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    name = filename.strip() if filename else f"JARVIS_{time.strftime('%Y%m%d_%H%M%S')}.png"
    if not name.lower().endswith(".png"):
        name += ".png"
    out_path = shots_dir / name

    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
        "$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen; "
        "$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height; "
        "$gfx = [System.Drawing.Graphics]::FromImage($bmp); "
        "$gfx.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size); "
        f"$bmp.Save('{str(out_path)}', [System.Drawing.Imaging.ImageFormat]::Png); "
        "$gfx.Dispose(); $bmp.Dispose()"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"Screenshot failed: {proc.stderr.strip()}")
    return f"Screenshot captured and saved to: {out_path}"


# ── 3. Window Management ────────────────────────────────────────────────────

def _enum_visible_windows() -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            if title:
                results.append({"hwnd": hwnd, "title": title})

    win32gui.EnumWindows(_cb, None)
    return results


def control_window(action: str, window_title: Optional[str] = None) -> str:
    """Control open Windows desktop windows."""
    _check_perm("control_window", PermissionLevel.CONTROL, details={"action": action, "window_title": window_title})
    act = action.lower().strip()

    if act in ("minimize_all", "show_desktop"):
        send_keyboard_shortcut("win+d")
        return "Minimized all windows (Show Desktop)."
    if act == "switch_window":
        send_keyboard_shortcut("alt+tab")
        return "Switched to next window."
    if act == "close_active":
        send_keyboard_shortcut("alt+f4")
        return "Sent close command (Alt+F4) to active window."
    if act == "maximize_active":
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return "Maximized active window."
    if act == "minimize_active":
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return "Minimized active window."
    if act == "list_windows":
        wins = _enum_visible_windows()
        titles = [w["title"] for w in wins[:20]]
        return "Open windows:\n• " + "\n• ".join(titles) if titles else "No visible titled windows found."
    if act == "focus_window" and window_title:
        wins = _enum_visible_windows()
        q = window_title.lower().strip()
        for w in wins:
            if q in w["title"].lower():
                hwnd = w["hwnd"]
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                return f"Focused window: {w['title']}"
        return f"No open window matching '{window_title}'."

    return f"Unsupported window action '{action}'."


# ── 4. Keyboard & Mouse Automation ──────────────────────────────────────────

def send_keyboard_shortcut(keys: str) -> str:
    """Press a keyboard key or shortcut combination (e.g. 'ctrl+c', 'win+e', 'alt+tab')."""
    _check_perm("send_keyboard_shortcut", PermissionLevel.CONTROL, details={"keys": keys})
    parts = [p.strip().lower() for p in keys.split("+") if p.strip()]
    if not parts:
        return "No keys specified."

    vks: List[int] = []
    for part in parts:
        if part in _VK_MAP:
            vks.append(_VK_MAP[part])
        elif len(part) == 1:
            vks.append(ord(part.upper()))
        else:
            raise ValueError(f"Unknown key token: '{part}'")

    for vk in vks:
        win32api.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
    for vk in reversed(vks):
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.01)

    return f"Pressed keyboard shortcut: {keys}"


def type_text(text: str, press_enter: bool = False) -> str:
    """Type Unicode text into the currently focused application."""
    _check_perm("type_text", PermissionLevel.CONTROL, details={"length": len(text), "press_enter": press_enter})

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT(ctypes.Structure):
        class _I(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]
        _anonymous_ = ("i",)
        _fields_ = [("type", ctypes.c_ulong), ("i", _I)]

    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_KEYUP = 0x0002
    INPUT_KEYBOARD = 1

    for ch in text:
        code = ord(ch)
        down = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, None))
        up = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None))
        ctypes.windll.user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
        ctypes.windll.user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
        time.sleep(0.005)

    if press_enter:
        _tap_vk(win32con.VK_RETURN)

    return f"Typed {len(text)} character(s)."


def mouse_control(action: str, x: Optional[int] = None, y: Optional[int] = None, amount: int = 3) -> str:
    """Control mouse pointer position, clicks, or scroll wheel."""
    _check_perm("mouse_control", PermissionLevel.CONTROL, details={"action": action, "x": x, "y": y})
    act = action.lower().strip()

    if x is not None and y is not None:
        win32api.SetCursorPos((int(x), int(y)))

    cx, cy = win32api.GetCursorPos()
    if act == "move":
        return f"Moved cursor to ({cx}, {cy})."
    if act == "click":
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, cx, cy, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, cx, cy, 0, 0)
        return f"Left-clicked at ({cx}, {cy})."
    if act == "double_click":
        for _ in range(2):
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, cx, cy, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, cx, cy, 0, 0)
            time.sleep(0.05)
        return f"Double-clicked at ({cx}, {cy})."
    if act == "right_click":
        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, cx, cy, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, cx, cy, 0, 0)
        return f"Right-clicked at ({cx}, {cy})."
    if act == "scroll_up":
        win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, cx, cy, int(amount) * 120, 0)
        return f"Scrolled up ({amount} notches)."
    if act == "scroll_down":
        win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, cx, cy, -int(amount) * 120, 0)
        return f"Scrolled down ({amount} notches)."
    return f"Unsupported mouse action: {action}"


# ── 5. Power, Settings, Browser, Clipboard & Processes ──────────────────────

def system_power_action(action: str) -> str:
    """Execute Windows power/session command ('lock', 'sleep', 'display_off', 'restart', 'shutdown', 'cancel_shutdown')."""
    _check_perm("system_power_action", PermissionLevel.ADVANCED, details={"action": action})
    act = action.lower().strip()
    if act == "lock":
        ctypes.windll.user32.LockWorkStation()
        return "Workstation locked."
    if act == "display_off":
        # HWND_BROADCAST = 0xFFFF, WM_SYSCOMMAND = 0x0112, SC_MONITORPOWER = 0xF170, 2 = Power off
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x0112, 0xF170, 2, 2, 1000, None)
        return "Turned off display monitor."
    if act == "sleep":
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        return "Putting PC to sleep."
    if act == "restart":
        subprocess.run(["shutdown", "/r", "/t", "10"], check=False)
        return "PC restart scheduled in 10 seconds (say 'cancel shutdown' to abort)."
    if act == "shutdown":
        subprocess.run(["shutdown", "/s", "/t", "10"], check=False)
        return "PC shutdown scheduled in 10 seconds (say 'cancel shutdown' to abort)."
    if act == "cancel_shutdown":
        subprocess.run(["shutdown", "/a"], check=False)
        return "Cancelled scheduled shutdown/restart."
    return f"Unsupported power action: {action}"


def open_url_or_search(url_or_query: str, site: str = "auto") -> str:
    """Open a website URL or search YouTube / Google directly in the default browser."""
    _check_perm("open_url_or_search", PermissionLevel.CONTROL, target=url_or_query)
    q = url_or_query.strip()
    s = site.lower().strip()

    if s == "youtube":
        url = f"https://www.youtube.com/results?search_query={quote_plus(q)}"
    elif s == "google":
        url = f"https://www.google.com/search?q={quote_plus(q)}"
    elif q.startswith(("http://", "https://")):
        url = q
    elif "." in q and " " not in q:
        url = f"https://{q}"
    else:
        url = f"https://www.google.com/search?q={quote_plus(q)}"

    webbrowser.open(url)
    return f"Opened in browser: {url}"


def open_windows_settings(page: str = "") -> str:
    """Open Windows Settings page (wifi, bluetooth, display, sound, battery, updates, apps, storage)."""
    _check_perm("open_windows_settings", PermissionLevel.CONTROL, target=page)
    uri_map = {
        "wifi": "ms-settings:network-wifi",
        "network": "ms-settings:network-status",
        "bluetooth": "ms-settings:bluetooth",
        "display": "ms-settings:display",
        "sound": "ms-settings:sound",
        "audio": "ms-settings:sound",
        "battery": "ms-settings:batterysaver",
        "updates": "ms-settings:windowsupdate",
        "update": "ms-settings:windowsupdate",
        "apps": "ms-settings:appsfeatures",
        "storage": "ms-settings:storagesense",
        "privacy": "ms-settings:privacy",
    }
    uri = uri_map.get(page.lower().strip(), "ms-settings:")
    os.startfile(uri)  # noqa: S606
    return f"Opened Windows Settings ({uri})."


def clipboard_control(action: str, text: Optional[str] = None) -> str:
    """Get or set Windows clipboard text."""
    _check_perm("clipboard_control", PermissionLevel.CONTROL, details={"action": action})
    act = action.lower().strip()
    win32clipboard.OpenClipboard()
    try:
        if act == "set" and text is not None:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
            return f"Copied text to clipboard ({len(text)} chars)."
        if act == "get":
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                return f"Clipboard content:\n{data}"
            return "Clipboard has no text content."
    finally:
        win32clipboard.CloseClipboard()
    return "Specify action 'get' or 'set' with text."


def list_running_processes(limit: int = 15) -> str:
    """List top running processes on the PC by memory usage."""
    _check_perm("list_running_processes", PermissionLevel.READ)
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            mem_mb = (p.info["memory_info"].rss or 0) / (1024 * 1024)
            procs.append((mem_mb, p.info["pid"], p.info["name"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(reverse=True)
    lines = [f"• {name} (PID {pid}): {mem:.1f} MB" for mem, pid, name in procs[:limit]]
    return "Top running processes:\n" + "\n".join(lines)


def run_pc_command(command: str, shell_type: str = "powershell") -> str:
    """Execute a Windows PowerShell or CMD command when Full PC Access is enabled."""
    settings = get_settings()
    if not settings.jarvis_full_pc_access:
        raise PermissionError("Full PC Access is disabled in settings (JARVIS_FULL_PC_ACCESS=false).")

    _check_perm("run_pc_command", PermissionLevel.CONTROL, target=command[:120], details={"shell": shell_type})
    logger = get_audit_logger()
    logger.info(f"Executing PC command ({shell_type}): {command}")

    if shell_type.lower().strip() == "cmd":
        args = ["cmd.exe", "/c", command]
    else:
        args = ["powershell", "-NoProfile", "-Command", command]

    proc = subprocess.run(args, capture_output=True, text=True, timeout=20)
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    combined = "\n".join(x for x in [out, f"STDERR: {err}" if err else ""] if x)
    if not combined:
        return f"Command completed (exit code {proc.returncode})."
    return combined[:3000]


# ── 6. Full PC File & System Helper Wrappers ────────────────────────────────

def list_directory(path: str) -> str:
    """List files and folders inside a directory path on the PC."""
    _check_perm("list_directory", PermissionLevel.READ, target=path)
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"Directory does not exist: {p}"
    entries = []
    for item in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:60]:
        tag = "[DIR]" if item.is_dir() else f"[{item.stat().st_size} B]"
        entries.append(f"{tag} {item.name}")
    return f"Contents of {p}:\n" + ("\n".join(entries) if entries else "(empty)")


def _register_all_pc_tools() -> None:
    """Register all PC control, file, web, and memory tools in the global ToolRegistry."""

    register_tool(
        name="control_volume",
        func=lambda a: control_volume(a["action"], a.get("level")),
        spec={
            "name": "control_volume",
            "description": "Control laptop speaker volume: up, down, mute, unmute, or set exact percentage 0-100.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["up", "down", "mute", "unmute", "set"]},
                    "level": {"type": "integer", "description": "Volume percentage 0-100 (for 'set') or step delta."},
                },
                "required": ["action"],
            },
        },
        level=PermissionLevel.CONTROL,
    )

    register_tool(
        name="control_media",
        func=lambda a: control_media(a["action"]),
        spec={
            "name": "control_media",
            "description": "Control active media/music/video playback (play_pause, next, previous, stop).",
            "parameters": {
                "type": "object",
                "properties": {"action": {"type": "string", "enum": ["play_pause", "next", "previous", "stop"]}},
                "required": ["action"],
            },
        },
        level=PermissionLevel.CONTROL,
    )

    register_tool(
        name="control_brightness",
        func=lambda a: control_brightness(a["level"]),
        spec={
            "name": "control_brightness",
            "description": "Set laptop screen brightness from 0 to 100.",
            "parameters": {
                "type": "object",
                "properties": {"level": {"type": "integer", "description": "Brightness percentage 0-100."}},
                "required": ["level"],
            },
        },
        level=PermissionLevel.CONTROL,
    )

    register_tool(
        name="take_screenshot",
        func=lambda a: take_screenshot(a.get("filename")),
        spec={
            "name": "take_screenshot",
            "description": "Take a screenshot of the PC screen and save it to Pictures/Screenshots.",
            "parameters": {
                "type": "object",
                "properties": {"filename": {"type": "string", "description": "Optional filename."}},
                "required": [],
            },
        },
        level=PermissionLevel.CONTROL,
    )

    register_tool(
        name="control_window",
        func=lambda a: control_window(a["action"], a.get("window_title")),
        spec={
            "name": "control_window",
            "description": "Manage desktop windows: minimize_all, show_desktop, switch_window, close_active, maximize_active, minimize_active, list_windows, focus_window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "minimize_all", "show_desktop", "switch_window",
                            "close_active", "maximize_active", "minimize_active",
                            "list_windows", "focus_window",
                        ],
                    },
                    "window_title": {"type": "string", "description": "Title substring for focus_window."},
                },
                "required": ["action"],
            },
        },
        level=PermissionLevel.CONTROL,
    )

    register_tool(
        name="send_keyboard_shortcut",
        func=lambda a: send_keyboard_shortcut(a["keys"]),
        spec={
            "name": "send_keyboard_shortcut",
            "description": "Send keyboard shortcut or key press (e.g. 'ctrl+c', 'ctrl+v', 'win+e', 'alt+f4', 'enter').",
            "parameters": {
                "type": "object",
                "properties": {"keys": {"type": "string"}},
                "required": ["keys"],
            },
        },
        level=PermissionLevel.CONTROL,
    )

    register_tool(
        name="type_text",
        func=lambda a: type_text(a["text"], bool(a.get("press_enter", False))),
        spec={
            "name": "type_text",
            "description": "Type text directly into the active window (supports English, Telugu, Hindi).",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "press_enter": {"type": "boolean"},
                },
                "required": ["text"],
            },
        },
        level=PermissionLevel.CONTROL,
    )

    register_tool(
        name="mouse_control",
        func=lambda a: mouse_control(a["action"], a.get("x"), a.get("y"), a.get("amount", 3)),
        spec={
            "name": "mouse_control",
            "description": "Move mouse cursor, click, double_click, right_click, scroll_up, or scroll_down.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["move", "click", "double_click", "right_click", "scroll_up", "scroll_down"]},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "amount": {"type": "integer"},
                },
                "required": ["action"],
            },
        },
        level=PermissionLevel.CONTROL,
    )

    register_tool(
        name="system_power_action",
        func=lambda a: system_power_action(a["action"]),
        spec={
            "name": "system_power_action",
            "description": "Control PC power state: lock, sleep, display_off, restart, shutdown, cancel_shutdown.",
            "parameters": {
                "type": "object",
                "properties": {"action": {"type": "string", "enum": ["lock", "sleep", "display_off", "restart", "shutdown", "cancel_shutdown"]}},
                "required": ["action"],
            },
        },
        level=PermissionLevel.ADVANCED,
    )

    register_tool(
        name="open_url_or_search",
        func=lambda a: open_url_or_search(a["url_or_query"], a.get("site", "auto")),
        spec={
            "name": "open_url_or_search",
            "description": "Open a URL in the browser or search YouTube / Google directly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url_or_query": {"type": "string"},
                    "site": {"type": "string", "enum": ["auto", "youtube", "google"]},
                },
                "required": ["url_or_query"],
            },
        },
        level=PermissionLevel.CONTROL,
    )

    register_tool(
        name="open_windows_settings",
        func=lambda a: open_windows_settings(a.get("page", "")),
        spec={
            "name": "open_windows_settings",
            "description": "Open a Windows Settings page (wifi, bluetooth, display, sound, battery, updates, apps, storage).",
            "parameters": {
                "type": "object",
                "properties": {"page": {"type": "string"}},
                "required": [],
            },
        },
        level=PermissionLevel.CONTROL,
    )

    register_tool(
        name="clipboard_control",
        func=lambda a: clipboard_control(a["action"], a.get("text")),
        spec={
            "name": "clipboard_control",
            "description": "Read ('get') or copy ('set') text on the Windows clipboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["get", "set"]},
                    "text": {"type": "string"},
                },
                "required": ["action"],
            },
        },
        level=PermissionLevel.CONTROL,
    )

    register_tool(
        name="list_running_processes",
        func=lambda a: list_running_processes(a.get("limit", 15)),
        spec={
            "name": "list_running_processes",
            "description": "List top running processes on the PC with PID and RAM usage.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
                "required": [],
            },
        },
        level=PermissionLevel.READ,
    )

    register_tool(
        name="run_pc_command",
        func=lambda a: run_pc_command(a["command"], a.get("shell_type", "powershell")),
        spec={
            "name": "run_pc_command",
            "description": "Execute a PowerShell or CMD command on the PC to inspect or automate anything in Windows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "PowerShell or CMD command to execute."},
                    "shell_type": {"type": "string", "enum": ["powershell", "cmd"]},
                },
                "required": ["command"],
            },
        },
        level=PermissionLevel.CONTROL,
    )

    register_tool(
        name="get_system_status",
        func=lambda _: __import__("system.system_info", fromlist=["get_system_summary"]).get_system_summary(),
        spec={
            "name": "get_system_status",
            "description": "Get live PC CPU, RAM, disk drives, battery, OS, and uptime telemetry.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        level=PermissionLevel.READ,
    )

    register_tool(
        name="list_directory",
        func=lambda a: list_directory(a["path"]),
        spec={
            "name": "list_directory",
            "description": "List files and subdirectories in any folder on the PC (e.g. Desktop, Downloads, C:\\).",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
        level=PermissionLevel.READ,
    )

    register_tool(
        name="search_files_pc",
        func=lambda a: __import__("files.file_search", fromlist=["search_files"]).search_files(
            query=a.get("query", ""), max_depth=a.get("max_depth", 4)
        ),
        spec={
            "name": "search_files_pc",
            "description": "Search for files across authorized folders and drives on the PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_depth": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
        level=PermissionLevel.READ,
    )

    register_tool(
        name="read_file_pc",
        func=lambda a: __import__("files.document_parser", fromlist=["parse_document"]).parse_document(a["path"]),
        spec={
            "name": "read_file_pc",
            "description": "Read text/content from a file or document (txt, py, md, pdf, docx, csv) on the PC.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
        level=PermissionLevel.READ,
    )

    register_tool(
        name="create_file_pc",
        func=lambda a: __import__("files.file_operations", fromlist=["create_file"]).create_file(
            a["path"], a.get("content", ""), bool(a.get("overwrite", False))
        ),
        spec={
            "name": "create_file_pc",
            "description": "Create or write a file at an absolute path on the PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "overwrite": {"type": "boolean"},
                },
                "required": ["path"],
            },
        },
        level=PermissionLevel.CONTROL,
    )

    register_tool(
        name="manage_file_pc",
        func=lambda a: (
            __import__("files.file_operations", fromlist=["copy_file"]).copy_file(a["src"], a["dest"])
            if a["action"] == "copy"
            else (
                __import__("files.file_operations", fromlist=["move_file"]).move_file(a["src"], a["dest"])
                if a["action"] in ("move", "rename")
                else __import__("files.file_operations", fromlist=["delete_file"]).delete_file(a["src"])
            )
        ),
        spec={
            "name": "manage_file_pc",
            "description": "Copy, move, rename, or delete a file on the PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["copy", "move", "rename", "delete"]},
                    "src": {"type": "string"},
                    "dest": {"type": "string"},
                },
                "required": ["action", "src"],
            },
        },
        level=PermissionLevel.ADVANCED,
    )

    register_tool(
        name="web_search_live",
        func=lambda a: __import__("browser.web_search", fromlist=["web_search"]).web_search(
            a["query"], a.get("max_results", 4)
        ),
        spec={
            "name": "web_search_live",
            "description": "Search the internet live via DuckDuckGo and return titles, URLs, and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
        level=PermissionLevel.READ,
    )


_register_all_pc_tools()
