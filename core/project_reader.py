import os
import json
from pathlib import Path

MAX_README_CHARS = 3000
MAX_STACK_CHARS = 500

import os
import json
import subprocess
from pathlib import Path

MAX_README_CHARS = 4000
MAX_STACK_CHARS = 800

def read_project_context(directory: str = None) -> dict:
    """
    Reads comprehensive project context from the given directory.
    Extracts README, secondary markdown docs, package configs (package.json, pyproject.toml, etc.),
    tech stack, recent git history, and project name to give the AI complete grounding.
    """
    cwd = Path(directory or os.getcwd())

    context = {
        "project_name": cwd.name,
        "readme_content": "",
        "tech_stack": "",
        "project_type": "",
        "main_language": "",
        "package_info": "",
        "doc_summaries": "",
        "recent_commits": "",
    }

    # 1. Read README
    for readme_name in ["README.md", "readme.md", "README.txt", "README"]:
        readme_path = cwd / readme_name
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding="utf-8", errors="ignore")
                context["readme_content"] = content[:MAX_README_CHARS]
                if len(content) > MAX_README_CHARS:
                    context["readme_content"] += "\n... [truncated]"
                break
            except Exception:
                pass

    # 2. Read secondary markdown documentation (docs/*.md, ARCHITECTURE.md, etc.)
    secondary_docs = []
    doc_candidates = list(cwd.glob("*.md"))
    if (cwd / "docs").exists():
        doc_candidates.extend(list((cwd / "docs").glob("*.md")))
    for doc in doc_candidates:
        if doc.name.lower() in ["readme.md", "license.md"]:
            continue
        try:
            doc_text = doc.read_text(encoding="utf-8", errors="ignore").strip()
            if doc_text:
                secondary_docs.append(f"### Doc: {doc.name}\n{doc_text[:600]}")
        except Exception:
            pass
    if secondary_docs:
        context["doc_summaries"] = "\n\n".join(secondary_docs[:4])

    # 3. Detect tech stack & detailed package configs
    stack_signals = []
    pkg_info = []

    if (cwd / "package.json").exists():
        try:
            pkg = json.loads((cwd / "package.json").read_text(encoding="utf-8", errors="ignore"))
            name = pkg.get("name", cwd.name)
            version = pkg.get("version", "")
            desc = pkg.get("description", "")
            deps = list(pkg.get("dependencies", {}).keys())[:15]
            dev_deps = list(pkg.get("devDependencies", {}).keys())[:10]
            scripts = list(pkg.get("scripts", {}).keys())[:8]

            if name:
                context["project_name"] = name
            context["main_language"] = "TypeScript/JavaScript"
            stack_signals.append(f"JS/TS project: {name} v{version}")

            info = f"package.json name: {name} (v{version})"
            if desc:
                info += f"\nDescription: {desc}"
            if deps:
                info += f"\nDependencies: {', '.join(deps)}"
            if dev_deps:
                info += f"\nDevDependencies: {', '.join(dev_deps)}"
            if scripts:
                info += f"\nScripts: {', '.join(scripts)}"
            pkg_info.append(info)
        except Exception:
            pass

    if (cwd / "pyproject.toml").exists():
        try:
            pyproject_text = (cwd / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
            stack_signals.append("Python project (pyproject.toml)")
            context["main_language"] = "Python"
            pkg_info.append(f"pyproject.toml:\n{pyproject_text[:400]}")
        except Exception:
            pass

    if (cwd / "requirements.txt").exists():
        try:
            reqs = (cwd / "requirements.txt").read_text(encoding="utf-8", errors="ignore").strip()
            stack_signals.append("Python project (requirements.txt)")
            context["main_language"] = "Python"
            pkg_info.append(f"Python Dependencies: {reqs[:300]}")
        except Exception:
            pass

    if (cwd / "Cargo.toml").exists():
        stack_signals.append("Rust project (Cargo.toml)")
        context["main_language"] = "Rust"

    if (cwd / "go.mod").exists():
        stack_signals.append("Go project (go.mod)")
        context["main_language"] = "Go"

    if (cwd / "pom.xml").exists():
        stack_signals.append("Java/Maven project")
        context["main_language"] = "Java"

    if (cwd / "Dockerfile").exists():
        stack_signals.append("Dockerized")

    if (cwd / ".github").exists():
        stack_signals.append("GitHub Actions CI")

    context["tech_stack"] = " | ".join(stack_signals)[:MAX_STACK_CHARS]
    context["package_info"] = "\n".join(pkg_info)[:1500]

    # 4. Recent git commits
    try:
        res = subprocess.run(
            ["git", "log", "-n", "5", "--pretty=format:%h %s (%cr)"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            errors="ignore",
            timeout=3
        )
        if res.returncode == 0 and res.stdout.strip():
            context["recent_commits"] = res.stdout.strip()
    except Exception:
        pass

    # Detect project type
    if (cwd / "manage.py").exists():
        context["project_type"] = "Django web app"
    elif (cwd / "app.py").exists() or (cwd / "main.py").exists():
        context["project_type"] = "Python app"
    elif (cwd / "next.config.js").exists() or (cwd / "next.config.mjs").exists() or (cwd / "next.config.ts").exists():
        context["project_type"] = "Next.js web app"
    elif (cwd / "vite.config.js").exists() or (cwd / "vite.config.ts").exists():
        context["project_type"] = "Vite web app"
    elif (cwd / "index.js").exists() or (cwd / "index.ts").exists():
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
