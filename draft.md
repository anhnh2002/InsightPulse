About this project:
- I wanna build a semi-autonomous pipeline that automatically crawl papers, news from KOL on socials like LinkedIn and X
- for each paper: an ai agent carefully read it and write a blog, and classified to a well maintained hierachical topics tree, corresponding with flat key words
- for news: summarize and write a blog
- a blog should include personal opinion like strength, weakness, potential applications, next directions, ...; also should include metadata like authors and their org, github repo available and stars, ... whatever showing the reliability

- These blogs should stored in queue, and I'll manually review them to see papers/news worth to post a blog, as well as it contents and classified topic; I'll do this review with the support of codex

- Once blogs get accepted, push the blog to selfhosted blog pages

- We can treat these blogs as a very useful knowledge, whe we can add ai agents to summarise recent trends for example (let this feature for future implementation)


Technical advices:
- Any AI Agent implementation should use caw: https://github.com/zzjas/caw/tree/main, which allow us to use codex subscription to run agent on a well-designed harness (see ~/poc_playground/cgsa/scanning/pr_scan_agent.py for example)
- In order to allow AI agent to read and search throughout social, use https://github.com/Panniantong/Agent-Reach/tree/main , I already installed it for reaching LinkedIn and X
- Container all services via docker compose

List KOLs:
- LinkedIn: https://www.linkedin.com/in/omarsar/ ; https://www.linkedin.com/company/dair-ai/
- X: https://x.com/tom_doerr
- allow update later