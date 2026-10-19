# quiz-me-full

Spaced-repetition quizzing (SM-2) over Markdown decks, with an adaptive difficulty ladder, leech detection, confidence-weighted grading, and progress kept as plain Markdown in `~/Desktop/quiz-progress/`.

- Requirements: `python3` (no packages). Standalone: it bundles its own deck parser and renderer.
- Install: `cp -r skills/learning/quiz-me-full ~/.claude/skills/`
- Use: `python3 ~/.claude/skills/learning/quiz-me-full/scripts/quizctl.py start deck.md`, then `sync`, `status`, `brief`.
