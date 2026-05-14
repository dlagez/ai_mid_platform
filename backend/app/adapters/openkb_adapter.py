from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import yaml

from app.adapters.base_adapter import BaseAdapter
from app.utils.exceptions import PlatformError


DEFAULT_AGENTS_MD = """# Wiki Schema

## Directory Structure

- sources/ - Document content. Short docs as .md, long docs as .json.
- sources/images/ - Extracted images from documents, referenced by sources.
- summaries/ - One per source document.
- concepts/ - Cross-document topic synthesis.
- explorations/ - Saved query results.
- reports/ - Lint health check reports.

## Special Files

- index.md - Content catalog.
- log.md - Chronological append-only operation log.
"""

OPENKB_COMMANDS = [
    {"command": "/help", "description": "List available commands"},
    {"command": "/status", "description": "Show knowledge base status"},
    {"command": "/list", "description": "List all documents"},
    {"command": "/add <path>", "description": "Add a document or directory without leaving the chat"},
    {"command": "/save [name]", "description": "Export the transcript to wiki/explorations/"},
    {"command": "/clear", "description": "Start a fresh session; the current one stays on disk"},
    {"command": "/lint", "description": "Run knowledge base lint"},
    {"command": "/exit", "description": "Exit the chat session"},
]


class OpenKBAdapter(BaseAdapter):
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name, config)
        self.kb_root = Path(config.get("kb_root", "storage/openkb")).expanduser()
        self.default_kb = config.get("default_kb", "default")
        self.model = config.get("model", "qwen3.6-plus")
        self.language = config.get("language", "en")
        self.pageindex_threshold = int(config.get("pageindex_threshold", 20))
        self._configure_llm_env(config)

    async def call(self, payload: dict[str, Any]) -> dict[str, Any]:
        operation = payload.get("operation")
        if operation == "query":
            return await self.query(**payload["params"])
        if operation == "chat":
            return await self.chat(**payload["params"])
        if operation == "add":
            return await self.add(**payload["params"])
        if operation == "list":
            return self.list(**payload.get("params", {}))
        if operation == "status":
            return self.status(**payload.get("params", {}))
        if operation == "help":
            return self.help()
        if operation == "save":
            return self.save_transcript(**payload["params"])
        if operation == "clear":
            return self.clear_session(**payload.get("params", {}))
        if operation == "lint":
            return await self.lint(**payload.get("params", {}))
        if operation == "exit":
            return self.exit_session(**payload.get("params", {}))
        raise PlatformError(f"Unsupported OpenKB operation: {operation}", status_code=400)

    def help(self) -> dict[str, Any]:
        return {"commands": OPENKB_COMMANDS}

    async def query(self, question: str, kb_name: str | None = None, save: bool = False) -> dict[str, Any]:
        from openkb.agent.query import run_query
        from openkb.config import load_config
        from openkb.log import append_log

        kb_dir = self._ensure_kb(kb_name)
        config = load_config(kb_dir / ".openkb" / "config.yaml")
        answer = await run_query(
            question=question,
            kb_dir=kb_dir,
            model=config.get("model", self.model),
            stream=False,
            raw=False,
        )
        append_log(kb_dir / "wiki", "query", question)
        saved_path = self._save_query_result(kb_dir, question, answer) if save else None
        return {
            "kb_name": kb_dir.name,
            "question": question,
            "answer": answer,
            "saved_path": str(saved_path) if saved_path else None,
        }

    async def chat(
        self,
        message: str,
        kb_name: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        from agents import Runner
        from openkb.agent.chat_session import ChatSession, load_session, resolve_session_id
        from openkb.agent.query import MAX_TURNS, build_query_agent
        from openkb.config import load_config
        from openkb.log import append_log

        kb_dir = self._ensure_kb(kb_name)
        config = load_config(kb_dir / ".openkb" / "config.yaml")
        model = config.get("model", self.model)
        language = config.get("language", self.language)

        if session_id:
            resolved = resolve_session_id(kb_dir, session_id)
            if not resolved:
                raise PlatformError(f"OpenKB chat session not found: {session_id}", status_code=404)
            session = load_session(kb_dir, resolved)
        else:
            session = ChatSession.new(kb_dir, model, language)

        agent = build_query_agent(str(kb_dir / "wiki"), session.model, language=session.language)
        result = await Runner.run(
            agent,
            session.history + [{"role": "user", "content": message}],
            max_turns=MAX_TURNS,
        )
        answer = result.final_output or ""
        session.record_turn(message, answer, result.to_input_list())
        append_log(kb_dir / "wiki", "query", message)
        return {
            "kb_name": kb_dir.name,
            "session_id": session.id,
            "message": message,
            "answer": answer,
            "turn_count": session.turn_count,
        }

    async def add(self, path: str, kb_name: str | None = None) -> dict[str, Any]:
        from openkb.cli import SUPPORTED_EXTENSIONS, add_single_file

        kb_dir = self._ensure_kb(kb_name)
        target = Path(path).expanduser()
        if not target.is_absolute():
            target = (kb_dir / target).resolve()
        if not target.exists():
            raise PlatformError(f"OpenKB add path does not exist: {path}", status_code=404)

        added: list[str] = []
        skipped: list[str] = []

        if target.is_dir():
            files = [
                item
                for item in sorted(target.rglob("*"))
                if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS
            ]
        elif target.suffix.lower() in SUPPORTED_EXTENSIONS:
            files = [target]
        else:
            raise PlatformError(f"Unsupported OpenKB document type: {target.suffix}", status_code=400)

        for file_path in files:
            before_names = {
                str(meta.get("name"))
                for meta in self._read_hashes(kb_dir).values()
                if meta.get("name")
            }
            try:
                await asyncio.to_thread(add_single_file, file_path, kb_dir)
            except Exception as exc:
                skipped.append(f"{file_path}: {exc}")
                continue

            after_names = {
                str(meta.get("name"))
                for meta in self._read_hashes(kb_dir).values()
                if meta.get("name")
            }
            if file_path.name in after_names and file_path.name not in before_names:
                added.append(str(file_path))
            else:
                skipped.append(f"{file_path}: already indexed or no new hash registered")

        return {"kb_name": kb_dir.name, "added": added, "skipped": skipped}

    def list(self, kb_name: str | None = None) -> dict[str, Any]:
        kb_dir = self._ensure_kb(kb_name)
        hashes = self._read_hashes(kb_dir)
        return {
            "kb_name": kb_dir.name,
            "documents": [
                {
                    "hash": file_hash,
                    "name": meta.get("name", "unknown"),
                    "type": self._display_type(meta.get("type", "unknown")),
                    "pages": meta.get("pages"),
                }
                for file_hash, meta in hashes.items()
            ],
            "summaries": self._markdown_stems(kb_dir / "wiki" / "summaries"),
            "concepts": self._markdown_stems(kb_dir / "wiki" / "concepts"),
            "reports": self._markdown_names(kb_dir / "wiki" / "reports"),
        }

    def status(self, kb_name: str | None = None) -> dict[str, Any]:
        kb_dir = self._ensure_kb(kb_name)
        wiki_dir = kb_dir / "wiki"
        hashes = self._read_hashes(kb_dir)
        directories = {
            subdir: self._markdown_count(wiki_dir / subdir)
            for subdir in ("sources", "summaries", "concepts", "reports")
        }
        raw_dir = kb_dir / "raw"
        directories["raw"] = len([item for item in raw_dir.iterdir() if item.is_file()]) if raw_dir.exists() else 0
        return {
            "kb_name": kb_dir.name,
            "kb_dir": str(kb_dir),
            "model": self.model,
            "language": self.language,
            "directories": directories,
            "total_indexed": len(hashes),
            "last_compile": self._newest_mtime(wiki_dir / "summaries"),
            "last_lint": self._newest_mtime(wiki_dir / "reports"),
        }

    def save_upload(self, filename: str, content: bytes, kb_name: str | None = None) -> Path:
        kb_dir = self._ensure_kb(kb_name)
        safe_name = Path(filename).name or "document"
        destination = kb_dir / "raw" / safe_name
        destination.write_bytes(content)
        return destination

    def clear_session(self, kb_name: str | None = None, previous_session_id: str | None = None) -> dict[str, Any]:
        from openkb.agent.chat_session import ChatSession
        from openkb.config import load_config

        kb_dir = self._ensure_kb(kb_name)
        config = load_config(kb_dir / ".openkb" / "config.yaml")
        session = ChatSession.new(
            kb_dir,
            config.get("model", self.model),
            config.get("language", self.language),
        )
        session.save()
        return {
            "kb_name": kb_dir.name,
            "previous_session_id": previous_session_id,
            "session_id": session.id,
            "message": "Started a fresh OpenKB session.",
        }

    def save_transcript(
        self,
        session_id: str,
        kb_name: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        from openkb.agent.chat import _save_transcript
        from openkb.agent.chat_session import load_session, resolve_session_id

        kb_dir = self._ensure_kb(kb_name)
        resolved = resolve_session_id(kb_dir, session_id)
        if not resolved:
            raise PlatformError(f"OpenKB chat session not found: {session_id}", status_code=404)
        session = load_session(kb_dir, resolved)
        if not session.user_turns:
            raise PlatformError("Nothing to save yet.", status_code=400)
        path = _save_transcript(kb_dir, session, name)
        return {
            "kb_name": kb_dir.name,
            "session_id": session.id,
            "saved_path": str(path),
            "message": f"Saved transcript to {path}",
        }

    async def lint(self, kb_name: str | None = None) -> dict[str, Any]:
        from openkb.cli import run_lint

        kb_dir = self._ensure_kb(kb_name)
        report_path = await run_lint(kb_dir)
        return {
            "kb_name": kb_dir.name,
            "report_path": str(report_path) if report_path else None,
            "message": "Lint completed." if report_path else "Nothing to lint.",
        }

    def exit_session(self, kb_name: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        kb_dir = self._ensure_kb(kb_name)
        return {
            "kb_name": kb_dir.name,
            "session_id": session_id,
            "closed": True,
            "message": "Exited OpenKB chat session.",
        }

    def _configure_llm_env(self, config: dict[str, Any]) -> None:
        api_key = config.get("llm_api_key") or os.environ.get("LLM_API_KEY") or os.environ.get("BAILIAN_API_KEY")
        if api_key and not os.environ.get("LLM_API_KEY"):
            os.environ["LLM_API_KEY"] = str(api_key)
        if api_key and not os.environ.get("DASHSCOPE_API_KEY"):
            os.environ["DASHSCOPE_API_KEY"] = str(api_key)
        if os.environ.get("LLM_API_KEY"):
            for env_var in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
                os.environ.setdefault(env_var, os.environ["LLM_API_KEY"])

    def initialize_default_kb(self) -> Path:
        return self._ensure_kb(self.default_kb)

    def _ensure_kb(self, kb_name: str | None = None) -> Path:
        name = kb_name or self.default_kb
        if not name.replace("_", "-").replace("-", "").isalnum():
            raise PlatformError("KB name may only contain letters, numbers, hyphens, and underscores", 400)

        kb_dir = (self.kb_root / name).resolve()
        openkb_dir = kb_dir / ".openkb"

        (kb_dir / "raw").mkdir(parents=True, exist_ok=True)
        (kb_dir / "wiki" / "sources" / "images").mkdir(parents=True, exist_ok=True)
        (kb_dir / "wiki" / "summaries").mkdir(parents=True, exist_ok=True)
        (kb_dir / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
        (kb_dir / "wiki" / "explorations").mkdir(parents=True, exist_ok=True)
        (kb_dir / "wiki" / "reports").mkdir(parents=True, exist_ok=True)
        openkb_dir.mkdir(parents=True, exist_ok=True)

        self._write_file_if_missing(kb_dir / "wiki" / "AGENTS.md", DEFAULT_AGENTS_MD)
        self._write_file_if_missing(
            kb_dir / "wiki" / "index.md",
            "# Knowledge Base Index\n\n## Documents\n\n## Concepts\n\n## Explorations\n",
        )
        self._write_file_if_missing(kb_dir / "wiki" / "log.md", "# Operations Log\n\n")
        self._sync_openkb_config(openkb_dir / "config.yaml")
        self._write_file_if_missing(openkb_dir / "hashes.json", json.dumps({}))
        return kb_dir

    def _write_file_if_missing(self, path: Path, content: str) -> None:
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    def _write_yaml_if_missing(self, path: Path, content: dict[str, Any]) -> None:
        if not path.exists():
            path.write_text(yaml.safe_dump(content, allow_unicode=True, sort_keys=True), encoding="utf-8")

    def _sync_openkb_config(self, path: Path) -> None:
        existing = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
        desired = {
            **(existing or {}),
            "model": self.model,
            "language": self.language,
            "pageindex_threshold": self.pageindex_threshold,
        }
        if desired != existing:
            path.write_text(yaml.safe_dump(desired, allow_unicode=True, sort_keys=True), encoding="utf-8")

    def _read_hashes(self, kb_dir: Path) -> dict[str, dict[str, Any]]:
        hashes_file = kb_dir / ".openkb" / "hashes.json"
        if not hashes_file.exists():
            return {}
        return json.loads(hashes_file.read_text(encoding="utf-8"))

    def _save_query_result(self, kb_dir: Path, question: str, answer: str) -> Path:
        import re

        slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")[:60] or "query"
        explore_dir = kb_dir / "wiki" / "explorations"
        explore_dir.mkdir(parents=True, exist_ok=True)
        path = explore_dir / f"{slug}.md"
        path.write_text(f'---\nquery: "{question}"\n---\n\n{answer}\n', encoding="utf-8")
        return path

    def _markdown_count(self, path: Path) -> int:
        return len(list(path.glob("*.md"))) if path.exists() else 0

    def _markdown_stems(self, path: Path) -> list[str]:
        return sorted(item.stem for item in path.glob("*.md")) if path.exists() else []

    def _markdown_names(self, path: Path) -> list[str]:
        return sorted(item.name for item in path.glob("*.md")) if path.exists() else []

    def _newest_mtime(self, path: Path) -> str | None:
        if not path.exists():
            return None
        files = list(path.glob("*.md"))
        if not files:
            return None
        import datetime

        newest = max(files, key=lambda item: item.stat().st_mtime)
        return datetime.datetime.fromtimestamp(newest.stat().st_mtime).isoformat()

    def _display_type(self, raw_type: str) -> str:
        if raw_type == "long_pdf":
            return "pageindex"
        if raw_type in {"pdf", "docx", "md", "markdown", "html", "htm", "txt", "csv", "pptx", "xlsx"}:
            return "short"
        return raw_type
