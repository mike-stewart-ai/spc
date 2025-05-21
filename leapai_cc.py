# PikPak Accuracy Control Charts Dashboard (Streamlit Version)

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timedelta
import os

# --- SETTINGS ---
file_path = "PikPak Pick Accuracy.xlsx"

if not os.path.isfile(file_path):
    st.error("No valid file path found. Please ensure 'PikPak Pick Accuracy.xlsx' exists in the app directory.")
    st.stop()

sheets_to_plot = ["EVG #006", "EVG #007", "LWS #010"]

# --- FUNCTIONS ---
def load_machine_products(file_path, machine):
    try:
        df = pd.read_excel(file_path, sheet_name=machine)
        if 'Product' not in df.columns:
            return ['All Products']
        products = df['Product'].dropna().unique().tolist()
        return ['All Products'] + sorted([p for p in products if str(p).strip()])
    except Exception as e:
        st.error(f"Error loading products for {machine}: {str(e)}")
        return ['All Products']

def load_machine_data(machine):
    try:
        df = pd.read_excel(file_path, sheet_name=machine, parse_dates=['Date'])
        return df
    except Exception as e:
        st.error(f"Error loading data for {machine}: {e}")
        return pd.DataFrame(columns=['Date', 'Product', 'Status'])

def filter_data_by_product(df, product):
    if product == 'All Products' or 'Product' not in df.columns:
        return df
    return df[df['Product'] == product]

def load_events():
    try:
        df = pd.read_excel(file_path, sheet_name='Events', parse_dates=['Date'])
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        return df
    except Exception as e:
        st.warning(f"Error loading events: {e}")
        return pd.DataFrame(columns=['Date', 'Machine', 'Description', 'Recalculate Mean (Yes/No)'])

def calculate_control_limits(segment_data, usl=None, lsl=None):
    p_bar = segment_data['Bad Picks'].sum() / segment_data['Total Picks'].sum()
    centerline = p_bar * 100
    mu = segment_data['Bad %'].mean()
    sigma = segment_data['Bad %'].std(ddof=1)
    cpk = None
    if usl is not None and lsl is not None and sigma > 0:
        cpu = (usl - mu) / (3 * sigma)
        cpl = (mu - lsl) / (3 * sigma)
        cpk = min(cpu, cpl)
    avg_sample_size = segment_data['Total Picks'].mean()
    ucl = (p_bar + 3 * np.sqrt(p_bar * (1 - p_bar) / avg_sample_size)) * 100
    lcl = max((p_bar - 3 * np.sqrt(p_bar * (1 - p_bar) / avg_sample_size)) * 100, 0)
    return centerline, ucl, lcl, cpk

def plot_chart(data, events, machine, product, chart_type, usl, lsl, detect_rules, show_events, event_dates):
    fig, ax = plt.subplots(figsize=(14, 7))

    daily_summary = data.groupby('Date').agg({'Bad Picks': 'sum', 'Total Picks': 'sum'}).reset_index()
    daily_summary['Bad %'] = daily_summary['Bad Picks'] / daily_summary['Total Picks'] * 100

    relevant_events = events[(events['Machine'] == machine) & (events['Recalculate Mean (Yes/No)'].str.upper() == 'YES')]
    if not relevant_events.empty:
        last_recalc_date = relevant_events['Date'].max()
        recalculation_data = data[data['Date'] <= last_recalc_date]
    else:
        recalculation_data = data

    summary_for_calc = recalculation_data.groupby('Date').agg({'Bad Picks': 'sum', 'Total Picks': 'sum'}).reset_index()
    summary_for_calc['Bad %'] = summary_for_calc['Bad Picks'] / summary_for_calc['Total Picks'] * 100

    centerline, ucl, lcl, cpk = calculate_control_limits(summary_for_calc, usl, lsl)
    ax.plot(daily_summary['Date'], daily_summary['Bad %'], marker='o', linestyle='-', color='blue')
    ax.plot(daily_summary['Date'], [ucl] * len(daily_summary), 'r--', label=f"UCL = {ucl:.2f}%")
    ax.plot(daily_summary['Date'], [lcl] * len(daily_summary), 'r--', label=f"LCL = {lcl:.2f}%")
    ax.plot(daily_summary['Date'], [centerline] * len(daily_summary), 'g--', label=f"Centerline = {centerline:.2f}%")

    ax.set_title(f"{machine} - {product} Control Chart")
    ax.set_xlabel("Date")
    ax.set_ylabel("Bad %")
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MONDAY))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%y'))
    ax.grid(True)
    ax.legend()

    return fig

# --- STREAMLIT APP ---

with st.expander("ℹ️ Help: Detection Rules", expanded=False):
    st.markdown("""
    This dashboard applies four key statistical rules to help detect signals in your process:

    - **Outside Limits**: One point beyond the upper or lower control limits.
    - **Zone Shift**: 8 or more consecutive points on one side of the centerline.
    - **Trend**: 6 or more points trending upward or downward.
    - **Alternating**: 14 or more points alternating up and down.

    Enable **Detection Rules** in the sidebar to highlight these conditions on the control chart.
    """)

st.title("PikPak Accuracy Control Charts Dashboard")

with st.sidebar:
    with st.form(key="chart_form"):
        machine = st.selectbox("Select Machine", sheets_to_plot)
        if machine:
            product_list = load_machine_products(file_path, machine)
        else:
            product_list = ['All Products']

        product = st.selectbox("Select Product", product_list)

        from datetime import date
        default_start = date.today() - timedelta(days=30)
        default_end = date.today()
        date_range = st.date_input("Date Range", value=(default_start, default_end))

        usl = st.number_input("USL (% Bad)", value=2.0)
        lsl = st.number_input("LSL (% Bad)", value=0.0)

        detect_rules = st.checkbox("Enable Detection Rules")
        show_events = st.checkbox("Show Events")

        submitted = st.form_submit_button("Update Chart")

if submitted:
    df = load_machine_data(machine)
    df = filter_data_by_product(df, product)
    if df.empty:
        st.warning("No data available for the selected product.")
    else:
        events = load_events()
        fig = plot_chart(df, events, machine, product, "Shewhart", None, usl, lsl, detect_rules, show_events, [])
        st.pyplot(fig)




with st.container():
    if submitted and machine:
        df = load_machine_data(machine)
        df['Date'] = df['Date'].dt.normalize()
        df['Total Picks'] = 1
        df['Bad Picks'] = df['Status'].apply(lambda x: 1 if x == 'Bad' else 0)
        df = filter_data_by_product(df, product)

        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date = pd.to_datetime(date_range[0])
            end_date = pd.to_datetime(date_range[1])
            df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]

        if df.empty:
            st.warning("No data available for selected filters.")
        else:
            events = load_events()
            recalc_date = st.date_input("Add Recalculation Date(s)", [])
            event_dates = recalc_date if isinstance(recalc_date, list) else [recalc_date]
            chart = plot_chart(df, events, machine, product, "Shewhart", usl, lsl, detect_rules, show_events, event_dates)
            st.session_state['chart'] = chart

            if chart:
                st.pyplot(chart)
            else:
                st.warning("No chart was generated. Check input filters or data.")

            if 'chart' in st.session_state and st.session_state['chart'] is not None:
                if st.button("Save Chart as PNG"):
                    filename = f"ControlChart_{machine}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    st.session_state['chart'].savefig(filename, dpi=300, bbox_inches='tight')
                    st.success(f"Chart saved as {filename}")
