# PikPak Accuracy Control Charts Dashboard (Streamlit Version)

import streamlit as st
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('Agg') # Set a non-interactive backend
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timedelta, date
import os
import base64

print("Reached after imports")

# --- SETTINGS ---
file_path = "PikPak Pick Accuracy.xlsx"

# Add debug information
st.write("Current working directory:", os.getcwd())
st.write("Files in directory:", os.listdir())

# Function to load Excel file with better error handling
def load_excel_file(file_path):
    try:
        if not os.path.isfile(file_path):
            st.error(f"File not found: {file_path}")
            st.error(f"Current directory contents: {os.listdir()}")
            return None
        
        # Try to read the file
        df = pd.read_excel(file_path)
        return True
    except Exception as e:
        st.error(f"Error reading Excel file: {str(e)}")
        return False

# Check if we can read the Excel file
if not load_excel_file(file_path):
    st.error("""
    Unable to read the Excel file. Please ensure:
    1. The file 'PikPak Pick Accuracy.xlsx' is in the repository
    2. The file is properly committed and pushed to GitHub
    3. The file is accessible in the Streamlit Cloud environment
    """)
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
        df['Total Picks'] = 1
        df['Bad Picks'] = df['Status'].apply(lambda x: 1 if x == 'Bad' else 0)
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
        # st.write("Debug - All Events:", df)  # Debug line
        return df
    except Exception as e:
        st.warning(f"Error loading events: {e}")
        return pd.DataFrame(columns=['Date', 'Machine', 'Description', 'Recalculate Mean (Yes/No)'])

def calculate_control_limits(segment_data, usl=None, lsl=None):
    total_picks_sum = segment_data['Total Picks'].sum()
    if total_picks_sum == 0:
        # Handle case with no total picks to avoid division by zero
        return 0, 0, 0, None # Or return previous limits, or other default values
        
    p_bar = segment_data['Bad Picks'].sum() / total_picks_sum
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

def detect_violations(segment_data, centerline, ucl, lcl):
    violations = {
        'outside_limits': [],
        'zone_shift': [],
        'trend': [],
        'alternating': []
    }

    # Rule 1: Outside Limits
    for index, row in segment_data.iterrows():
        if row['Bad %'] > ucl or row['Bad %'] < lcl:
            violations['outside_limits'].append(row['Date'])

    # Rule 2: Zone Shift (8 or more consecutive points on one side of centerline)
    consecutive_count = 0
    last_side = None
    shift_start_date = None
    
    for index, row in segment_data.iterrows():
        current_side = 'above' if row['Bad %'] > centerline else 'below'
        
        if last_side == current_side:
            consecutive_count += 1
            if consecutive_count == 8:
                shift_start_date = row['Date']
        else:
            consecutive_count = 1
            last_side = current_side
            
        if consecutive_count >= 8:
            violations['zone_shift'].append(row['Date'])

    # Rule 3: Trend (6 or more points trending up or down)
    trend_count = 0
    trend_direction = None
    trend_start_date = None
    
    for i in range(1, len(segment_data)):
        current_value = segment_data.iloc[i]['Bad %']
        previous_value = segment_data.iloc[i-1]['Bad %']
        
        if trend_direction is None:
            trend_direction = 'up' if current_value > previous_value else 'down'
            trend_count = 2
        elif (trend_direction == 'up' and current_value > previous_value) or \
             (trend_direction == 'down' and current_value < previous_value):
            trend_count += 1
            if trend_count == 6:
                trend_start_date = segment_data.iloc[i-5]['Date']
        else:
            trend_count = 1
            trend_direction = 'up' if current_value > previous_value else 'down'
            
        if trend_count >= 6:
            violations['trend'].append(segment_data.iloc[i]['Date'])

    # Rule 4: Alternating (14 or more points alternating up and down)
    alternating_count = 0
    last_direction = None
    
    for i in range(1, len(segment_data)):
        current_value = segment_data.iloc[i]['Bad %']
        previous_value = segment_data.iloc[i-1]['Bad %']
        current_direction = 'up' if current_value > previous_value else 'down'
        
        if last_direction is None:
            last_direction = current_direction
            alternating_count = 1
        elif last_direction != current_direction:
            alternating_count += 1
            last_direction = current_direction
        else:
            alternating_count = 1
            
        if alternating_count >= 14:
            violations['alternating'].append(segment_data.iloc[i]['Date'])

    return violations

def plot_chart(data, events, machine, product, chart_type, usl, lsl, detect_rules, show_events, user_recalc_dates, include_event_recalcs):
    fig, ax = plt.subplots(figsize=(14, 7))

    daily_summary = data.groupby('Date').agg({'Bad Picks': 'sum', 'Total Picks': 'sum'}).reset_index()
    daily_summary['Bad %'] = daily_summary['Bad Picks'] / daily_summary['Total Picks'] * 100

    # Combine user-selected recalculation dates with event-based recalculation dates conditionally
    event_recalc_dates = []
    if include_event_recalcs:
        event_recalc_dates_df = events[(events['Machine'] == machine) & (events['Recalculate Mean (Yes/No)'].str.upper() == 'YES')].copy()
        event_recalc_dates = event_recalc_dates_df['Date'].tolist()

    # Ensure user_recalc_dates are datetime objects
    user_recalc_dates_dt = [pd.to_datetime(d) for d in user_recalc_dates if d is not None]

    # Use combined dates if include_event_recalcs is True, otherwise just user dates
    all_recalc_dates = sorted(list(set(user_recalc_dates_dt + event_recalc_dates)))

    # Add the start date of the data as the first recalculation point if it's not already there
    if not daily_summary.empty:
        first_data_date = daily_summary['Date'].min()
        if not all_recalc_dates or all_recalc_dates[0] > first_data_date:
             all_recalc_dates.insert(0, first_data_date)

    # Ensure recalculation dates are within the data's date range
    if not daily_summary.empty:
        min_data_date = daily_summary['Date'].min()
        max_data_date = daily_summary['Date'].max()
        all_recalc_dates = [d for d in all_recalc_dates if d >= min_data_date and d <= max_data_date]

    segments = []
    for i in range(len(all_recalc_dates)):
        start_date = all_recalc_dates[i]
        if i + 1 < len(all_recalc_dates):
            end_date = all_recalc_dates[i+1] - timedelta(days=1) # Segment ends the day before the next recalculation
        else:
            end_date = daily_summary['Date'].max() # Last segment goes to the end of the data
        
        # Ensure end_date is not before start_date due to timedelta(days=1) on a recalculation date that is also the max data date
        if end_date < start_date:
             end_date = start_date

        segment_data = daily_summary[(daily_summary['Date'] >= start_date) & (daily_summary['Date'] <= end_date)]
        if not segment_data.empty:
            segments.append({
                'start_date': start_date,
                'end_date': end_date,
                'data': segment_data
            })

    all_centerlines, all_ucls, all_lcls = [], [], []

    for segment in segments:
        centerline, ucl, lcl, cpk = calculate_control_limits(segment['data'], usl, lsl)
        segment['centerline'] = centerline
        segment['ucl'] = ucl
        segment['lcl'] = lcl
        segment['cpk'] = cpk

        # Detect violations if enabled
        if detect_rules:
            segment['violations'] = detect_violations(segment['data'], centerline, ucl, lcl)
        else:
            segment['violations'] = {}

        # Extend control limits across the segment's date range
        segment_dates = segment['data']['Date']
        all_centerlines.extend([(d, centerline) for d in segment_dates])
        all_ucls.extend([(d, ucl) for d in segment_dates])
        all_lcls.extend([(d, lcl) for d in segment_dates])


    # Plotting the data points
    ax.plot(daily_summary['Date'], daily_summary['Bad %'], marker='o', linestyle='-', color='blue', label='Bad %')

    # Highlight violation points with different colors and markers
    if detect_rules:
        violation_colors = {
            'outside_limits': 'red',
            'zone_shift': 'orange',
            'trend': 'purple',
            'alternating': 'green'
        }
        
        for rule, color in violation_colors.items():
            violation_dates = []
            for segment in segments:
                if 'violations' in segment and rule in segment['violations']:
                    violation_dates.extend(segment['violations'][rule])

            if violation_dates:
                violation_points = daily_summary[daily_summary['Date'].isin(violation_dates)]
                if not violation_points.empty:
                    rule_label = rule.replace('_', ' ').title()
                    ax.plot(violation_points['Date'], violation_points['Bad %'], 
                           marker='o', linestyle='', color=color, markersize=8, 
                           label=f'{rule_label} Violation')

    # Plotting the segmented control limits
    if all_ucls:
        all_ucls.sort()
        ucl_dates, ucl_values = zip(*all_ucls)
        # Get the last calculated UCL value for the legend
        last_ucl = segments[-1]['ucl'] if segments else 0
        ax.plot(ucl_dates, ucl_values, 'r--', label=f"UCL = {last_ucl:.2f}%") # Include value in legend

    if all_lcls:
        all_lcls.sort()
        lcl_dates, lcl_values = zip(*all_lcls)
        # Get the last calculated LCL value for the legend
        last_lcl = segments[-1]['lcl'] if segments else 0
        ax.plot(lcl_dates, lcl_values, 'r--', label=f"LCL = {last_lcl:.2f}%") # Include value in legend

    if all_centerlines:
        all_centerlines.sort()
        centerline_dates, centerline_values = zip(*all_centerlines)
        # Get the last calculated Centerline value for the legend
        last_centerline = segments[-1]['centerline'] if segments else 0
        ax.plot(centerline_dates, centerline_values, 'g--', label=f"Centerline = {last_centerline:.2f}%") # Include value in legend

    # Add Cpk to the legend
    if segments and segments[-1]['cpk'] is not None:
        last_cpk = segments[-1]['cpk']
        # Use an invisible line to add Cpk to the legend
        ax.plot([], [], ' ', label=f"Cpk = {last_cpk:.2f}")

    ax.set_title(f"{machine} - {product} Control Chart")
    ax.set_xlabel("Date")
    ax.set_ylabel("Bad %")
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MONDAY))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m-%Y'))
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True)
    ax.legend()

    # Add events to the chart if show_events is True
    if show_events and not events.empty:
        machine_events = events[events['Machine'] == machine].copy()
        # Ensure event dates are in the data's date range that is currently displayed
        min_data_date = daily_summary['Date'].min()
        max_data_date = daily_summary['Date'].max()
        machine_events = machine_events[(machine_events['Date'] >= min_data_date) & (machine_events['Date'] <= max_data_date)].copy()

        for index, event in machine_events.iterrows():
            event_date = event['Date']
            description = event['Description']

            # Find the closest date in daily_summary to the event_date
            # Ensure the closest date is within the currently displayed data range
            closest_date_index = daily_summary['Date'].sub(event_date).abs().idxmin()
            closest_date_data = daily_summary.loc[closest_date_index]

            y_pos = closest_date_data['Bad %']
            x_pos = closest_date_data['Date'] # Point annotation arrow to the closest data point

            # Add annotation
            ax.annotate(
                description,
                (x_pos, y_pos), # Use closest data point for annotation position
                textcoords="offset points",
                xytext=(0, 100), # Set vertical offset to 100 points
                ha='center',
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.9), # Increased alpha for more solid box
                arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0", color='red') # Arrow pointing down to the point, changed color to red
            )

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

st.title("PikPak Accuracy Dashboard")

with st.sidebar:
    # Add custom CSS for green button
    st.markdown("""
        <style>
        div[data-testid="stForm"] button[kind="primaryFormSubmit"] {
            background-color: #28a745;
            color: white;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.form(key="chart_form"):
        # We will load and filter data outside the form submission check now
        # The submitted flag will be used to trigger chart display and session state update
        submitted = st.form_submit_button("Show Chart", type='primary')

        # Primary selection controls
        machine = st.selectbox("Select Machine", sheets_to_plot)
        if machine:
            product_list = load_machine_products(file_path, machine)
        else:
            product_list = ['All Products']

        product = st.selectbox("Select Product", product_list, index=product_list.index("All Products") if "All Products" in product_list else 0)

        # Date range input
        from datetime import date, timedelta
        
        # Get the earliest date from the data
        df = load_machine_data(machine)
        df = filter_data_by_product(df, product)
        if not df.empty:
            default_start = df['Date'].min().date()
            default_end = df['Date'].max().date()
        else:
            # Fallback to last 3 months if no data
            default_end = date.today()
            default_start = default_end - timedelta(days=90)

        # Use radio buttons for date range selection
        date_selection = st.radio(
            "Date Selection",
            ["Show All Data", "Custom Date Range"],
            index=0,
            help="Choose whether to show all data or select a specific date range"
        )
            
        date_range = None
        if date_selection == "Custom Date Range":
            st.write("\n") # Add some space
            date_range = st.date_input(
                "Select your custom date range:",
                value=(default_start, default_end),
                format="DD-MM-YYYY",
                help="Select a start and end date for your custom range"
            )

        # Checkboxes
        detect_rules = st.checkbox("Enable Detection Rules")
        show_events = st.checkbox("Show Events")
        include_event_recalcs = st.checkbox("Include Event Recalculations", value=False, help="Include dates from the Events sheet marked for recalculation.")

        # Recalculation date input
        recalc_date_input = st.date_input(
            "Select Recalculation Date",
            value=None,
            format="DD-MM-YYYY",
            help="Select a date to add as a recalculation point for control limits."
        )

        if 'recalc_dates' not in st.session_state:
            st.session_state.recalc_dates = []

        add_date_button = st.form_submit_button("Add Recalculation Point")

        if add_date_button and recalc_date_input:
            if recalc_date_input not in st.session_state.recalc_dates:
                st.session_state.recalc_dates.append(recalc_date_input)
                st.session_state.recalc_dates.sort() # Keep dates sorted

        # Control limits at the bottom
        st.sidebar.markdown("---")  # Add a separator line
        st.sidebar.markdown("### Specification Limits")
        usl = st.number_input("USL (% Bad)", value=2.0)
        lsl = st.number_input("LSL (% Bad)", value=0.0)

    # Display selected recalculation dates and add a clear button (moved outside the form)
    if 'recalc_dates' in st.session_state and st.session_state.recalc_dates:
        st.sidebar.write("Recalculation Points:", [d.strftime("%Y-%m-%d") for d in st.session_state.recalc_dates])
        # Add a unique key to the clear button as it's outside the form now
        if st.sidebar.button("Clear Recalculation Points", key="clear_recalc_dates"):
            st.session_state.recalc_dates = []
            st.rerun()

# --- Data Loading and Filtering (moved outside submitted check) ---
df = load_machine_data(machine)
df = filter_data_by_product(df, product)

# Apply the date range filter to the data
if date_selection == "Custom Date Range" and date_range and len(date_range) == 2:
    start_date = pd.to_datetime(date_range[0])
    end_date = pd.to_datetime(date_range[1])
    df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)].copy() # Use .copy() to avoid SettingWithCopyWarning

# --- Chart Generation and Display ---
# Generate the chart if data is available or if the form was submitted (to handle initial display)
if not df.empty:
    events = load_events()
    fig = plot_chart(df, events, machine, product, "Shewhart", usl, lsl, detect_rules, show_events, st.session_state.recalc_dates, include_event_recalcs)
    st.session_state['chart'] = fig # Always update session state with the latest chart

    # Display the chart if it exists in session state
    if 'chart' in st.session_state and st.session_state['chart'] is not None:
        st.pyplot(st.session_state['chart'])

else:
    st.warning("No data available for the selected filters.")
