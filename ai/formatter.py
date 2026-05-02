import re

# [Formatter] module for post cleaning and thread splitting

def split_into_thread(post_text: str, max_chars: int = 270) -> list[str]:
    """
    Splits text into multiple tweets at sentence boundaries.
    Numbers each tweet: 1/ 2/ 3/
    """
    if len(post_text) <= 280:
        return [post_text]

    # Split into sentences (basic regex split)
    sentences = re.split(r'(?<=[.!?])\s+', post_text.strip())
    
    tweets = []
    current_tweet = ""
    tweet_number = 1
    
    for sentence in sentences:
        # Check if adding this sentence exceeds limit (considering "N/ " prefix)
        prefix = f"{tweet_number}/ "
        potential_content = current_tweet + (" " if current_tweet else "") + sentence
        
        if len(prefix + potential_content) <= max_chars:
            current_tweet = potential_content
        else:
            if current_tweet:
                tweets.append(f"{tweet_number}/ {current_tweet}")
                tweet_number += 1
            
            # If a single sentence is too long, we must split it by words
            if len(f"{tweet_number}/ {sentence}") > max_chars:
                words = sentence.split()
                sub_tweet = ""
                for word in words:
                    if len(f"{tweet_number}/ {sub_tweet} {word}") <= max_chars:
                        sub_tweet = f"{sub_tweet} {word}".strip()
                    else:
                        tweets.append(f"{tweet_number}/ {sub_tweet}...")
                        tweet_number += 1
                        sub_tweet = word
                current_tweet = sub_tweet
            else:
                current_tweet = sentence

    if current_tweet:
        tweets.append(f"{tweet_number}/ {current_tweet}")

    return tweets

if __name__ == "__main__":
    print("=== THREAD SPLITTER TEST ===")
    long_post = "This is a very long post that should be split into multiple tweets. It contains many sentences. Each sentence is relatively short but together they exceed the limit of a single tweet. We want to see how the formatter handles this situation by splitting at sentence boundaries and numbering the resulting tweets correctly."
    
    # Force small limit for testing
    result = split_into_thread(long_post, max_chars=100)
    for t in result:
        print(f"[{len(t)} chars] {t}")
