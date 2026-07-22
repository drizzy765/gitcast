import os
import json
from pathlib import Path

MAX_README_CHARS = 3000
MAX_STACK_CHARS = 500

def read_project_context(directory: str = None) -> dict:
    """
    Reads project context from the current working
    directory. Extracts README, tech stack, and
    project name to give the AI real grounding.
    """
    cwd = Path(directory or os.getcwd())

    context = {
        "project_name": cwd.name,
        "readme_content": "",
        "tech_stack": "",
        "project_type": "",
        "main_language": "",
    }

    # Read README
    for readme_name in [
        "README.md", "readme.md",
        "README.txt", "README"]:
        readme_path = cwd / readme_name
        if readme_path.exists():
            try:
                content = readme_path.read_text(
                    encoding="utf-8", errors="ignore")
                # cap at 3000 chars
                context["readme_content"] = \
                    content[:MAX_README_CHARS]
                if len(content) > MAX_README_CHARS:
                    context["readme_content"] += \
                        "\n... [truncated]"
                break
            except Exception:
                pass

    # Detect tech stack from config files
    stack_signals = []

    if (cwd / "requirements.txt").exists():
        try:
            reqs = (cwd / "requirements.txt"
                    ).read_text(errors="ignore")
            stack_signals.append(
                f"Python project. Dependencies: "
                f"{reqs[:300]}")
            context["main_language"] = "Python"
        except Exception:
            pass

    if (cwd / "package.json").exists():
        try:
            pkg = json.loads(
                (cwd / "package.json").read_text())
            name = pkg.get("name", "")
            deps = list(pkg.get(
                "dependencies", {}).keys())[:10]
            stack_signals.append(
                f"JavaScript/Node project: {name}. "
                f"Dependencies: {', '.join(deps)}")
            context["main_language"] = "JavaScript"
        except Exception:
            pass

    if (cwd / "Cargo.toml").exists():
        stack_signals.append("Rust project")
        context["main_language"] = "Rust"

    if (cwd / "go.mod").exists():
        stack_signals.append("Go project")
        context["main_language"] = "Go"

    if (cwd / "pom.xml").exists():
        stack_signals.append("Java/Maven project")
        context["main_language"] = "Java"

    if (cwd / "Dockerfile").exists():
        stack_signals.append("Dockerized")

    if (cwd / ".github").exists():
        stack_signals.append("GitHub Actions CI")

    context["tech_stack"] = " | ".join(
        stack_signals)[:MAX_STACK_CHARS]

    # detect project type
    if (cwd / "manage.py").exists():
        context["project_type"] = "Django web app"
    elif (cwd / "app.py").exists() or \
         (cwd / "main.py").exists():
        context["project_type"] = "Python app"
    elif (cwd / "index.js").exists() or \
         (cwd / "index.ts").exists():
        context["project_type"] = "Node.js app"
    elif (cwd / "src").exists():
        context["project_type"] = "Source project"

    return context

def detect_gitcast_window(ocr_text: str) -> bool:
    """
    Detects if the captured window is the Gitcast
    dashboard itself (localhost:8000).
    Returns True if the screenshot is of Gitcast.
    """
    gitcast_signals = [
        "localhost:8000",
        "127.0.0.1:8000",
        "DRAFT_ROOM",
        "X_POST",
        "GITCAST",
        "git diff → published post",
        "NEW_CAPTURE",
        "QUICK_WIN",
    ]
    ocr_upper = ocr_text.upper()
    matches = sum(1 for s in gitcast_signals
                  if s.upper() in ocr_upper)
    return matches >= 2
