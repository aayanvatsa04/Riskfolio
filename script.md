Here’s a ready-to-film 5-minute script for **Riskfolio**.

**Video Script**

**0:00-0:25 — Opening Hook**

**Visual:** Start on the Riskfolio homepage.

**Narration:**
“Most retail investors know what they own, but not always how much risk they are actually taking. A portfolio can look diversified on the surface, but still be exposed to major losses if the market moves against it. Riskfolio helps everyday investors understand that risk clearly, using tools usually seen in professional finance.”

**On screen:** Show the Riskfolio title and subtitle.

---

**0:25-1:10 — What Riskfolio Does**

**Visual:** Slowly scroll through the main portfolio input screen.

**Narration:**
“Riskfolio is a web application for portfolio risk analysis and optimization. You enter the stocks you own, along with the number of shares, and Riskfolio estimates the current value of your portfolio using recent market prices. From there, you can run two types of analysis: downside risk analysis, which tells you how much you could lose in a bad market scenario, and efficient frontier optimization, which shows whether your current allocation is giving you a good balance between risk and return.”

---

**1:10-2:00 — Entering a Portfolio**

**Visual:** Type example holdings such as `AAPL`, `MSFT`, `NVDA`, with quantities.

**Narration:**
“Let’s start by entering a sample portfolio. I’ll add a few stock tickers and the number of shares held. As I type each ticker, Riskfolio automatically fetches the latest available price and estimates the position value. This means users do not have to manually calculate how much each holding is worth.”

**Visual:** Show estimated position value.

**Narration:**
“Riskfolio also lets users name, save, load, and delete portfolios locally, which makes it easy to come back later and rerun analysis without typing everything again. Behind the scenes, this is powered by Dexie, a lightweight browser database wrapper. In simple terms, Dexie stores saved portfolios directly on the user’s own device, inside their browser. That means sensitive portfolio drafts are not being uploaded just to save them, which helps protect user privacy and removes the need for a full login system for local portfolio storage. When the user chooses to run an analysis, only the holdings needed for that calculation are sent to the backend.”

---

**2:00-3:10 — VaR Analysis**

**Visual:** Select “VaR analysis”. Choose 95% confidence, 22 days, 10,000 simulations. Click “Calculate VaR”.

**Narration:**
“The first analysis mode is Value at Risk, or VaR. In simple terms, this answers the question: ‘In a bad month, how much money could this portfolio realistically lose?’”

“Here, I can choose the confidence level, the time horizon, and how many simulations to run. For example, I’ll use a 95% confidence level over one month with 10,000 simulations.”

**Visual:** Show loading, then results.

**Narration:**
“Riskfolio then runs thousands of possible future portfolio outcomes based on historical price behavior. Instead of giving only one prediction, it gives a range of possible outcomes.”

**Visual:** Zoom in on Value at Risk and Expected Shortfall cards.

**Narration:**
“The Value at Risk number shows the loss threshold in a bad-case scenario. The Expected Shortfall goes one step further and estimates the average loss if things are even worse than that threshold. So instead of only saying, ‘Your portfolio might fall,’ Riskfolio gives a clearer dollar estimate of what that downside could look like.”

---

**3:10-3:55 — Simulation Chart**

**Visual:** Show Monte Carlo simulation chart. Adjust path count, horizon, or volatility slider.

**Narration:**
“Below the summary, Riskfolio visualizes possible portfolio paths. Each line represents one possible future path the portfolio could take. The chart helps make risk more intuitive: you can see that outcomes spread out over time, and higher volatility creates a wider range of possible results.”

“This is useful because investing risk is not just about average return. It is also about how uncomfortable the ride can get along the way.”

---

**3:55-4:45 — Efficient Frontier Optimization**

**Visual:** Switch to “Efficient frontier”. Choose simulated portfolios, click “Run Optimization”.

**Narration:**
“The second analysis mode is efficient frontier optimization. This helps answer a different question: ‘Am I using my chosen stocks in the best possible proportions?’”

**Visual:** Show efficient frontier chart.

**Narration:**
“Riskfolio compares thousands of possible portfolio allocations using the same stocks. Each dot represents a different mix of weights. The chart shows the relationship between expected return and volatility.”

**Visual:** Point to green, blue, and amber dots.

**Narration:**
“The green dot highlights the portfolio with the strongest risk-return balance. The blue dot shows the most stable allocation. The amber dot shows the user’s current portfolio. This makes it easy to see whether rebalancing could improve the portfolio without changing the actual stocks owned.”

---

**4:45-5:00 — Closing**

**Visual:** Return to full app view, showing both the input and results.

**Narration:**
“Riskfolio brings professional-style portfolio risk tools into a simple interface for everyday investors. It helps users understand potential losses, compare possible outcomes, and make more informed allocation decisions. It does not tell you what to buy, and it is not financial advice, but it gives you a clearer picture of the risk already inside your portfolio.”

**On-screen closing text:**
“Riskfolio — Portfolio risk analysis for everyday investors.”
