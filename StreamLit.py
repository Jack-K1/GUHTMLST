import streamlit as st
import pandas as pd
import plotly.express as px
from helpers import (
    load_trade_data,
    load_tick_data,
    parse_trade_number_input,
    filter_initial_trades,
    group_trades_into_signals,
    calculate_mean_pips_away,
    calculate_median_pips_away,
    create_candlestick_chart,
    adjust_trade_times,
    calculate_daily_profits,
    calculate_cumulative_volume,
    calculate_cumulative_trades_per_signal,
    calculate_initial_trade_volume,
    calculate_max_pip_drawdown
)

def load_all_trades(file_path):
    """Loads all trade data from a specified CSV file."""
    return load_trade_data(file_path)

def filter_trades(all_trade_data_df, trade_numbers, desired_columns):
    """Filters the trades based on the input trade numbers."""
    trade_data_dfs = []
    for trade_number in trade_numbers:
        trade_data_df = all_trade_data_df[all_trade_data_df['Trade Number'] == trade_number]
        if not trade_data_df.empty:
            trade_data_df = trade_data_df[desired_columns]
            trade_data_dfs.append(trade_data_df)
    return trade_data_dfs

def get_input_settings():
    """Collects various display and indicator settings from the user."""
    input_settings = {
        "Candles Before": st.number_input('Candles Before Trade', min_value=0, value=5),
        "Candles After": st.number_input('Candles After Trade', min_value=0, value=5),
        "Showing Position Lot Size": st.checkbox('Show Position Lot Size?'),
        "Showing Hedges": st.checkbox('Show Hedges?', value=True),
        "Display RSI?": st.checkbox("Display RSI?", value=False),
        "Display Bollinger Bands?": st.checkbox('Display Bollinger Bands?', value=False)
    }
    if input_settings["Display RSI?"]:
        input_settings["RSI Length"] = st.number_input("RSI Length", value=21, min_value=1)
    if input_settings["Display Bollinger Bands?"]:
        input_settings["Bollinger Bands Period"] = st.number_input('Bollinger Bands Period', min_value=1, value=20)
        input_settings["Bollinger Bands Std. Dev"] = st.number_input('Bollinger Bands Std. Dev', value=2)
    return input_settings

def calculate_average_prices(trade_agg_data):
    """Calculates unweighted and weighted average prices."""
    unweighted_average_opening_price = trade_agg_data["Opening Price"].mean()
    unweighted_average_closing_price = trade_agg_data["Closing Price"].mean()

    weighted_average_opening_price = (trade_agg_data["Opening Price"] * trade_agg_data["Volume"]).sum() / trade_agg_data["Volume"].sum()
    weighted_average_closing_price = (trade_agg_data["Closing Price"] * trade_agg_data["Volume"]).sum() / trade_agg_data["Volume"].sum()

    unweighted_difference = unweighted_average_closing_price - unweighted_average_opening_price
    weighted_difference = weighted_average_closing_price - weighted_average_opening_price

    average_price_data_df = pd.DataFrame({
        'Open Price': {
            'Unweighted': unweighted_average_opening_price,
            'Lotsize-weighted': weighted_average_opening_price
        },
        'Closing Price': {
            'Unweighted': unweighted_average_closing_price,
            'Lotsize-weighted': weighted_average_closing_price
        },
        'Difference': {
            'Unweighted': unweighted_difference,
            'Lotsize-weighted': weighted_difference
        }
    })
    return average_price_data_df

def main():
    st.title('GBPUSD Trade Viewer')

    trade_numbers_input = st.text_input('Enter trade sequence numbers from 1 to 216', value="0")
    try:
        if trade_numbers_input == "":
            raise ValueError("Enter trade number(s)")
        trade_numbers = parse_trade_number_input(trade_numbers_input)
        trade_numbers = sorted(set(trade_numbers))
    except ValueError as e:
        st.error(f"Invalid input: {e}")
        st.stop()

    selected_timeframe = st.radio("Select Timeframe", ('1M', '5M', '15M', '1H', '4H', '1D'))
    file_mapping = {
        '1M': 'GUM1_OHLC_dropnaCSV.csv',
        '5M': 'GUM5_OHLC_dropnaCSV.csv',
        '15M': 'GUM15_OHLC_dropnaCSV.csv',
        '1H': 'GUH1_OHLC_dropnaCSV.csv',
        '4H': 'GUH4_OHLC_dropnaCSV.csv',
        '1D': 'GUD1_OHLC_dropnaCSV.csv'
    }
    desired_columns = [
        'Trade Number', 'Open DateTime', 'Opening Price', 'Type', 'Volume',
        'S / L', 'T / P', 'Close DateTime', 'Closing Price', 'Profit'
    ]

    all_trades_file_path = 'trades/trade_0.csv'
    all_trade_data_df = load_all_trades(all_trades_file_path)
    trade_data_dfs = filter_trades(all_trade_data_df, trade_numbers, desired_columns)

    if not trade_data_dfs:
        st.write("No valid trades selected.")
        st.stop()

    tick_data_file_path = file_mapping[selected_timeframe]
    tf_ohlc_data = load_tick_data(tick_data_file_path)
    input_settings = get_input_settings()

    trade_agg_data = pd.concat(trade_data_dfs).reset_index(drop=True)
    if not input_settings["Showing Hedges"]:
        trade_agg_data = filter_initial_trades(trade_agg_data)
        trade_agg_data = trade_agg_data[desired_columns]

    trade_agg_data = group_trades_into_signals(trade_agg_data)
    mean_pips_away_df = calculate_mean_pips_away(trade_agg_data)
    median_pips_away_df = calculate_median_pips_away(trade_agg_data)

    # Calculate daily profits
    daily_profits_df = calculate_daily_profits(trade_agg_data)

    # Calculate statistics for daily profits
    daily_profit_mean = daily_profits_df['Profit'].mean()
    daily_profit_median = daily_profits_df['Profit'].median()

    # Calculate cumulative volume by signal
    cumulative_volume_df = calculate_cumulative_volume(trade_agg_data)

    # Calculate statistics for cumulative volume
    volume_mean = cumulative_volume_df['Volume'].mean()
    volume_median = cumulative_volume_df['Volume'].median()
    volume_max = cumulative_volume_df['Volume'].max()
    volume_min = cumulative_volume_df['Volume'].min()

    # Calculate cumulative trades per signal
    cumulative_trades_df = calculate_cumulative_trades_per_signal(trade_agg_data)

    # Calculate statistics for cumulative trades per signal
    trades_mean = cumulative_trades_df['Trade Count'].mean()
    trades_median = cumulative_trades_df['Trade Count'].median()
    trades_max = cumulative_trades_df['Trade Count'].max()
    trades_min = cumulative_trades_df['Trade Count'].min()

    # Calculate initial trade volume per signal
    initial_trade_volume_df = calculate_initial_trade_volume(trade_agg_data)

    # Calculate statistics for initial trade volume per signal
    initial_volume_mean = initial_trade_volume_df['Volume'].mean()
    initial_volume_median = initial_trade_volume_df['Volume'].median()
    initial_volume_max = initial_trade_volume_df['Volume'].max()
    initial_volume_min = initial_trade_volume_df['Volume'].min()

    # Calculate max pip drawdown for initial trades
    max_pip_drawdown_df = calculate_max_pip_drawdown(trade_agg_data, tf_ohlc_data)

    # Calculate statistics for max pip drawdown
    drawdown_mean = max_pip_drawdown_df['Max Pip Drawdown'].mean()
    drawdown_median = max_pip_drawdown_df['Max Pip Drawdown'].median()
    drawdown_max = max_pip_drawdown_df['Max Pip Drawdown'].max()
    drawdown_min = max_pip_drawdown_df['Max Pip Drawdown'].min()

    # Display the candlestick chart first
    chart = create_candlestick_chart(tf_ohlc_data, trade_agg_data, selected_timeframe, input_settings)
    st.plotly_chart(chart, use_container_width=True)

    # Display the mean pips away chart
    fig_mean = px.bar(
        mean_pips_away_df, 
        x='Trade Count', 
        y='Mean Pips Away', 
        title='Mean Pips Away from First Trade in Signal',
        text='Trade Count'
    )
    fig_mean.update_traces(textposition='outside')
    st.plotly_chart(fig_mean, use_container_width=True)

    # Display the median pips away chart
    fig_median = px.bar(
        median_pips_away_df, 
        x='Trade Count', 
        y='Median Pips Away', 
        title='Median Pips Away from First Trade in Signal',
        text='Trade Count'
    )
    fig_median.update_traces(textposition='outside')
    st.plotly_chart(fig_median, use_container_width=True)

    # Display the histogram of daily profits
    fig_hist = px.histogram(
        daily_profits_df, 
        x='Profit', 
        nbins=20, 
        title='Histogram of Daily Profits',
        labels={'count': 'Number of Days'}
    )
    fig_hist.update_layout(yaxis_title='Number of Days')
    st.plotly_chart(fig_hist, use_container_width=True)

    # Display daily profit statistics
    st.write(f"Mean Daily Profit: ${daily_profit_mean:.2f}")
    st.write(f"Median Daily Profit: ${daily_profit_median:.2f}")

    # Display the histogram of cumulative volume
    fig_vol_hist = px.histogram(
        cumulative_volume_df,
        x='Volume',
        nbins=20,
        title='Histogram of Cumulative Volume by Signal'
    )
    fig_vol_hist.update_layout(yaxis_title='Number of Signals')
    st.plotly_chart(fig_vol_hist, use_container_width=True)

    # Display volume statistics
    st.write(f"Mean Volume: {volume_mean:.2f}")
    st.write(f"Median Volume: {volume_median:.2f}")
    st.write(f"Maximum Volume: {volume_max:.2f}")
    st.write(f"Minimum Volume: {volume_min:.2f}")

    # Display the histogram of cumulative trades per signal
    fig_trades_hist = px.histogram(
        cumulative_trades_df,
        x='Trade Count',
        nbins=20,
        title='Histogram of Cumulative Trades per Signal'
    )
    fig_trades_hist.update_layout(yaxis_title='Number of Signals')
    st.plotly_chart(fig_trades_hist, use_container_width=True)

    # Display trade count statistics
    st.write(f"Mean Trades per Signal: {trades_mean:.2f}")
    st.write(f"Median Trades per Signal: {trades_median:.2f}")
    st.write(f"Maximum Trades per Signal: {trades_max:.2f}")
    st.write(f"Minimum Trades per Signal: {trades_min:.2f}")

    # Display the histogram of initial trade volume per signal
    fig_initial_vol_hist = px.histogram(
        initial_trade_volume_df,
        x='Volume',
        nbins=20,
        title='Histogram of Initial Trade Volume by Signal'
    )
    fig_initial_vol_hist.update_layout(yaxis_title='Number of Signals')
    st.plotly_chart(fig_initial_vol_hist, use_container_width=True)

    # Display initial trade volume statistics
    st.write(f"Mean Initial Trade Volume: {initial_volume_mean:.2f}")
    st.write(f"Median Initial Trade Volume: {initial_volume_median:.2f}")
    st.write(f"Maximum Initial Trade Volume: {initial_volume_max:.2f}")
    st.write(f"Minimum Initial Trade Volume: {initial_volume_min:.2f}")

    # Display the histogram of max pip drawdown per signal
    fig_drawdown_hist = px.histogram(
        max_pip_drawdown_df,
        x='Max Pip Drawdown',
        nbins=20,
        title='Histogram of Max Pip Drawdown by Signal'
    )
    fig_drawdown_hist.update_layout(yaxis_title='Number of Signals')
    st.plotly_chart(fig_drawdown_hist, use_container_width=True)

    # Display max pip drawdown statistics
    st.write(f"Mean Max Pip Drawdown: {drawdown_mean:.2f}")
    st.write(f"Median Max Pip Drawdown: {drawdown_median:.2f}")
    st.write(f"Maximum Max Pip Drawdown: {drawdown_max:.2f}")
    st.write(f"Minimum Max Pip Drawdown: {drawdown_min:.2f}")

    if input_settings["Showing Hedges"]:
        average_price_data_df = calculate_average_prices(trade_agg_data)
        st.table(average_price_data_df)

    st.table(trade_agg_data)

if __name__ == "__main__":
    main()
