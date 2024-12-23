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
    st.success("Access Granted! Please allow a few minutes for your DAM tickers to load.")
else:
    st.error("Please enter a valid code.")
    st.stop()  # Stops the app if the code is not correct

# Define tickers and time period
tickers = ['GOOGL', 'META', 'DIS', 'AMZN', 'TSLA', 'NKE', 'PG', 'KO', 'PEP', 
           'XOM', 'CVX', 'SLB', 'JPM', 'BAC', 'WFC', 'JNJ', 'PFE', 'UNH', 'BA', 
           'GE', 'CAT', 'AAPL', 'MSFT', 'NVDA', 'LIN', 'APD', 'FCX', 'AMT', 'PLD', 
           'SPG', 'NEE', 'DUK', 'SO']

all_data = pd.DataFrame()

# Define end date as today
end_date = datetime.now().strftime('%Y-%m-%d')

# Calculate start date as 13 months ago, and adjust to the first day of the month
start_date = (datetime.now() - relativedelta(months=13)).replace(day=1).strftime('%Y-%m-%d')

# Streamlit UI elements
st.subheader('DAM Tickers')
        
        # Download monthly historical data for each ticker
        data = yf.download(ticker, start=start_date, end=end_date, interval="1mo")
        
        # Get stock info, including sector
        stock_info = yf.Ticker(ticker).info
        sector = stock_info.get('sector', 'N/A')  # Get sector, if not available, return 'N/A'
        
        # Add Ticker, Sector, and Adjusted Close columns
        data['Ticker'] = ticker
        data['Sector'] = sector
        
        # Keep only the required columns
        all_data = pd.concat([all_data, data[['Ticker', 'Sector', 'Adj Close']]])

    # Reset index to format DataFrame
    all_data.reset_index(inplace=True)

    # Calculate Excess Return (Column E)
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

    # Map SPY Excess Return to all_data
    spy_return_map = dict(zip(spy_data['Date'], spy_data['SPY Excess Return']))
    all_data['SPY Excess Return'] = all_data['Date'].map(spy_return_map)

    # Calculate 3 Month Return (Column G)
    all_data['3 Month Return'] = all_data.groupby('Ticker')['Adj Close'].pct_change(periods=3)

    # Calculate 3 Month Market Weighted Return (Column H)
    def calculate_market_weighted_return(df):
        weighted_returns = []
        for i in range(len(df)):
            if i < 3:  # Require at least 3 months of data
                weighted_returns.append(None)
            else:
                weighted_return = (
                    df['SPY Excess Return'].iloc[i-3] * 0.04 +  # 3 periods ago
                    df['SPY Excess Return'].iloc[i-2] * 0.16 +  # 2 periods ago
                    df['SPY Excess Return'].iloc[i-1] * 0.36    # 1 period ago (most recent)
                )
                weighted_returns.append(weighted_return)
        return pd.Series(weighted_returns, index=df.index)

    all_data['3 Month Market Weighted Return'] = (
        all_data.groupby('Ticker', group_keys=False).apply(calculate_market_weighted_return)
    )

    # Calculate 12 Month Beta (Column I)
    def calculate_beta(df):
        beta = []
        for i in range(len(df)):
            if i < 11:  # Require at least 12 months of data
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
        # Example formula combining 3-month return, market weighted return, and beta.
        return (row['3 Month Return'] or 0) + (row['3 Month Market Weighted Return'] or 0) + (row['12 Month Beta'] or 0)

    # Apply DAM calculation
    all_data['DAM'] = all_data.apply(calculate_dam, axis=1)

    # Now group by ticker to get the overall DAM score for each ticker
    tickers_dam = all_data.groupby('Ticker').agg({'DAM': 'mean'}).reset_index()

    # Now group by sector and get the top 2 DAM tickers
    def get_top_two_dam_tickers(group):
        # Sort the group by DAM in descending order
        sorted_group = group.sort_values(by='DAM', ascending=False)
        # Get the top and second top tickers
        top_ticker = sorted_group.iloc[0]
        alt_ticker = sorted_group.iloc[1] if len(sorted_group) > 1 else None
        return pd.Series({
            'Ticker': top_ticker['Ticker'],
            'DAM': top_ticker['DAM'],
            'Alt Ticker': alt_ticker['Ticker'] if alt_ticker is not None else None,
            'Alt DAM': alt_ticker['DAM'] if alt_ticker is not None else None
        })

    # Merge the tickers DAM with sectors data
    tickers_dam_with_sector = all_data[['Ticker', 'Sector']].drop_duplicates()
    tickers_dam = tickers_dam.merge(tickers_dam_with_sector, on='Ticker', how='left')

    # Apply the function to each sector
    sector_best_tickers = tickers_dam.groupby('Sector').apply(get_top_two_dam_tickers)

    # Reset index and display the result in Streamlit
    sector_best_tickers_reset = sector_best_tickers.reset_index()
    st.dataframe(sector_best_tickers_reset[['Sector', 'Ticker', 'Alt Ticker']])


# Fetch the sector weightings for SPY ETF
etf = Ticker('SPY')
sector_weightings = etf.fund_sector_weightings

# Add subheader for Sector Weights
st.subheader("Sector Weights")
if isinstance(sector_weightings, dict) and 'SPY' in sector_weightings:
    st.write(f"\nSector weightings for SPY ETF:")
    for sector, weight in sector_weightings['SPY'].items():
        st.write(f"{sector}: {weight:.2%}")
elif hasattr(sector_weightings, 'columns') and 'SPY' in sector_weightings.columns:
    for index, row in sector_weightings.iterrows():
        sector = index.strip()
        weight = row['SPY']
        if sector:  # Skip any empty rows
            st.write(f"{sector}: {weight:.2%}")
else:
    st.write("Sector weightings for SPY ETF not found or no data available.")
