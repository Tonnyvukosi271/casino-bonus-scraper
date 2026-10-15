# Submission

- Live page: [https://tonnyvukosi271.github.io/casino-bonus-scraper/](https://tonnyvukosi271.github.io/casino-bonus-scraper/) — deployed from `main` and verified.
- Repository: [https://github.com/Tonnyvukosi271/casino-bonus-scraper](https://github.com/Tonnyvukosi271/casino-bonus-scraper)
- Source used: [Casino.com South African casino bonuses](https://www.casino.com/zar/bonuses/). Live scrape run with `--no-ai` for Jackpot City, YesPlay, and Jabulabets.
- Source checks: On 2026-10-15, `https://www.casino.com/robots.txt` allowed `/` and disallowed only `/go/`. The legacy `/terms-and-conditions/` URL redirects to About, which discloses affiliate commissions; no standalone terms-of-use page was found.
- Time spent: 1 hour 30 minutes (within the 3-hour limit).
- Extraction result: Jackpot City — R2,000 match bonus or up to 350 free spins; YesPlay — 100% first deposit bonus; Jabulabets — up to R30,000 plus 245 free spins. The table does not give casino-specific wagering requirements or minimum deposits, so those fields are left blank rather than inferred. All three records are marked partial. No OpenAI request was made.
- To refresh: `python scraper.py --no-ai --source-url "https://www.casino.com/zar/bonuses/" --casinos "Jackpot City,YesPlay,Jabulabets"`
- Publishing: Changes were committed as `b685660` and pushed to `main`. The GitHub Pages deployment completed successfully, and the published JSON was verified to contain all three records.
- Written response: [production-plan.md](./production-plan.md)
- AI reflection: [AI_REFLECTION.md](./AI_REFLECTION.md)
