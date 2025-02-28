import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time

# Define a list of allowed access codes
AUTHORIZED_CODES = ["freelunch"]

# Login page
st.title("Dynamic Alpha Model")
code_input = st.text_input("Enter your DAM access code:", type="password")

# Initialize a flag to check if the code is correct
is_code_valid = code_input in AUTHORIZED_CODES if code_input else None

# Display success or error messages based on code validation
if is_code_valid:
    st.success("Access Granted!")

    # Display DAM instructions and the model status message
    st.write("**DAM Instructions:**")
    st.write("1. Rotate at the beginning of the month.")
    st.write("2. Ensure current monthly data is true (before 5th).")
    st.write("3. Weight portfolio matching S&P sectors.")
    st.write("4. Errors/questions: tannerterry221@gmail.com")

    # Initialize tickers and data collection
    tickers = ['A', 'AAPL', 'ABBV', 'ABC', 'ABMD', 'ABT', 'ACGL', 'ACN', 'ADBE', 'ADI', 'ADM', 'ADP', 'ADSK']
    all_data = pd.DataFrame()

    # Set date range
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - relativedelta(months=13)).replace(day=1).strftime('%Y-%m-%d')

    st.subheader("DAM Tickers")
    status_placeholder = st.empty()

    for ticker in tickers:
        status_placeholder.text(f"Downloading data for {ticker}...")
        stock = yf.Ticker(ticker)
        data = stock.history(period='14mo', interval='1mo')  # Using history() instead of download()
        data.reset_index(inplace=True)

        # Try to get sector info safely
        stock_info = stock.info
        sector = stock_info.get('sector', 'N/A')

        data['Ticker'] = ticker
        data['Sector'] = sector
        all_data = pd.concat([all_data, data[['Date', 'Ticker', 'Sector', 'Close']].rename(columns={'Close': 'Adj Close'})])

        time.sleep(1)  # Sleep for 1 second between requests to avoid hitting rate limits

    all_data.reset_index(drop=True, inplace=True)
    all_data = all_data[all_data['Sector'] != 'N/A']

    # Calculate Excess Return
    all_data['Excess Return'] = all_data.groupby('Ticker')['Adj Close'].pct_change().sub(0.024 / 12).fillna(0)

    # Get SPY data for comparison
    spy_data = yf.Ticker('SPY').history(period='14mo', interval='1mo')
    spy_data.reset_index(inplace=True)
    spy_data['SPY Excess Return'] = spy_data['Close'].pct_change().sub(0.024 / 12).fillna(0)
    spy_return_map = dict(zip(spy_data['Date'], spy_data['SPY Excess Return']))
    all_data['SPY Excess Return'] = all_data['Date'].map(spy_return_map)

    all_data['3 Month Return'] = all_data.groupby('Ticker')['Adj Close'].pct_change(periods=3)

    # Calculate Market Weighted Return
    def calculate_market_weighted_return(df):
        weighted_returns = [None] * 3
        for i in range(3, len(df)):
            weighted_returns.append(
                df['SPY Excess Return'].iloc[i-3] * 0.04 +
                df['SPY Excess Return'].iloc[i-2] * 0.16 +
                df['SPY Excess Return'].iloc[i-1] * 0.36
            )
        return pd.Series(weighted_returns, index=df.index)

    all_data['3 Month Market Weighted Return'] = all_data.groupby('Ticker', group_keys=False).apply(calculate_market_weighted_return)

    # Calculate Beta
    def calculate_beta(df):
        beta = [None] * 11
        for i in range(11, len(df)):
            y = df['Excess Return'].iloc[i-11:i+1]
            x = df['SPY Excess Return'].iloc[i-11:i+1]
            beta.append(pd.Series(y).cov(x) / pd.Series(x).var())
        return pd.Series(beta, index=df.index)

    all_data['12 Month Beta'] = all_data.groupby('Ticker', group_keys=False).apply(calculate_beta)

    # Calculate DAM
    all_data['DAM'] = all_data.apply(lambda row: (row['3 Month Return'] or 0) + (row['3 Month Market Weighted Return'] or 0) + (row['12 Month Beta'] or 0), axis=1)

    tickers_dam = all_data.groupby('Ticker').agg({'DAM': 'mean'}).reset_index()
    tickers_dam_with_sector = all_data[['Ticker', 'Sector']].drop_duplicates()
    tickers_dam = tickers_dam.merge(tickers_dam_with_sector, on='Ticker', how='left')

    def get_top_two_dam_tickers(group):
        sorted_group = group.sort_values(by='DAM', ascending=False)
        top_ticker = sorted_group.iloc[0]
        alt_ticker = sorted_group.iloc[1] if len(sorted_group) > 1 else None
        return pd.Series({
            'Ticker': top_ticker['Ticker'],
            'Alt Ticker': alt_ticker['Ticker'] if alt_ticker is not None else None
        })

    sector_best_tickers = tickers_dam.groupby('Sector').apply(get_top_two_dam_tickers).reset_index()
    styler = sector_best_tickers.style.hide(axis="index")
    
    # Determine if data is current
    latest_date = all_data['Date'].max().strftime('%Y-%m-%d')  # Get latest available date
    current_month = datetime.now().strftime('%Y-%m')  # Get current month as YYYY-MM

    is_current_data = latest_date.startswith(current_month)

    # Display True/False for current data check
    st.write(f"**Model using current monthly data:** {is_current_data}")

    # Proceed button
    if st.button("Proceed"):
        st.write(styler.to_html(), unsafe_allow_html=True)

        # Fetch and display sector weightings
        st.subheader("Sector Weights")
        try:
            etf = yf.Ticker('SPY')
            funds_data = etf.funds_data  # Accessing funds data
            sector_weightings = funds_data.sector_weightings  # Retrieve sector weightings for the ETF
            
            if sector_weightings:
                formatted_weightings = {sector: f"{weight * 100:.2f}%" for sector, weight in sector_weightings.items()}
                st.write(formatted_weightings)
            else:
                st.write("No sector weightings data available for SPY ETF.")
        except Exception as e:
            st.error(f"Error retrieving sector weightings: {e}")

elif is_code_valid is False:
    st.error("Please enter a valid code.")
