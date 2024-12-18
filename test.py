import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
from dateutil.relativedelta import relativedelta
from yahooquery import Ticker

# Define a list of allowed access codes
AUTHORIZED_CODES = ["freelunch"]

# Login page
st.title("Dynamic Alpha Model (Beta)")
code_input = st.text_input("Enter your DAM access code:", type="password")

# Check if the entered code is valid
if code_input in AUTHORIZED_CODES:
    st.success("You're in. Please allow a few minutes for your DAM tickers to load.")
else:
    st.error("Please enter a valid code.")
    st.stop()  # Stops the app if the code is not correct

# Define tickers and time period
tickers = ['SPY', 'AAPL', 'MSFT', 'GOOG', 'AMZN', 'JNJ', 'PFE']  # Reduced list for clarity
all_data = pd.DataFrame()

# Define end date as today
end_date = datetime.now().strftime('%Y-%m-%d')

# Calculate start date as 13 months ago, and adjust to the first day of the month
start_date = (datetime.now() - relativedelta(months=13)).replace(day=1).strftime('%Y-%m-%d')

# Download data for all tickers
for ticker in tickers:
    print(f"Downloading monthly data for {ticker}...")
    data = yf.download(ticker, start=start_date, end=end_date, interval="1mo")
    stock_info = yf.Ticker(ticker).info
    sector = stock_info.get('sector', 'N/A')  # Get sector, if not available, return 'N/A'
    data['Ticker'] = ticker
    data['Sector'] = sector
    all_data = pd.concat([all_data, data[['Ticker', 'Sector', 'Adj Close']]])

all_data.reset_index(inplace=True)

# Calculate Excess Return
all_data['Excess Return'] = (
    all_data.groupby('Ticker')['Adj Close']
    .pct_change()
    .sub(0.024 / 12)  # Subtracting the risk-free rate (monthly)
    .fillna(0)
)

# Get SPY data and calculate SPY Excess Return
spy_data = yf.download('SPY', start=start_date, end=end_date, interval="1mo")
spy_data['SPY Excess Return'] = spy_data['Adj Close'].pct_change().sub(0.024 / 12).fillna(0)
spy_data.reset_index(inplace=True)
spy_return_map = dict(zip(spy_data['Date'], spy_data['SPY Excess Return']))
all_data['SPY Excess Return'] = all_data['Date'].map(spy_return_map)

# Calculate 3 Month Return
all_data['3 Month Return'] = all_data.groupby('Ticker')['Adj Close'].pct_change(periods=3)

# Calculate 3 Month Market Weighted Return
def calculate_market_weighted_return(df):
    weighted_returns = []
    for i in range(len(df)):
        if i < 3:
            weighted_returns.append(None)
        else:
            weighted_return = (
                df['SPY Excess Return'].iloc[i-3] * 0.04 +
                df['SPY Excess Return'].iloc[i-2] * 0.16 +
                df['SPY Excess Return'].iloc[i-1] * 0.36
            )
            weighted_returns.append(weighted_return)
    return pd.Series(weighted_returns, index=df.index)

all_data['3 Month Market Weighted Return'] = (
    all_data.groupby('Ticker', group_keys=False).apply(calculate_market_weighted_return)
)

# Calculate 12 Month Beta
def calculate_beta(df):
    beta = []
    for i in range(len(df)):
        if i < 11:
            beta.append(None)
        else:
            y = df['Excess Return'].iloc[i-11:i+1]
            x = df['SPY Excess Return'].iloc[i-11:i+1]
            beta.append(pd.Series(y).cov(x) / pd.Series(x).var())
    return pd.Series(beta, index=df.index)

all_data['12 Month Beta'] = (
    all_data.groupby('Ticker', group_keys=False).apply(calculate_beta)
)

# Define DAM calculation function
def calculate_dam(row):
    return (row['3 Month Return'] or 0) + (row['3 Month Market Weighted Return'] or 0) + (row['12 Month Beta'] or 0)

# Apply DAM calculation
all_data['DAM'] = all_data.apply(calculate_dam, axis=1)

# Apply 20% constraint
def apply_max_allocation_constraint(df, max_allocation=0.20):
    df = df.sort_values(by='DAM', ascending=False)
    total_weight = 0
    allocations = []
    
    for _, row in df.iterrows():
        remaining_allocation = max_allocation - total_weight
        allocation = min(row['DAM'], remaining_allocation)
        total_weight += allocation
        allocations.append(allocation)
    
    df['Adjusted Weight'] = allocations
    return df

# Group by sector and apply the constraint
sector_best_tickers = all_data.groupby('Sector').apply(lambda x: apply_max_allocation_constraint(x))

# Print Results
st.write(f"{'Sector':<20} | {'Ticker':<6} | {'DAM':<8} | {'Adjusted Weight':>15}")
st.write("-" * 58)
for sector, row in sector_best_tickers.iterrows():
    st.write(f"{row['Sector']:<20} | {row['Ticker']:<6} | {row['DAM']:<8.2f} | {row['Adjusted Weight']:>15.2%}")
