"""Auto-Tagger für Video-Szenen basierend auf Moondream-Captions.

Extrahiert semantische Tags aus Bild-Beschreibungen via Keyword-Matching.
AMD-Version: Identisch (rein Python, kein GPU).
"""

from typing import List


TAG_KEYWORDS = {
    "person": [
        "person", "man", "woman", "people", "crowd", "face", "dancer",
        "girl", "boy", "child", "group", "audience", "performer", "singer",
        "dj", "musician",
    ],
    "nature": [
        "mountain", "forest", "tree", "beach", "ocean", "sky", "sunset",
        "water", "river", "lake", "cloud", "rain", "snow", "flower",
        "sunrise", "landscape", "field", "grass",
    ],
    "urban": [
        "building", "street", "city", "car", "road", "bridge", "window",
        "tower", "skyscraper", "traffic", "neon", "sign", "store",
        "apartment", "downtown",
    ],
    "action": [
        "running", "dancing", "jumping", "walking", "playing", "moving",
        "spinning", "flying", "driving", "swimming", "climbing", "performing",
    ],
    "dark": [
        "dark", "night", "shadow", "silhouette", "black", "dim", "nighttime",
    ],
    "bright": [
        "bright", "light", "sun", "glow", "neon", "colorful", "vivid",
        "illuminated", "shining", "glowing", "sparkling",
    ],
    "indoor": [
        "room", "interior", "stage", "studio", "hall", "club", "bar",
        "concert", "venue", "warehouse", "ceiling", "floor",
    ],
    "outdoor": [
        "outdoor", "field", "park", "garden", "open", "outside",
        "horizon", "aerial", "drone",
    ],
    "abstract": [
        "abstract", "pattern", "geometric", "texture", "blur", "fractal",
        "distort", "kaleidoscope", "psychedelic", "trippy",
    ],
    "closeup": [
        "close", "detail", "macro", "hand", "eye", "finger", "mouth",
        "closeup", "close-up",
    ],
    "vehicle": [
        "car", "truck", "motorcycle", "bike", "bus", "train", "plane",
        "boat", "ship", "helicopter",
    ],
    "animal": [
        "dog", "cat", "bird", "horse", "fish", "animal", "insect",
        "butterfly", "snake", "wolf",
    ],
}


def extract_tags(caption: str) -> List[str]:
    """Extrahiert semantische Tags aus einer Moondream-Caption."""
    if not caption:
        return []
    caption_lower = caption.lower()
    tags = []
    for tag, keywords in TAG_KEYWORDS.items():
        for keyword in keywords:
            if keyword in caption_lower:
                tags.append(tag)
                break
    return tags


def aggregate_clip_tags(scene_tags_list: List[List[str]], min_ratio: float = 0.2) -> List[str]:
    """Aggregiert Scene-Tags zu Clip-Level Tags.

    Ein Tag wird zum Clip-Tag wenn es in mindestens min_ratio der Szenen vorkommt.
    """
    if not scene_tags_list:
        return []
    total = len(scene_tags_list)
    tag_counts: dict[str, int] = {}
    for tags in scene_tags_list:
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    threshold = max(1, int(total * min_ratio))
    return sorted(tag for tag, count in tag_counts.items() if count >= threshold)
