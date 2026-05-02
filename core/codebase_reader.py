import os
from pathlib import Path

# [CodebaseReader] module for summarising repo structure for articles

def read_repo_structure(repo_path: str) -> str:
    """
    Walks git repo, returns a string summary of filename -> first 50 lines.
    Caps total output at 6000 characters.
    """
    repo_root = Path(repo_path)
    if not repo_root.exists():
        return "Repo path does not exist."

    ignore_dirs = {".git", "node_modules", "venv", "__pycache__", ".npm-global"}
    summary_parts = []
    total_chars = 0
    char_limit = 4000 # Reduced from 6000

    for root, dirs, files in os.walk(repo_root):
        # In-place modification to skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            if total_chars >= char_limit:
                break
                
            file_path = Path(root) / file
            
            # Skip binary or irrelevant files
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.pyc', '.exe', '.bin', '.json', '.txt', '.log')):
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(500) # Read less per file
                    lines = content.splitlines()[:15] # Only first 15 lines
                    snippet = "\n".join(lines)
                    
                    rel_path = file_path.relative_to(repo_root)
                    entry = f"--- FILE: {rel_path} ---\n{snippet}\n"
                    
                    if total_chars + len(entry) > char_limit:
                        summary_parts.append(f"--- FILE: {rel_path} --- (TRUNCATED)")
                        total_chars = char_limit
                        break
                    
                    summary_parts.append(entry)
                    total_chars += len(entry)
            except Exception as e:
                print(f"[CodebaseReader] Error reading {file}: {e}")

        if total_chars >= char_limit:
            break

    return "\n".join(summary_parts)

def get_key_files(repo_path: str) -> str:
    """Returns content of key files like README or main entry points."""
    repo_root = Path(repo_path)
    key_names = {"README.md", "main.py", "app.py", "index.py", "cli.py", "server.py"}
    summary_parts = []
    
    for name in key_names:
        file_path = repo_root / name
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(2000)
                    summary_parts.append(f"=== KEY FILE: {name} ===\n{content}\n")
            except Exception as e:
                print(f"[CodebaseReader] Error reading key file {name}: {e}")
                
    return "\n".join(summary_parts)

def summarise_for_prompt(repo_path: str) -> str:
    """Combines structure and key files into a single string for AI injection."""
    print(f"[CodebaseReader] Summarising {repo_path}...")
    structure = read_repo_structure(repo_path)
    key_files = get_key_files(repo_path)
    
    summary = f"CODEBASE ARCHITECTURE SUMMARY:\n\n{key_files}\n\nFILE STRUCTURE SNIPPETS:\n{structure}"
    return summary

if __name__ == "__main__":
    print("=== CODEBASE READER TEST ===")
    current_dir = os.getcwd()
    summary = summarise_for_prompt(current_dir)
    print(summary[:1000] + "...")
    print(f"\nTotal summary length: {len(summary)} chars")
