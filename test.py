import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
from dateutil.relativedelta import relativedelta
from yahooquery import Ticker

# Define a list of allowed access codes
AUTHORIZED_CODES = ["freelunch"]

# Login page
st.title("Dynamic Alpha Model")
code_input = st.text_input("Enter your DAM access code:", type="password")

# Initialize a flag to check if the code is correct
is_code_valid = None

# Check if the entered code is valid
if code_input:
    if code_input in AUTHORIZED_CODES:
        is_code_valid = True
    else:
        is_code_valid = False

# Display success or error messages based on code validation
if is_code_valid:
    st.success("Access Granted!")

    # Step 1: Model using current monthly data (TRUE/FALSE) message
    use_current_data = True  # This can be set based on your conditions
    st.write(f"Model using current monthly data: {use_current_data}")

    # Step 2: Proceed Button
    proceed_button = st.button("Proceed")
    
    if proceed_button:
        st.write("Please allow a few minutes for your DAM tickers to load.")
        # Define tickers and time period
        tickers = [
            'A', 'AAPL', 'ABBV', 'ABC', 'ABMD', 'ABT', 'ACGL', 'ACN', 'ADBE', 'ADI', 'ADM', 'ADP', 'ADSK',
            'AEE', 'AEP', 'AES', 'AFL', 'AIG', 'AIZ', 'AJG', 'AKAM', 'ALB', 'ALGN', 'ALK', 'ALL', 'ALLE', 'AMAT',
            'AMCR', 'AMD', 'AME', 'AMGN', 'AMP', 'AMT', 'AMZN', 'ANET', 'ANSS', 'AON', 'AOS', 'APA', 'APD', 'APH',
            'APTV', 'ARE', 'ATO', 'ATVI', 'AVB', 'AVGO', 'AVY', 'AWK', 'AXP', 'AZO', 'BA', 'BAC', 'BAX', 'BBWI',
            'BBY', 'BDX', 'BEN', 'BF.B', 'BIIB', 'BK', 'BKNG', 'BKR', 'BLK', 'BLL', 'BMY', 'BR', 'BRK.B', 'BRO',
            'BSX', 'BWA', 'BXP', 'C', 'CAG', 'CAH', 'CARR', 'CAT', 'CB', 'CBOE', 'CBRE', 'CCI', 'CCL', 'CDNS'
        ]
        
        all_data = pd.DataFrame()

        # Define end date as today
        end_date = datetime.now().strftime('%Y-%m-%d')

        # Calculate start date as 13 months ago, and adjust to the first day of the month
        start_date = (datetime.now() - relativedelta(months=13)).replace(day=1).strftime('%Y-%m-%d')

        # Streamlit UI elements
        st.subheader('DAM Tickers')

        # Placeholder for progress updates
        status_placeholder = st.empty()

        # Download data for all tickers
        for ticker in tickers:
            # Update the status in the placeholder
            status_placeholder.text(f"Downloading data for {ticker}...")

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

        # Exclude tickers with "N/A" sector
        all_data = all_data[all_data['Sector'] != 'N/A']

        # Calculate 12-Month Return
        all_data['12 Month Return'] = all_data.groupby('Ticker')['Adj Close'].pct_change(periods=12)

        # Calculate 12-Month Weighted Return (Example using equal weights, adjust as needed)
        def calculate_12_month_weighted_return(df):
            weighted_returns = []
            for i in range(len(df)):
                if i < 11:  # Require at least 12 months of data
                    weighted_returns.append(None)
                else:
                    weighted_return = (
                        df['SPY Excess Return'].iloc[i-11:i+1]  # Last 12 months
                    ).mean()  # Replace with weighted logic if necessary
            weighted_returns.append(weighted_return)
            return pd.Series(weighted_returns, index=df.index)

        all_data['12 Month Weighted Return'] = (
            all_data.groupby('Ticker', group_keys=False).apply(calculate_12_month_weighted_return)
        )

        # Calculate 6-Month Volatility
        all_data['6 Month Volatility'] = all_data.groupby('Ticker')['Adj Close'].pct_change().rolling(6).std()

        # Calculate 6-Month Beta
        def calculate_6_month_beta(df):
            beta = []
            for i in range(len(df)):
                if i < 5:  # Require at least 6 months of data
                    beta.append(None)
                else:
                    y = df['Excess Return'].iloc[i-5:i+1]
                    x = df['SPY Excess Return'].iloc[i-5:i+1]
                    beta.append(pd.Series(y).cov(x) / pd.Series(x).var())
            return pd.Series(beta, index=df.index)

        all_data['6 Month Beta'] = (
            all_data.groupby('Ticker', group_keys=False).apply(calculate_6_month_beta)
        )

        # Calculate DAM Score
        def calculate_dam_score(row):
            try:
                dam_score = (
                    (row['12 Month Return'] * row['12 Month Weighted Return']) /
                    row['6 Month Volatility'] * row['6 Month Beta']
                )
            except ZeroDivisionError:
                dam_score = None  # Handle cases where volatility is zero
            return dam_score

        all_data['DAM'] = all_data.apply(calculate_dam_score, axis=1)

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

        # Now reset index and display the result
        sector_best_tickers_reset = sector_best_tickers.reset_index()
        st.write(sector_best_tickers_reset[['Sector', 'Ticker', 'Alt Ticker']])

        # Download SPY data and calculate SPY Excess Return
        spy_data = yf.download('SPY', start=start_date, end=end_date, interval="1mo")
        spy_data['SPY Excess Return'] = spy_data['Adj Close'].pct_change().sub(0.024 / 12).fillna(0)
        spy_data.reset_index(inplace=True)

        # Map SPY Excess Return to all_data
        spy_return_map = dict(zip(spy_data['Date'], spy_data['SPY Excess Return']))
        all_data['SPY Excess Return'] = all_data['Date'].map(spy_return_map)

        # Check if the SPY Excess Return is correctly added
        st.write(all_data.head())  # Optional: To inspect the first few rows of your data

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

elif is_code_valid is False:
    st.error("Please enter a valid code.")
