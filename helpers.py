import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime

def parse_trade_number_input(input_string):
    """
    Parses the trade number input string and returns a list of trade numbers.
    Supports individual numbers and ranges (e.g., '0-19, 24-25, 98').
    """
    trade_numbers = []
    for part in input_string.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            if start > end:
                raise ValueError(f"Invalid range: {start}-{end}. Start must be less than end.")
            trade_numbers.extend(range(start, end + 1))
        else:
            trade_numbers.append(int(part.strip()))
    return trade_numbers

def load_tick_data(file_path):
    """
    Loads tick data (OHLC data) from a CSV file, adjusts for daylight saving time, and sets the DateTime column as the index.
    """
    tf_ohlc_data = pd.read_csv(file_path)
    tf_ohlc_data['DateTime'] = pd.to_datetime(tf_ohlc_data['DateTime'])

    # Adjust for daylight saving time starting from 2024-03-31
    dst_start = pd.Timestamp('2024-03-31 00:00:00')
    tf_ohlc_data['DateTime'] = tf_ohlc_data['DateTime'].apply(lambda dt: dt + pd.Timedelta(hours=1) if dt >= dst_start else dt)

    tf_ohlc_data.set_index('DateTime', inplace=True)
    return tf_ohlc_data

def load_trade_data(file_path):
    """
    Loads trade data from a CSV file, parses date columns, and adjusts trade times.
    Args:
        file_path (str): Path to the trade data CSV file.
    Returns:
        pd.DataFrame: DataFrame containing the trade data with adjusted times.
    """
    trade_data = pd.read_csv(file_path)
    trade_data['Open Time'] = pd.to_datetime(trade_data['Open Time'], format='%Y-%m-%d %H:%M')
    trade_data['Close Time'] = pd.to_datetime(trade_data['Close Time'], format='%Y-%m-%d %H:%M')
    
    # Adjust the trade times
    trade_data = adjust_trade_times(trade_data, hours_offset=-2)
    
    trade_data['Open DateTime'] = trade_data['Open Time']
    trade_data['Close DateTime'] = trade_data['Close Time']
    return trade_data

def filter_initial_trades(df):
    initial_trades = df.groupby('Close DateTime').first().reset_index()
    return initial_trades

def align_datetime_to_candle(dt, timeframe):
    """Aligns datetime to the start of the candlestick based on the timeframe."""
    if timeframe == 1:
        dt = dt.replace(second=0, microsecond=0)
    elif timeframe == 5:
        intervals = dt.minute // 5
        dt = dt.replace(minute=intervals * 5, second=0, microsecond=0)
    elif timeframe == 15:
        intervals = dt.minute // 15
        dt = dt.replace(minute=intervals * 15, second=0, microsecond=0)
    elif timeframe == 60:
        dt = dt.replace(minute=0, second=0, microsecond=0)
    elif timeframe == 240:
        intervals = dt.hour // 4
        dt = dt.replace(hour=intervals * 4, minute=0, second=0, microsecond=0)
    elif timeframe == 1440:
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)

    return dt

def adjust_start_end_datetimes(start_dt, end_dt, selected_timeframe, tf_ohlc_data):
    """Adjusts the start and end datetimes for the chart based on user input."""
    start_dt = align_datetime_to_candle(start_dt, selected_timeframe)
    end_dt = align_datetime_to_candle(end_dt, selected_timeframe)
    return (max(start_dt, tf_ohlc_data.index[0]), min(end_dt, tf_ohlc_data.index[-1]))

def create_candlestick_figure(filtered_data):
    """Creates the candlestick figure with the filtered data."""
    fig = go.Figure(data=[go.Candlestick(
        x=filtered_data.index,
        open=filtered_data['Open'],
        high=filtered_data['High'],
        low=filtered_data['Low'],
        close=filtered_data['Close'],
        name='Price'
    )])
    return fig

def add_price_markers(fig, start_dt, end_dt, open_price, close_price, trade_type):
    """Adds markers for open and Closing Prices to the figure."""

    fig.add_trace(go.Scatter(
        x=[start_dt],
        y=[open_price],
        mode='markers',
        marker_symbol='triangle-up' if trade_type == 'buy' else 'triangle-down',
        marker_color='blue' if trade_type == 'buy' else 'red',
        marker_size=10,
        name='Opening Price Marker'
    ))

    fig.add_trace(go.Scatter(
        x=[end_dt],
        y=[close_price],
        mode='markers',
        marker_symbol='triangle-down' if trade_type == 'buy' else 'triangle-up',
        marker_color='white',
        marker_size=10,
        name='Closing Price Marker'
    ))

    return fig

def add_lot_sizes(fig, start_dt, end_dt, volume, open_price):
    """Adds texts for position lot sizes to the figure."""
    fig.add_annotation(text=str(volume), x=start_dt, y=open_price, align="left")
    return fig

def create_candlestick_chart(tf_ohlc_data, selected_trades, selected_timeframe, input_settings):
    # Determine the number of minutes for the selected timeframe
    timeframe_minutes = {
        '1M': 1,
        '5M': 5,
        '15M': 15,
        '1H': 60,
        '4H': 240,
        '1D': 1440
    }

    first_trade_start_datetime, last_trade_end_datetime = adjust_start_end_datetimes(selected_trades["Open DateTime"].iloc[0], selected_trades["Close DateTime"].iloc[-1], timeframe_minutes[selected_timeframe], tf_ohlc_data)

    # Filter the data for the chart
    chart_start_datetime = first_trade_start_datetime - pd.Timedelta(minutes=timeframe_minutes[selected_timeframe] * input_settings["Candles Before"])
    chart_end_datetime = last_trade_end_datetime + pd.Timedelta(minutes=timeframe_minutes[selected_timeframe] * input_settings["Candles After"])
    filtered_data = tf_ohlc_data.loc[chart_start_datetime:chart_end_datetime]
    # Create the candlestick figure and add markers and lines
    fig = create_candlestick_figure(filtered_data)

    for index, trade in selected_trades.iterrows():
        trade_start_datetime, trade_end_datetime = adjust_start_end_datetimes(trade["Open DateTime"], trade["Close DateTime"], timeframe_minutes[selected_timeframe], tf_ohlc_data)
        fig = add_price_markers(fig, trade_start_datetime, trade_end_datetime, trade["Opening Price"], trade["Closing Price"], trade["Type"])
        if input_settings["Showing Position Lot Size"]:
            fig = add_lot_sizes(fig, trade_start_datetime, trade_end_datetime, trade["Volume"], trade["Opening Price"])
    
    fig.update_layout(
        title={
            'text': 'Trade Progress',
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        },
        xaxis_title='Time',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        showlegend=False
    )

    if input_settings["Display RSI?"]:
        fig = add_rsi(fig, tf_ohlc_data, chart_start_datetime, chart_end_datetime, timeframe_minutes[selected_timeframe], input_settings["RSI Length"])

    if input_settings["Display Bollinger Bands?"]:
        upper_band, middle_band, lower_band = calculate_bollinger_bands(tf_ohlc_data, input_settings["Bollinger Bands Period"], input_settings["Bollinger Bands Std. Dev"])
        fig = add_bollinger_bands(fig, upper_band, middle_band, lower_band, chart_start_datetime, chart_end_datetime)
    
    # Remove gaps from chart
    fig.update_layout(xaxis_type='category')

    return fig

def calculate_rsi(data, period):
    delta = data['Close'].diff()
    gain = ((delta > 0) * delta).fillna(0)
    loss = ((delta < 0) * -delta).fillna(0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def add_rsi(fig, tf_ohlc_data, chart_start_datetime, chart_end_datetime, timeframe_minutes, period):
    # Calculate RSI
    start_rsi_datetime = chart_start_datetime - pd.Timedelta(minutes=timeframe_minutes * period)
    rsi = calculate_rsi(tf_ohlc_data.loc[start_rsi_datetime:chart_end_datetime], period)
    rsi = rsi[chart_start_datetime:chart_end_datetime]

    # Create a subplot with 2 rows
    new_fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                        row_heights=[0.75, 0.25])

    # Move existing traces to the new subplot
    for trace in fig.data:
        new_fig.add_trace(trace, row=1, col=1)

    # Copy annotations to the new figure, adjusting the yref to the new subplot if necessary
    if fig.layout.annotations:
        for annotation in fig.layout.annotations:
            new_fig.add_annotation(annotation, row=1, col=1)
        
    # Add RSI trace to the second subplot
    new_fig.add_trace(
        go.Scatter(x=rsi.index, y=rsi, mode='lines', name='RSI', line=dict(color='cyan', width=2),),
        row=2, col=1
    )

    # Customize layout for RSI subplot
    new_fig.update_yaxes(title_text='Price', row=1, col=1)
    new_fig.update_yaxes(title_text='RSI', range=[0, 100], fixedrange=True, row=2, col=1)
    new_fig.update_xaxes(title_text='Time', row=2, col=1)
    new_fig.update_layout(xaxis2_type='category', # Remove gaps from RSI chart
                          title={
                                'text': 'Trade Progress',
                                'x':0.5,
                                'xanchor': 'center',
                                'yanchor': 'top'
                            },
                          xaxis1_rangeslider_visible=False, 
                          showlegend=False)
    return new_fig

def calculate_bollinger_bands(data, period=20, num_of_std=2):
    middle_band = data['Close'].rolling(window=period).mean()
    std_dev = data['Close'].rolling(window=period).std()
    upper_band = middle_band + (std_dev * num_of_std)
    lower_band = middle_band - (std_dev * num_of_std)
    
    return upper_band, middle_band, lower_band

def add_bollinger_bands(fig, upper_band, middle_band, lower_band, start_datetime, end_datetime):
    upper_band = upper_band[start_datetime:end_datetime]
    middle_band = middle_band[start_datetime:end_datetime]
    lower_band = lower_band[start_datetime:end_datetime]
    
    fig.add_trace(go.Scatter(x=upper_band.index, y=upper_band, line=dict(color='rgba(76, 175, 80, 0.5)'), name='Upper Bollinger Band'))
    fig.add_trace(go.Scatter(x=middle_band.index, y=middle_band, line=dict(color='rgba(240, 173, 78, 0.5)'), name='Middle Bollinger Band'))
    fig.add_trace(go.Scatter(x=lower_band.index, y=lower_band, line=dict(color='rgba(76, 175, 80, 0.5)'), name='Lower Bollinger Band'))
    
    return fig

def adjust_trade_times(df, hours_offset=-2):
    """
    Adjusts the Open Time and Close Time columns by the specified number of hours.
    Args:
        df (pd.DataFrame): DataFrame containing the trade data.
        hours_offset (int): Number of hours to adjust the times by. Default is -2.
    Returns:
        pd.DataFrame: DataFrame with adjusted Open Time and Close Time.
    """
    df['Open Time'] = df['Open Time'] + pd.Timedelta(hours=hours_offset)
    df['Close Time'] = df['Close Time'] + pd.Timedelta(hours=hours_offset)
    return df

def group_trades_into_signals(trade_data):
    """
    Groups trades into signals based on their type and closing time.
    Args:
        trade_data (pd.DataFrame): DataFrame containing the trade data.
    Returns:
        pd.DataFrame: DataFrame with an additional column indicating the signal group.
    """
    trade_data = trade_data.sort_values(by='Open DateTime')
    trade_data['Signal Group'] = (trade_data['Type'] != trade_data['Type'].shift()).cumsum()
    
    for _, group in trade_data.groupby('Signal Group'):
        close_time = group['Close DateTime'].max()
        trade_data.loc[group.index, 'Signal Close Time'] = close_time

    return trade_data

def calculate_mean_pips_away(trade_data):
    """
    Calculates the mean pips away from the open price of the first trade in each signal and counts the number of trades.
    Args:
        trade_data (pd.DataFrame): DataFrame containing the trade data.
    Returns:
        pd.DataFrame: DataFrame with the mean pips away and trade count for each signal.
    """
    signals = trade_data.groupby('Signal Group')
    mean_pips_away_list = []

    for signal_group, trades in signals:
        first_open_price = trades.iloc[0]['Opening Price']
        trades['Pips Away'] = (trades['Opening Price'] - first_open_price) * 10000  # Assuming pip calculation for GBPUSD
        mean_pips_away = trades['Pips Away'].mean()
        trade_count = trades.shape[0]
        mean_pips_away_list.append({
            'Signal Group': signal_group, 
            'Mean Pips Away': mean_pips_away, 
            'Trade Count': trade_count
        })

    return pd.DataFrame(mean_pips_away_list)


def calculate_median_pips_away(trade_data):
    """
    Calculates the median pips away from the open price of the first trade in each signal and counts the number of trades.
    Args:
        trade_data (pd.DataFrame): DataFrame containing the trade data.
    Returns:
        pd.DataFrame: DataFrame with the median pips away and trade count for each signal.
    """
    signals = trade_data.groupby('Signal Group')
    median_pips_away_list = []

    for signal_group, trades in signals:
        first_open_price = trades.iloc[0]['Opening Price']
        trades['Pips Away'] = (trades['Opening Price'] - first_open_price) * 10000  # Assuming pip calculation for GBPUSD
        median_pips_away = trades['Pips Away'].median()
        trade_count = trades.shape[0]
        median_pips_away_list.append({
            'Signal Group': signal_group, 
            'Median Pips Away': median_pips_away, 
            'Trade Count': trade_count
        })

    return pd.DataFrame(median_pips_away_list)

def calculate_daily_profits(trade_data):
    """
    Calculates the daily profits from the trade data.
    Args:
        trade_data (pd.DataFrame): DataFrame containing the trade data.
    Returns:
        pd.DataFrame: DataFrame with the daily profits.
    """
    trade_data['Close Date'] = trade_data['Close DateTime'].dt.date
    daily_profits = trade_data.groupby('Close Date')['Profit'].sum().reset_index()
    daily_profits['Close Date'] = pd.to_datetime(daily_profits['Close Date'])
    return daily_profits


def calculate_cumulative_volume(trade_data):
    """
    Calculates the cumulative volume for each signal.
    Args:
        trade_data (pd.DataFrame): DataFrame containing the trade data.
    Returns:
        pd.DataFrame: DataFrame with the cumulative volume for each signal.
    """
    cumulative_volume_df = trade_data.groupby('Signal Group')['Volume'].sum().reset_index()
    return cumulative_volume_df


def calculate_cumulative_trades_per_signal(trade_data):
    """
    Calculates the cumulative number of trades for each signal.
    Args:
        trade_data (pd.DataFrame): DataFrame containing the trade data.
    Returns:
        pd.DataFrame: DataFrame with the cumulative number of trades for each signal.
    """
    cumulative_trades_df = trade_data.groupby('Signal Group').size().reset_index(name='Trade Count')
    return cumulative_trades_df



def calculate_initial_trade_volume(trade_data):
    """
    Calculates the volume of the initial trade in each signal.
    Args:
        trade_data (pd.DataFrame): DataFrame containing the trade data.
    Returns:
        pd.DataFrame: DataFrame with the volume of the initial trade for each signal.
    """
    initial_trades = trade_data.groupby('Signal Group').first().reset_index()
    initial_trade_volume_df = initial_trades[['Signal Group', 'Volume']]
    return initial_trade_volume_df

def calculate_max_pip_drawdown(trade_data, tf_ohlc_data):
    """
    Calculates the maximum pip drawdown for the initial trade in each signal.
    Args:
        trade_data (pd.DataFrame): DataFrame containing the trade data.
        tf_ohlc_data (pd.DataFrame): DataFrame containing the OHLC data.
    Returns:
        pd.DataFrame: DataFrame with the maximum pip drawdown for each signal.
    """
    initial_trades = trade_data.groupby('Signal Group').first().reset_index()
    
    drawdowns = []
    
    for _, trade in initial_trades.iterrows():
        trade_open_time = trade['Open DateTime']
        trade_close_time = trade['Close DateTime']
        open_price = trade['Opening Price']
        
        # Filter OHLC data for the period of the trade
        trade_ohlc_data = tf_ohlc_data[(tf_ohlc_data.index >= trade_open_time) & (tf_ohlc_data.index <= trade_close_time)]
        
        if trade['Type'] == 'buy':
            max_drawdown = (trade_ohlc_data['Low'].min() - open_price) * 10000
        else:
            max_drawdown = (open_price - trade_ohlc_data['High'].max()) * 10000
        
        drawdowns.append({
            'Signal Group': trade['Signal Group'],
            'Max Pip Drawdown': max_drawdown
        })
    
    return pd.DataFrame(drawdowns)
