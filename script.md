# Riskfolio Frontend Walkthrough Script

Target length: 5 minutes

Demo portfolio: use the built-in Sample Portfolio:

## Recording Flow

### 0:00-0:20 - Opening

Visual: Start on the dashboard with the Riskfolio title visible.

Narration:
"Riskfolio is a portfolio risk analysis app for everyday investors. The goal is to take a list of stock holdings and turn it into practical risk information: current portfolio value, downside-loss estimates, stress-test scenarios, and efficient-frontier optimization."

Visual action: Slowly move from the page title down to the portfolio holdings panel.

### 0:20-1:20 - Portfolio Setup And Local-First Workflow

Visual: Show the sidebar, Active portfolio selector, portfolio name field, and New / Save / Delete buttons.

Narration:
"The main workflow starts with a portfolio. I can create a new portfolio, name it, save it, load a previously saved one from the dropdown or sidebar, and delete it when I no longer need it. Riskfolio is local-first, so portfolios stay in this browser by default instead of requiring an account before the app is usable."

Visual action: type the demo holdings.

Narration:
"By keying in the ticker and share quantities, Riskfolio fetches the latest quote data fetched from Yahoo Finance API, and displays the relevant information about the stock in question."

Narration:
"We cache the prices of the ticker symbol in the browser's storage, so that the application does not make unecessary API calls. Users can change the refresh rates in the settings menu."

Visual action: Show the estimated position value summary.

Narration:
"At the bottom of the holdings table, the app totals the share count and estimated current market value when the loaded quotes share one currency. That value becomes the baseline for the risk analysis."

### 1:20-1:45 - Optional Cloud Sync

Visual: Show the local-only / cloud sync panel.

Narration:
"Cloud sync is optional. If I stay signed out, portfolios remain local to this browser. If I choose to sign in with Google, Riskfolio can sync saved portfolios through Supabase so they are available across devices."

Visual action: Open the "Sign in to sync" dialog.

Narration:
"This keeps the privacy story simple: the app works locally first, and cloud sync is an explicit choice."

### 1:45-2:35 - Running All Analyses

Visual: Scroll to the Analyses section.

Narration:
"The analysis section is split into three capabilities. First is Value at Risk, which estimates downside loss. Second is a stress test, where I can shock individual holdings and volatility. Third is the optimizer, which compares the current allocation against efficient alternatives."

Visual action: Show the left-side controls.

Narration:
"For VaR, I can select a confidence level, choose the time horizon, and set the number of Monte Carlo simulations. For this demo, I will keep the default 95 percent confidence level, a one-week horizon, and 10,000 simulations."

Visual action: Click "Run All Analyses".

Narration:
"Clicking Run All Analyses sends the same portfolio through all three analysis modules, so the dashboard fills in as one complete risk report."

Visual action: If useful, mention or point to the quote currency shown in the analysis details.

Narration:
"Riskfolio now validates the portfolio by quote currency instead of assuming everything is in US dollars. A portfolio can use USD, EUR, JPY, or another supported quote currency, but all holdings in one run need to share the same quote currency so the totals and risk numbers are meaningful."

### 2:35-3:35 - Value At Risk Results

Visual: Focus on the Value at Risk Analysis card.

Narration:
The first analysis is Value at Risk, one of the instruments we use to measure risk. It tells us how much the portfolio could lose in an unusually bad week, based on the simulations we ran.

For example, at a 95% confidence level, Riskfolio focuses on the worst 5% of simulated outcomes. So if the app says the one-week Value at Risk is $1,175, that means: in the simulation, there is a 5% chance the portfolio loses at least $1,175 over the next week.

In simpler terms, VaR gives us a realistic downside warning line. It does not predict exactly what will happen, but it helps answer the question: “If this portfolio has a bad week, how bad could that loss reasonably be?”

Visual action: Point to Value at Risk and Expected Shortfall.

Narration:
"Expected Shortfall is the follow-up question. VaR tells us where the bad-loss line starts. Expected Shortfall looks past that line and asks: in those worst cases, how much do we lose on average? So it helps us understand not just when losses become serious, but how painful they could get."

Visual action: Move through Expected P&L, best case, worst case, standard deviation, and P&L range.

Narration:
"The supporting metrics show the simulated expected P&L, best case, worst case, standard deviation, and the overall P&L range. These numbers are shown in the portfolio's shared quote currency, helping the user understand both the central expectation and the spread of possible outcomes."

### 3:35-4:20 - Monte Carlo Price Paths

Visual: Scroll to Monte Carlo Price Paths inside the VaR result.

Narration:
"Riskfolio also includes an interactive Monte Carlo price-path view. Instead of only showing final risk metrics, it visualizes how the portfolio might move over time."

Visual action: Adjust Paths, Volatility, or Horizon, then click "Run Paths".

Narration:
"I can control how many paths to draw, increase or decrease the volatility multiplier, and extend the horizon. The grey lines are individual simulated paths, while the summary lines show the mean and the 5th to 95th percentile range."

Visual action: Hover on the chart tooltip.

Narration:
"Hovering the chart gives the mean, median, and percentile range for a selected trading day. This makes the uncertainty easier to interpret visually."

### 4:20-5:15 - Stress Testing

Visual: Move to Stress Scenario controls.

Narration:
"The stress test answers a different question: what happens if specific holdings are shocked and market volatility changes?"

Visual action: Set example shocks, such as NVDA or AAPL down 10 percent if using those tickers; for the sample portfolio, set XOM down 8 percent and JPM down 5 percent. Increase global volatility to 1.50x. Click "Run Stress Test".

Narration:
"Here I can apply holding-level price shocks and then increase the global volatility multiplier. This is useful for scenario planning, such as testing a sector selloff or a more volatile market environment."

Visual action: Show Baseline and Shocked cards side by side.

Narration:
"The output compares the baseline portfolio against the shocked scenario. The cards show metrics to measure risk, such as normal VaR, conditional VaR, and profit-and-loss standard deviation. The comparison makes it clear how a shock changes both current value and downside risk."

### 5:15-6:10 - Efficient Frontier Optimizer

Visual: Move to Optimizer Settings and output.

Narration:
"The optimizer looks at allocation quality. It uses the same tickers and simulates thousands of possible weight combinations, then compares those allocations against the current portfolio."

Visual action: Show the Optimizer Portfolios selector and the efficient-frontier chart.

Narration:
"On the chart, the grey cloud shows random sampled portfolios. The red line is the analytical efficient frontier. Further right means more annual volatility, and higher up means more expected annual return."

Visual action: Point to Max Sharpe, Min Volatility, and Your Portfolio markers.

Narration:
"The green marker is the max-Sharpe portfolio, which has the strongest return per unit of risk in the model. The yellow marker is the minimum-volatility allocation. The blue marker is the current portfolio. This helps the user see whether rebalancing could improve risk-adjusted return without changing the list of stocks."

Visual action: Show the three allocation cards and rebalance plan.

Narration:
"Below the chart, Riskfolio turns the optimizer output into readable allocation cards. It shows return, volatility, Sharpe ratio, target weights, and a share-level rebalance plan, so the result is not just abstract percentages."

### 6:10-6:40 - Glossary And Settings

Visual: Use the sidebar to open Glossary.

Narration:
"Riskfolio also includes a glossary for the main finance terms used in the interface. This helps users understand concepts like VaR, CVaR, Sharpe ratio, volatility, and efficient frontier without leaving the app."

Visual action: Open Settings.

Narration:
"The settings page controls market-data freshness and portfolio save behavior. Users can change the price refresh interval, clear cached quote data, toggle portfolio autosave, and wipe browser or cloud-saved portfolios separately. If the app had to show stale cached prices because the network was unavailable, it will automatically try to refresh those prices again when the user returns to the browser window."

### 6:40-7:00 - Closing

Visual: Return to the dashboard with the completed results visible.

Narration:
"Riskfolio brings together portfolio valuation, Monte Carlo downside analysis, stress testing, and efficient-frontier optimization in one local-first interface. It helps them understand the risk already inside their portfolio and make more informed allocation decisions."

On-screen closing text:
"Riskfolio - Portfolio risk analysis for everyday investors."
