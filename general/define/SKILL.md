---
name: define
description: Give plain, no-frills definitions of terms or concepts in a fixed two-line format (definition + purpose, no analogies, no code, no narrative buildup). Use when the user asks "what is X?", "define X", "what does X mean?", "explain X simply", invokes /define, or has pushed back on a verbose / analogy-heavy explanation and asked for "just the definition" or "no analogies." Do NOT use when the user asks "how does X work?", asks for examples, or wants elaboration.
---

# define

Give plain definitions. One line of definition + one line of purpose. That's it.

## Format

For each term:

```
**Term** — definition.
*Purpose:* what the thing is for.
*Example:* one concrete instance, in plain words. No code.
```

Multiple terms: do them as a flat list in this format. No section headers between them.

Optional extra line per term: `_Avoid_: X, Y, Z.` — names NOT to use for this concept. Use only when the user is establishing project-wide vocabulary discipline (e.g., editing a glossary).

## Rules

- **No analogies.** No light bulbs, power adapters, restaurants, clocks, plumbing, lego, kitchens, USB ports, etc. Definitions, not metaphors.
- **No code examples.** Unless the user explicitly asks for one.
- **No narrative buildup.** Don't say "let me explain", "great question", or restate the term in a sentence before defining it. Lead with the bolded term and an em-dash.
- **Three lines per term** (four if `_Avoid_` is needed). If you can't define in one line, the definition is too vague — sharpen it.
- **Purpose answers "why does this exist?"** — not "how do you use it?" or "what does it do internally?"
- **Example is concrete and specific** — one real instance, not a category. "Unix `tee` command" beats "any fan-out tool." Plain prose, no code blocks.
- **Plain English in the definition.** Don't define a term using other jargon unless that jargon was already defined in the same response or is clearly common knowledge.
- **No closing summary, no "does that help?" pleasantries.** End on the last definition.

## When to use

- User asks "what is X?" / "define X" / "what does X mean?"
- User says "explain X" — unless they explicitly ask for examples or deeper context.
- User invokes `/define X`.
- User has pushed back on a verbose explanation and asked for "just the definition," "no analogies," "plain definition," or similar.

## When NOT to use

- "How does X work?" → process question, not a definition. Give a normal explanation.
- "Why does X matter?" / "give me an example of X" → wants elaboration.
- Asks for a tutorial, walkthrough, comparison, or argument.

## Example

User: "what's a closure?"

Response:

**Closure** — a function bundled with the variables from the scope where it was created.
*Purpose:* lets a function remember data from outside its body even after that outer code has finished running.
*Example:* a counter function that returns the next number each time you call it, by holding onto a count variable from its creator.
