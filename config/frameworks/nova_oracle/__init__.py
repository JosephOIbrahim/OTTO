"""
Nova Oracle Payload - Deferred Tier
===================================

Implements ThoughtLeader routing from Nova v3 Framework.

Source Frameworks:
- Nova v3 (canonical - Nova v2 merged into this)
- Nova ADHD (neurodiversity cluster)

Key Features:
- Cross-disciplinary thought leader consultation
- Neurodiversity cluster (C_NEURODIVERSITY_COGNITIVE_TECH)
- Keyword-based leader routing
"""

from typing import Dict, List, Any

# Thought Leader Clusters (from Nova v3)
CLUSTERS = {
    "C_SYSTEMS_FIRST_PRINCIPLES": {
        "name": "Systems & First Principles",
        "leaders": ["Elon Musk", "Richard Feynman", "Claude Shannon"],
        "keywords": ["systems", "first principles", "fundamental", "physics"]
    },
    "C_CREATIVITY_INNOVATION": {
        "name": "Creativity & Innovation",
        "leaders": ["Steve Jobs", "Leonardo da Vinci", "Pixar Brain Trust"],
        "keywords": ["creative", "innovative", "design", "art", "beauty"]
    },
    "C_BUSINESS_STRATEGY": {
        "name": "Business & Strategy",
        "leaders": ["Warren Buffett", "Peter Thiel", "Reid Hoffman"],
        "keywords": ["business", "strategy", "investment", "market"]
    },
    "C_COGNITIVE_SCIENCE": {
        "name": "Cognitive Science",
        "leaders": ["Daniel Kahneman", "Amos Tversky", "Herbert Simon"],
        "keywords": ["cognitive", "bias", "decision", "heuristic"]
    },
    "C_NEURODIVERSITY_COGNITIVE_TECH": {
        "name": "Neurodiversity & Cognitive Technology",
        "leaders": ["Temple Grandin", "Thomas West", "ADHD Research"],
        "keywords": ["neurodiversity", "adhd", "autism", "dyslexia", "cognitive"]
    }
}

def get_triggers() -> List[str]:
    """Triggers for loading this payload."""
    return ["expert", "inspiration", "cross-disciplinary", "thought leader",
            "perspective", "wisdom", "insight"]

def route_to_leaders(task: str) -> Dict[str, Any]:
    """Route task to relevant thought leader clusters.

    Returns matched clusters with confidence scores.
    """
    task_lower = task.lower()
    matches = {}

    for cluster_id, cluster in CLUSTERS.items():
        score = sum(1 for kw in cluster["keywords"] if kw in task_lower)
        if score > 0:
            matches[cluster_id] = {
                "name": cluster["name"],
                "leaders": cluster["leaders"],
                "score": score / len(cluster["keywords"])
            }

    # Sort by score
    sorted_matches = sorted(matches.items(), key=lambda x: -x[1]["score"])

    return {
        "matched_clusters": dict(sorted_matches[:3]),
        "primary_cluster": sorted_matches[0][0] if sorted_matches else None,
        "cross_disciplinary": len(matches) > 1
    }

def get_neurodiversity_boost(task: str) -> float:
    """Calculate neurodiversity relevance boost (Nova v3 feature).

    Boosts routing scores for neurodiversity-related queries.
    """
    neuro_keywords = ["adhd", "focus", "attention", "working memory",
                      "executive function", "hyperfocus", "burnout"]
    task_lower = task.lower()

    matches = sum(1 for kw in neuro_keywords if kw in task_lower)
    return min(matches * 0.1, 0.5)  # Max 50% boost

__all__ = ["CLUSTERS", "get_triggers", "route_to_leaders", "get_neurodiversity_boost"]
