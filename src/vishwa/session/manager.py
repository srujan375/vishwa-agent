"""
Session Manager for Vishwa.

Handles saving, loading, and listing chat sessions for resumption.
Mirrors Claude Code's session management:
- Per-project storage
- Tool results preservation
- Checkpointing with rewind
- Named sessions
"""

import json
import os
import shutil
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Checkpoint:
    """Represents a checkpoint (code state before an edit)."""

    id: str
    timestamp: str
    message_index: int  # Which message triggered this checkpoint
    description: str  # What was about to happen
    file_states: Dict[str, str]  # path -> content before edit


@dataclass
class Session:
    """Represents a saved chat session."""

    id: str
    name: Optional[str]  # User-assigned name (for /rename)
    created_at: str
    updated_at: str
    working_directory: str
    git_branch: Optional[str]
    model: str
    message_count: int
    summary: str  # Brief summary of the conversation
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)  # Tool call results
    files_in_context: Dict[str, str] = field(default_factory=dict)
    modifications: List[Dict[str, Any]] = field(default_factory=list)
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)  # For rewind

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create session from dictionary."""
        # Handle missing fields for backwards compatibility
        data.setdefault("name", None)
        data.setdefault("git_branch", None)
        data.setdefault("tool_results", [])
        data.setdefault("checkpoints", [])
        return cls(**data)


class SessionManager:
    """
    Manages session persistence for Vishwa.

    Sessions are stored per-project in .vishwa/sessions/
    Falls back to ~/.vishwa/sessions/ for non-git directories.
    """

    def __init__(self, project_dir: Optional[Path] = None):
        """
        Initialize session manager.

        Args:
            project_dir: Project root directory (default: current working directory)
        """
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.sessions_dir = self._get_sessions_dir()

        # Ensure directory exists
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _get_sessions_dir(self) -> Path:
        """
        Get the sessions directory for the current project.

        Uses .vishwa/sessions/ in project root (git root or cwd).
        """
        # Try to find git root
        git_root = self._find_git_root()

        if git_root:
            return git_root / ".vishwa" / "sessions"
        else:
            # Fall back to project directory
            return self.project_dir / ".vishwa" / "sessions"

    def _find_git_root(self) -> Optional[Path]:
        """Find the git repository root."""
        current = self.project_dir

        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent

        return None

    def _get_git_branch(self) -> Optional[str]:
        """Get current git branch name."""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
            )
            if result.returncode == 0:
                return result.stdout.strip() or None
        except:
            pass
        return None

    def generate_session_id(self) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"{timestamp}-{short_uuid}"

    def save_session(self, session: Session) -> Path:
        """
        Save a session to disk.

        Args:
            session: Session to save

        Returns:
            Path to the saved session file
        """
        # Update timestamp
        session.updated_at = datetime.now().isoformat()

        # Update git branch
        session.git_branch = self._get_git_branch()

        # Save to file
        session_file = self.sessions_dir / f"{session.id}.json"

        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)

        return session_file

    def load_session(self, session_id: str) -> Optional[Session]:
        """
        Load a session from disk.

        Args:
            session_id: ID of the session to load

        Returns:
            Session if found, None otherwise
        """
        session_file = self.sessions_dir / f"{session_id}.json"

        if not session_file.exists():
            # Try to find by name
            return self._find_session_by_name(session_id)

        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Session.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def _find_session_by_name(self, name: str) -> Optional[Session]:
        """Find a session by its user-assigned name."""
        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("name") == name:
                    return Session.from_dict(data)
            except:
                continue
        return None

    def get_most_recent_session(self) -> Optional[Session]:
        """
        Get the most recent session for --continue flag.

        Returns:
            Most recent session or None
        """
        sessions = self.list_sessions(limit=1)
        if sessions:
            return self.load_session(sessions[0].id)
        return None

    def list_sessions(self, limit: int = 20) -> List[Session]:
        """
        List recent sessions.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of sessions, newest first
        """
        sessions = []

        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Load minimal info for listing (don't load full messages)
                session = Session(
                    id=data.get("id", session_file.stem),
                    name=data.get("name"),
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                    working_directory=data.get("working_directory", ""),
                    git_branch=data.get("git_branch"),
                    model=data.get("model", "unknown"),
                    message_count=data.get("message_count", 0),
                    summary=data.get("summary", ""),
                    messages=[],  # Don't load full messages for listing
                    tool_results=[],
                    files_in_context={},
                    modifications=[],
                    checkpoints=[],
                )
                sessions.append(session)

            except (json.JSONDecodeError, KeyError):
                continue

        # Sort by updated_at (newest first)
        sessions.sort(key=lambda s: s.updated_at, reverse=True)

        return sessions[:limit]

    def rename_session(self, session_id: str, new_name: str) -> bool:
        """
        Rename a session.

        Args:
            session_id: ID of session to rename
            new_name: New name for the session

        Returns:
            True if renamed successfully
        """
        session = self.load_session(session_id)
        if not session:
            return False

        session.name = new_name
        self.save_session(session)
        return True

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: ID of the session to delete

        Returns:
            True if deleted, False if not found
        """
        session_file = self.sessions_dir / f"{session_id}.json"

        if session_file.exists():
            session_file.unlink()
            return True

        return False

    def get_session_by_index(self, index: int) -> Optional[Session]:
        """
        Get a session by its index in the list (1-based).

        Args:
            index: 1-based index from list_sessions

        Returns:
            Full session if found, None otherwise
        """
        sessions = self.list_sessions(limit=50)

        if 1 <= index <= len(sessions):
            session_id = sessions[index - 1].id
            return self.load_session(session_id)

        return None

    def create_summary(self, messages: List[Dict[str, Any]]) -> str:
        """
        Create a brief summary of the conversation.

        Extracts the first user message as the summary.

        Args:
            messages: List of message dictionaries

        Returns:
            Brief summary string
        """
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # Truncate to first 100 chars
                if len(content) > 100:
                    return content[:100] + "..."
                return content

        return "Empty session"

    def cleanup_old_sessions(self, keep_count: int = 50) -> int:
        """
        Remove old sessions, keeping only the most recent ones.

        Args:
            keep_count: Number of sessions to keep

        Returns:
            Number of sessions deleted
        """
        sessions = self.list_sessions(limit=1000)

        if len(sessions) <= keep_count:
            return 0

        deleted = 0
        for session in sessions[keep_count:]:
            if self.delete_session(session.id):
                deleted += 1

        return deleted


class CheckpointManager:
    """
    Manages checkpoints for code state rewind.

    Creates snapshots of file states before edits,
    allowing users to rewind to previous states.
    """

    def __init__(self, session_id: str, checkpoints_dir: Optional[Path] = None):
        """
        Initialize checkpoint manager.

        Args:
            session_id: Current session ID
            checkpoints_dir: Directory for checkpoint storage
        """
        self.session_id = session_id

        if checkpoints_dir:
            self.checkpoints_dir = checkpoints_dir
        else:
            # Store in .vishwa/checkpoints/<session_id>/
            git_root = self._find_git_root()
            base = git_root if git_root else Path.cwd()
            self.checkpoints_dir = base / ".vishwa" / "checkpoints" / session_id

        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints: List[Checkpoint] = []
        self._load_checkpoints()

    def _find_git_root(self) -> Optional[Path]:
        """Find the git repository root."""
        current = Path.cwd()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return None

    def _load_checkpoints(self) -> None:
        """Load existing checkpoints from disk."""
        index_file = self.checkpoints_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file, "r") as f:
                    data = json.load(f)
                self.checkpoints = [
                    Checkpoint(**cp) for cp in data.get("checkpoints", [])
                ]
            except:
                self.checkpoints = []

    def _save_index(self) -> None:
        """Save checkpoint index to disk."""
        index_file = self.checkpoints_dir / "index.json"
        with open(index_file, "w") as f:
            json.dump({
                "session_id": self.session_id,
                "checkpoints": [asdict(cp) for cp in self.checkpoints]
            }, f, indent=2)

    def create_checkpoint(
        self,
        message_index: int,
        description: str,
        files_to_snapshot: List[str],
    ) -> Checkpoint:
        """
        Create a checkpoint before an edit.

        Args:
            message_index: Current message index
            description: What's about to happen
            files_to_snapshot: List of file paths to snapshot

        Returns:
            Created checkpoint
        """
        checkpoint_id = f"cp-{len(self.checkpoints):04d}"

        # Snapshot file states
        file_states = {}
        for file_path in files_to_snapshot:
            path = Path(file_path)
            if path.exists():
                try:
                    file_states[file_path] = path.read_text(encoding="utf-8")
                except:
                    pass  # Skip files that can't be read

        checkpoint = Checkpoint(
            id=checkpoint_id,
            timestamp=datetime.now().isoformat(),
            message_index=message_index,
            description=description,
            file_states=file_states,
        )

        self.checkpoints.append(checkpoint)

        # Save file states to disk
        cp_dir = self.checkpoints_dir / checkpoint_id
        cp_dir.mkdir(exist_ok=True)

        for file_path, content in file_states.items():
            # Preserve directory structure
            rel_path = Path(file_path).name
            (cp_dir / rel_path).write_text(content, encoding="utf-8")

        self._save_index()
        return checkpoint

    def get_checkpoints(self) -> List[Checkpoint]:
        """Get all checkpoints."""
        return self.checkpoints.copy()

    def rewind_to_checkpoint(
        self,
        checkpoint_id: str,
        rewind_code: bool = True,
    ) -> Optional[Checkpoint]:
        """
        Rewind to a specific checkpoint.

        Args:
            checkpoint_id: ID of checkpoint to rewind to
            rewind_code: Whether to restore file states

        Returns:
            The checkpoint rewound to, or None if not found
        """
        # Find checkpoint
        checkpoint = None
        checkpoint_index = -1
        for idx, cp in enumerate(self.checkpoints):
            if cp.id == checkpoint_id:
                checkpoint = cp
                checkpoint_index = idx
                break

        if not checkpoint:
            return None

        if rewind_code:
            # Restore file states
            for file_path, content in checkpoint.file_states.items():
                try:
                    Path(file_path).write_text(content, encoding="utf-8")
                except Exception as e:
                    print(f"Warning: Could not restore {file_path}: {e}")

        # Remove checkpoints after this one
        self.checkpoints = self.checkpoints[:checkpoint_index + 1]
        self._save_index()

        return checkpoint

    def rewind_to_index(self, index: int, rewind_code: bool = True) -> Optional[Checkpoint]:
        """
        Rewind to checkpoint by index (1-based, from most recent).

        Args:
            index: 1-based index (1 = most recent checkpoint)
            rewind_code: Whether to restore file states

        Returns:
            The checkpoint rewound to, or None
        """
        if not self.checkpoints or index < 1:
            return None

        # Convert to 0-based index from end
        actual_index = len(self.checkpoints) - index
        if actual_index < 0:
            return None

        checkpoint = self.checkpoints[actual_index]
        return self.rewind_to_checkpoint(checkpoint.id, rewind_code)

    def clear(self) -> None:
        """Clear all checkpoints."""
        self.checkpoints = []

        # Remove checkpoint files
        if self.checkpoints_dir.exists():
            shutil.rmtree(self.checkpoints_dir)
            self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
