from dataclasses import dataclass

MODES = ("behavioral", "project", "system_design")

SCALE = ("1 = missing or wrong, 2 = weak, 3 = adequate for an intern, "
         "4 = strong, 5 = exceptional for an intern")


@dataclass(frozen=True)
class Criterion:
    name: str
    description: str


RUBRICS: dict[str, tuple[Criterion, ...]] = {
    "behavioral": (
        Criterion("Structure", "Clear situation, task, action and result; easy to follow."),
        Criterion("Specificity", "Concrete details such as systems, numbers and timelines, not generalities."),
        Criterion("Ownership", "Clear about what the candidate personally did."),
        Criterion("Impact", "A real, preferably measurable outcome."),
        Criterion("Reflection", "What they learned or would do differently."),
    ),
    "project": (
        Criterion("Problem framing", "Explains the problem, who it was for and why it mattered."),
        Criterion("Technical depth", "Accurate explanation of how the system works."),
        Criterion("Trade-offs", "Names alternatives considered and why one was chosen."),
        Criterion("Ownership", "Clear about which parts the candidate built."),
        Criterion("Results", "How success was measured, with real outcomes."),
    ),
    "system_design": (
        Criterion("Requirements", "Clarifies functional needs and scale before designing."),
        Criterion("High-level design", "Sensible components and how they interact."),
        Criterion("Scalability", "Identifies bottlenecks and how to handle growth."),
        Criterion("Trade-offs", "Weighs options such as consistency, cost and complexity."),
        Criterion("Communication", "Structured, easy-to-follow explanation."),
    ),
}


def overall_score(scores: list[int]) -> int:
    """Map the mean of 1-5 criterion scores onto 1-10: all 1s -> 1, all 5s -> 10."""
    mean = sum(scores) / len(scores)
    return int(1 + (mean - 1) * 9 / 4 + 0.5)  # round half up