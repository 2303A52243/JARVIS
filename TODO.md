# JARVIS - Project TODO & Master Roadmap

## Phase 1: Foundation & Architecture Setup
- [x] Inspect workspace and Windows/Python runtime environment.
- [x] Configure `.gitignore`, `requirements.txt`, and `.env.example`.
- [x] Design modular directory structure and create package packages.
- [x] Implement robust Pydantic configuration (`app/config.py`).
- [x] Implement structured Audit Logger (`security/audit_logger.py`).
- [x] Implement Security & Permission Manager with allowlists (`core/permissions.py`).
- [x] Implement Pub/Sub Event Manager (`core/event_manager.py`).
- [x] Implement Application Startup & Diagnostics (`app/startup.py`).
- [ ] Build Dark-Themed PySide6 Desktop GUI Shell (`ui/main_window.py`).
- [ ] Create Phase 1 Unit Tests (`tests/test_config.py`, `tests/test_permissions.py`).
- [ ] Verify Phase 1 test suite.

## Phase 2: AI Brain & OpenAI Integration
- [ ] Implement OpenAI Client wrapper with configurable models (`ai/openai_client.py`).
- [ ] Implement Prompt templates & JARVIS persona (`ai/prompts.py`).
- [ ] Implement Response Handler with streaming token support (`ai/response_handler.py`).
- [ ] Implement Conversation History manager (`core/conversation.py`).
- [ ] Unit tests for AI client & prompt validation (`tests/test_ai.py`).

## Phase 3: Voice Interaction Engine (English, Telugu, Hindi)
- [ ] Implement Microphone capture and audio buffer (`voice/microphone.py`).
- [ ] Implement Speech-to-Text via Whisper API with language flags (`voice/speech_to_text.py`).
- [ ] Implement Text-to-Speech via OpenAI TTS & SAPI5 fallback (`voice/text_to_speech.py`).
- [ ] Implement Language Manager for English, Telugu, and Hindi (`voice/language_manager.py`).
- [ ] Implement Wake-Word activation interface (`voice/wake_word.py`).
- [ ] Implement Voice Controller & interruption handling.
- [ ] Unit tests for Voice components (`tests/test_voice.py`).

## Phase 4: Windows Laptop System & Application Control
- [ ] Implement System hardware inspection (CPU, RAM, Disk, Battery, GPU, OS) (`system/system_info.py`).
- [ ] Implement Running process monitor & safe termination (`system/process_manager.py`).
- [ ] Implement Windows application discovery from Registry & Start Menu (`system/application_manager.py`).
- [ ] Implement Safe application launch & window switching (`system/windows_integration.py`).
- [ ] Unit tests for system inspection & application discovery (`tests/test_system_info.py`, `tests/test_app_manager.py`).

## Phase 5: Secure File & Document Management
- [ ] Implement Configurable Folder Allowlist enforcement (`files/folder_permissions.py`).
- [ ] Implement File search by name, extension, and recency (`files/file_search.py`).
- [ ] Implement Local document parser (TXT, PDF, DOCX, CSV, XLSX, JSON, PY, MD) (`files/document_parser.py`).
- [ ] Implement Safe file operations (create, copy, move, rename, delete with dry-run) (`files/file_operations.py`).
- [ ] Implement Document summarization (`files/file_reader.py`).
- [ ] Unit tests for file operations & security boundaries (`tests/test_file_operations.py`).

## Phase 6: Developer Assistant & Git Integration
- [ ] Implement Project directory scanner and stack detector (Python, JS, React, FastAPI) (`developer/project_scanner.py`).
- [ ] Implement Code analyzer and syntax / error diagnostics (`developer/code_analyzer.py`).
- [ ] Implement Git manager (status, branch, commit history, diffs) (`developer/git_manager.py`).
- [ ] Unit tests for developer tools (`tests/test_developer.py`).

## Phase 7: Persistent Memory, Tool Calling & Workflow Engine
- [ ] Implement SQLite Persistent Storage schema & migrations (`memory/database.py`).
- [ ] Implement Long-term memory manager (preferences, facts, notes) (`memory/memory_manager.py`).
- [ ] Implement Tool Registry & function calling schemas (`core/tool_registry.py`).
- [ ] Implement Browser manager & safe web research (`browser/browser_manager.py`, `browser/web_search.py`).
- [ ] Implement Multi-step Task Planner & Executor with approval checks (`automation/task_planner.py`, `automation/task_executor.py`).
- [ ] Unit tests for memory, tools, and workflow execution (`tests/test_memory.py`, `tests/test_tool_registry.py`, `tests/test_workflow.py`).

## Phase 8: Comprehensive UI Integration, Packaging & Final Documentation
- [ ] Build Complete UI Panels: Dashboard, Chat, Voice, System Monitor, App Manager, File Manager, Project Assistant, Memory Manager, Settings.
- [ ] Integrate Real-Time System Monitoring graph & battery stats.
- [ ] Implement Interactive Permission & Confirmation Dialogs.
- [ ] Emergency Stop functionality across all background threads.
- [ ] Write Complete `README.md` with beginner-friendly PowerShell commands, setup guide, and PyInstaller instructions.
- [ ] Run full test suite and verify clean exit.
