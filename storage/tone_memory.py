import json
import time
from pathlib import Path
from config.settings import TONE_LOG

# [ToneMemory] module for RLHF-style feedback and few-shot example selection

def save_rating(post_text: str, format_key: str, rating: int, timestamp: str = ""):
    """Appends a post rating to TONE_LOG as newline-delimited JSON."""
    if not timestamp:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
    entry = {
        "timestamp": timestamp,
        "format_key": format_key,
        "post_text": post_text,
        "rating": rating,
        "engagement": {
            "likes": 0,
            "retweets": 0,
            "replies": 0,
            "impressions": 0
        }
    }
    
    try:
        with open(TONE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"[ToneMemory] Saved rating {rating} for {format_key}")
    except Exception as e:
        print(f"[ToneMemory] Error saving rating: {e}")

def load_ratings():
    """Returns all entries from TONE_LOG."""
    if not TONE_LOG.exists():
        return []
    
    entries = []
    try:
        with open(TONE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    except Exception as e:
        print(f"[ToneMemory] Error loading ratings: {e}")
    
    return entries

def get_few_shot_examples(format_key: str = None, top_n: int = 3) -> list[str]:
    """
    Returns top_n post_text strings with highest rating for format_key.
    If format_key is None, returns top examples across all formats.
    """
    entries = load_ratings()
    if not entries:
        return []
    
    if format_key:
        filtered = [e for e in entries if e.get("format_key") == format_key]
    else:
        filtered = entries
        
    # Sort by rating descending
    sorted_entries = sorted(filtered, key=lambda x: x.get("rating", 0), reverse=True)
    return [e["post_text"] for e in sorted_entries[:top_n]]

def update_engagement(post_text: str, likes: int, retweets: int, replies: int):
    """
    Finds matching entry in TONE_LOG, updates with engagement metrics.
    Higher engagement boosts effective rating weight.
    """
    entries = load_ratings()
    updated = False
    
    # We use post_text as a loose identifier; in a real DB we'd use a UUID
    for e in entries:
        if e["post_text"] == post_text:
            e["engagement"]["likes"] = likes
            e["engagement"]["retweets"] = retweets
            e["engagement"]["replies"] = replies
            updated = True
            break
            
    if updated:
        try:
            with open(TONE_LOG, "w", encoding="utf-8") as f:
                for e in entries:
                    f.write(json.dumps(e) + "\n")
            print("[ToneMemory] Updated engagement metrics for post")
        except Exception as e:
            print(f"[ToneMemory] Error updating engagement: {e}")

def get_weighted_examples(format_key: str, top_n: int = 3) -> list[str]:
    """
    Combines explicit rating + engagement metrics into weighted score.
    Returns top_n examples by weighted score.
    Score = rating + (likes * 0.5) + (retweets * 1.0) + (replies * 2.0)
    """
    entries = load_ratings()
    if not entries:
        return []
    
    filtered = [e for e in entries if e.get("format_key") == format_key]
    
    def calculate_score(entry):
        r = entry.get("rating", 0)
        eng = entry.get("engagement", {})
        score = r + (eng.get("likes", 0) * 0.5) + (eng.get("retweets", 0) * 1.0) + (eng.get("replies", 0) * 2.0)
        return score

    sorted_entries = sorted(filtered, key=calculate_score, reverse=True)
    return [e["post_text"] for e in sorted_entries[:top_n]]

if __name__ == "__main__":
    print("=== TONE MEMORY TEST ===")
    
    # Clear and test
    if TONE_LOG.exists():
        TONE_LOG.unlink()
        
    save_rating("Example post 1", "deep_tech", 5)
    save_rating("Example post 2", "deep_tech", 3)
    save_rating("Example post 3", "deep_tech", 4)
    save_rating("Example post 4", "struggle", 5)
    
    examples = get_few_shot_examples("deep_tech", top_n=2)
    print(f"Top 2 Deep Tech examples: {examples}")
    assert len(examples) == 2
    assert examples[0] == "Example post 1"
    
    # Test engagement boost
    update_engagement("Example post 3", likes=10, retweets=5, replies=2)
    weighted = get_weighted_examples("deep_tech", top_n=1)
    print(f"Top weighted Deep Tech: {weighted}")
    # Score for post 1: 5
    # Score for post 3: 4 + (10*0.5) + (5*1.0) + (2*2.0) = 4 + 5 + 5 + 4 = 18
    assert weighted[0] == "Example post 3"
    
    print("Tone Memory tests: PASSED")
