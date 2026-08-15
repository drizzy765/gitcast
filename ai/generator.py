"""
ai/generator.py

All AI generation routes through the Gitcast
cloud server at gitcast-api.onrender.com.
No direct provider calls exist in this file.
"""
import asyncio
from core.log_stream import stream_log


async def generate_posts(payload: dict) -> dict:
    """
    Routes post generation to Gitcast cloud server.
    Never calls providers directly.
    """
    from core.cloud_client import cloud_generate

    stream_log("GENERATOR", "INFO",
        "sending to Gitcast cloud server...")

    # clean payload — only send what server needs
    clean = {
        "raw_thought": payload.get(
            "raw_thought", ""),
        "ocr_text": payload.get("ocr_text", ""),
        "git_diff": payload.get("git_diff", ""),
        "git_diff_available": payload.get(
            "git_diff_available", False),
        "narrative": payload.get("narrative", ""),
        "user_message": payload.get(
            "user_message", ""),
        "format_keys": payload.get(
            "format_keys",
            ["x_post", "linkedin",
             "pr_desc", "quick_win"]),
        "project_name": payload.get(
            "project_name", ""),
        "readme_content": payload.get(
            "readme_content", ""),
        "tech_stack": payload.get(
            "tech_stack", ""),
        "project_type": payload.get(
            "project_type", ""),
        "all_docs": payload.get("all_docs", ""),
    }

    results = await cloud_generate(clean)

    if not results:
        stream_log("GENERATOR", "ERROR",
            "cloud server returned no results — "
            "check internet connection")
        format_keys = clean.get(
            "format_keys", [])
        return {
            k: "[Error] Could not reach generation "
               "server. Check your connection and "
               "try again."
            for k in format_keys
        }

    for key, val in results.items():
        if not str(val).startswith("[Error]"):
            stream_log("GENERATOR", "OK",
                f"{key} generated successfully")
        else:
            stream_log("GENERATOR", "WARN",
                f"{key} failed: {str(val)[:60]}")

    return results


async def generate_article(payload: dict) -> str:
    """
    Routes article generation to Gitcast cloud server.
    Never calls providers directly.
    """
    from core.cloud_client import (
        cloud_generate_article)

    stream_log("GENERATOR", "INFO",
        "generating article via cloud server...")

    clean = {
        "narrative": payload.get("narrative", ""),
        "readme_content": payload.get(
            "readme_content", ""),
        "all_docs": payload.get("all_docs", ""),
        "tech_stack": payload.get(
            "tech_stack", ""),
        "project_name": payload.get(
            "project_name", ""),
        "sprint_log": payload.get(
            "sprint_log", []),
        "project_context": payload.get(
            "project_context", ""),
    }

    result = await cloud_generate_article(clean)

    if not result:
        stream_log("GENERATOR", "ERROR",
            "article generation failed")
        return "[Error] Article generation failed. " \
               "Try again in a moment."

    stream_log("GENERATOR", "OK",
        "article generated successfully")
    return result


async def refine_post(
    current_post: str,
    instruction: str,
    format_key: str,
    **kwargs,
) -> str:
    """
    Routes post refinement to Gitcast cloud server.
    Never calls providers directly.
    """
    from core.cloud_client import cloud_refine

    stream_log("GENERATOR", "INFO",
        f"refining {format_key}: {instruction[:40]}")

    result = await cloud_refine(
        current_post=current_post,
        instruction=instruction,
        format_key=format_key,
    )

    if not result:
        return current_post

    stream_log("GENERATOR", "OK",
        "refinement complete")
    return result


async def generate_sprint_summary(
    entries: list,
    narrative: str = "",
) -> str:
    """
    Routes sprint summary generation to cloud.
    """
    from core.cloud_client import cloud_generate

    payload = {
        "raw_thought": "sprint summary",
        "narrative": narrative,
        "format_keys": ["sprint_summary"],
        "sprint_log": entries,
    }

    results = await cloud_generate(payload)
    return results.get("sprint_summary", "")
