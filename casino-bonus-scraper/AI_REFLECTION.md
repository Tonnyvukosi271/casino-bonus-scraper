# AI use (five lines)

1. Tool: Claude (Anthropic) wrote the first version of the scraper, tests, site and docs; the language-model step inside the scraper calls the OpenAI API (`gpt-4o-mini`).
2. I used AI for structure and boilerplate, and I reviewed what it produced rather than trusting passing tests.
3. **Mistake caught:** the anti-hallucination guard checked that numbers from the model appeared in the source text with a plain substring test, so a model answer of `35x` was accepted when the page said `350x` (same for `£20` vs `£200`).
4. How I caught it: I probed the function with near-miss inputs instead of relying on the tests, which had all passed first time; I then fixed it with whole-number matching and added regression tests. The same probe found that casino names matched inside longer words ("Alpha" in "Alphabet").
5. Live check: the Casino.com South African bonuses page exposed a limitation in the broad text-matching path, which could associate distant page text with a casino. I used the no-AI, table-header-based extractor for the published scrape; it captured the stated bonuses and left unstated wagering and minimum-deposit values empty.
