print("Script execution started")

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
import plotly.graph_objects as go

print("Reached after imports")

# --- SETTINGS ---
file_path = "PikPak Pick Accuracy.xlsx"

# Function to load Excel file with better error handling
def load_excel_file(file_path):
    try:
        if not os.path.isfile(file_path):
            st.error(f"File not found: {file_path}")
            return None
        
        # Try to read the file (just checking if it's readable)
        pd.read_excel(file_path, nrows=1) # Read just one row to check readability
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
    """Load data for a specific machine from the Excel file."""
    try:
        # Load the Excel file
        df = pd.read_excel("PikPak Pick Accuracy.xlsx", sheet_name=machine)
        # Convert Date column to datetime
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except Exception as e:
        st.error(f"Error loading data for {machine}: {e}")
        return pd.DataFrame()

def load_shift_pattern():
    """Load shift pattern data from the Excel file."""
    try:
        # Load the Shift Pattern sheet
        df = pd.read_excel("PikPak Pick Accuracy.xlsx", sheet_name="Shift Pattern")
        # Convert Date column to datetime
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except Exception as e:
        st.error(f"Error loading shift pattern data: {e}")
        return pd.DataFrame()

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
    total_picks_sum = segment_data['Total Picks'].sum()
    if total_picks_sum == 0:
        return 0, 0, 0, None
        
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

def plot_chart(data, events, machine, product, chart_type, usl, lsl, detect_rules, show_events, user_recalc_dates, include_event_recalcs, show_shift_pattern):
    """Plot the control chart with the given data and settings."""
    if data.empty:
        st.warning("No data available for the selected criteria.")
        return

    # Define minimum number of samples required for a valid data point
    min_samples = 1  # Temporarily lowered for testing

    # Create the figure
    fig = go.Figure()

    # Calculate daily summary (needed for both shift pattern and data points)
    # Create a temporary column for counting
    data['_count'] = 1
    # Calculate daily summary with Bad % calculation
    daily_summary = data.groupby('Date').agg({
        'Status': lambda x: (x == 'Bad').sum(),
        '_count': 'sum'
    }).reset_index()
    daily_summary.rename(columns={'Status': 'Bad Picks', '_count': 'Total Picks'}, inplace=True)
    daily_summary['Bad %'] = daily_summary['Bad Picks'] / daily_summary['Total Picks'] * 100
    daily_summary = daily_summary[daily_summary['Total Picks'] >= min_samples]
    daily_summary = daily_summary.sort_values('Date')
    data = data.drop('_count', axis=1)

    # Add shift pattern overlay if enabled and machine is LWS #010
    if show_shift_pattern and machine == "LWS #010":
        # Generate shift pattern based on an 8-day cycle starting Jan 1st, 2025 (4A, 4B)
        start_of_2025 = datetime(2025, 1, 1)  # Wednesday, January 1st, 2025

        # Get the date range from the daily_summary (calculated earlier)
        min_data_date = daily_summary['Date'].min()
        max_data_date = daily_summary['Date'].max()

        # Create a dataframe for all dates in the data range
        all_dates_in_range = pd.DataFrame({'Date': pd.date_range(start=min_data_date, end=max_data_date, freq='D')})

        # Calculate shift for each date
        shift_data = []
        for index, row in all_dates_in_range.iterrows():
            days_since_2025 = (row['Date'].date() - start_of_2025.date()).days
            # 8-day cycle: 0,1,2,3 = A; 4,5,6,7 = B; 8,9,10,11 = A, etc.
            # First 4 days (0-3) are Shift A, next 4 days (4-7) are Shift B
            shift = 'A' if (days_since_2025 % 8) < 4 else 'B'
            shift_data.append({'Date': row['Date'], 'Shift': shift})

        shift_df_generated = pd.DataFrame(shift_data)

        if not shift_df_generated.empty:
            # Filter shift data to the exact dates present in the daily_summary
            shift_df_filtered = shift_df_generated[(shift_df_generated['Date'] >= min_data_date) & (shift_df_generated['Date'] <= max_data_date)].copy()

            if not shift_df_filtered.empty:
                # Define colors for Shift A (blue) and Shift B (yellow) with transparency
                shift_colors = {
                    'A': 'rgba(0, 0, 255, 0.1)',  # Light blue tint
                    'B': 'rgba(255, 255, 0, 0.1)' # Light yellow tint
                }

                # Group dates by shift to create contiguous blocks
                segments = []
                current_shift = None
                segment_start_date = None

                # Ensure shift_df_filtered is sorted by date
                shift_df_filtered = shift_df_filtered.sort_values(by='Date').reset_index(drop=True)

                for index, row in shift_df_filtered.iterrows():
                    if current_shift is None:
                        current_shift = row['Shift']
                        segment_start_date = row['Date']
                    elif row['Shift'] != current_shift:
                        # Add the previous segment
                        segments.append({'Shift': current_shift, 'start_date': segment_start_date, 'end_date': shift_df_filtered.iloc[index-1]['Date']})
                        # Start the new segment
                        current_shift = row['Shift']
                        segment_start_date = row['Date']

                # Add the last segment after the loop
                if current_shift is not None and segment_start_date is not None:
                    segments.append({'Shift': current_shift, 'start_date': segment_start_date, 'end_date': shift_df_filtered.iloc[-1]['Date']})

                # Add background rectangles for each shift segment
                for segment in segments:
                    # Extend the end date by one day to cover the entire last day of the segment
                    end_date_extended = segment['end_date'] + timedelta(days=1)
                    fig.add_shape(
                        type="rect",
                        x0=segment['start_date'],
                        y0=daily_summary['Bad %'].min() * 0.9,  # Slightly below min data value
                        x1=end_date_extended,
                        y1=daily_summary['Bad %'].max() * 1.1,  # Slightly above max data value
                        fillcolor=shift_colors.get(segment['Shift'], 'rgba(128, 128, 128, 0.1)'),
                        opacity=1.0,
                        layer="below",  # Place below data points
                        line_width=0
                    )

                # Add simplified legend entries for shifts
                fig.add_trace(go.Scatter(
                    x=[None],
                    y=[None],
                    mode='markers',
                    marker=dict(size=10, color=shift_colors['A']),
                    name='Shift A',
                    showlegend=True
                ))
                fig.add_trace(go.Scatter(
                    x=[None],
                    y=[None],
                    mode='markers',
                    marker=dict(size=10, color=shift_colors['B']),
                    name='Shift B',
                    showlegend=True
                ))

    # Add data points
    fig.add_trace(go.Scatter(
        x=daily_summary['Date'],
        y=daily_summary['Bad %'],
        mode='lines+markers',
        name='% Bad',
        line=dict(color='blue', width=2),
        marker=dict(size=8, color='blue')
    ))

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

    # Calculate segments and control limits
    segments = []
    for i in range(len(all_recalc_dates)):
        start_date = all_recalc_dates[i]
        if i + 1 < len(all_recalc_dates):
            end_date = all_recalc_dates[i+1] - timedelta(days=1)
        else:
            end_date = daily_summary['Date'].max()

        if end_date < start_date:
            end_date = start_date

        segment_data = daily_summary[(daily_summary['Date'] >= start_date) & (daily_summary['Date'] <= end_date)]
        if not segment_data.empty:
            centerline, ucl, lcl, cpk = calculate_control_limits(segment_data, usl, lsl)
            segments.append({
                'start_date': start_date,
                'end_date': end_date,
                'data': segment_data,
                'centerline': centerline,
                'ucl': ucl,
                'lcl': lcl,
                'cpk': cpk
            })

    # Add detection rules highlighting if enabled
    if detect_rules:
        # Check for violations in each segment
        all_violations = {
            'outside_limits': [],
            'zone_shift': [],
            'trend': [],
            'alternating': []
        }
        
        for segment in segments:
            violations = detect_violations(segment['data'], segment['centerline'], segment['ucl'], segment['lcl'])
            # Combine violations from all segments
            for violation_type, dates in violations.items():
                all_violations[violation_type].extend(dates)
        
        # Add markers for all violations
        for violation_type, dates in all_violations.items():
            if dates:  # Only add if there are violations
                violation_data = daily_summary[daily_summary['Date'].isin(dates)]
                if not violation_data.empty:
                    fig.add_trace(go.Scatter(
                        x=violation_data['Date'],
                        y=violation_data['Bad %'],
                        mode='markers',
                        marker=dict(
                            size=8,
                            symbol='circle',
                            color='red'
                        ),
                        name=f'{violation_type.replace("_", " ").title()}',
                        showlegend=True
                    ))

    # Add control limits for each segment
    for i, segment in enumerate(segments):
        if i == 0:  # First segment
            # Add centerline
            fig.add_trace(go.Scatter(
                x=[segment['start_date'], segment['end_date']],
                y=[segment['centerline'], segment['centerline']],
                mode='lines',
                line=dict(color='green', dash='dash', width=2),
                name=f"Centerline = {segment['centerline']:.2f}%",
                showlegend=True
            ))

            # Add UCL
            fig.add_trace(go.Scatter(
                x=[segment['start_date'], segment['end_date']],
                y=[segment['ucl'], segment['ucl']],
                mode='lines',
                line=dict(color='red', dash='dash', width=2),
                name=f"UCL = {segment['ucl']:.2f}%",
                showlegend=True
            ))

            # Add LCL
            fig.add_trace(go.Scatter(
                x=[segment['start_date'], segment['end_date']],
                y=[segment['lcl'], segment['lcl']],
                mode='lines',
                line=dict(color='red', dash='dash', width=2),
                name=f"LCL = {segment['lcl']:.2f}%",
                showlegend=True
            ))
        else:  # Subsequent segments
            # Calculate adjusted dates for gaps
            end_of_prev = segments[i-1]['end_date'] - timedelta(days=0.5)  # End previous segment 0.5 days earlier
            start_of_next = segment['start_date'] + timedelta(days=0.5)    # Start next segment 0.5 days later

            # Add centerline
            fig.add_trace(go.Scatter(
                x=[start_of_next, segment['end_date']],  # Start after the gap
                y=[segment['centerline'], segment['centerline']],
                mode='lines',
                line=dict(color='green', dash='dash'),
                showlegend=False
            ))

            # Add UCL
            fig.add_trace(go.Scatter(
                x=[start_of_next, segment['end_date']],  # Start after the gap
                y=[segment['ucl'], segment['ucl']],
                mode='lines',
                line=dict(color='red', dash='dash'),
                showlegend=False
            ))

            # Add LCL
            fig.add_trace(go.Scatter(
                x=[start_of_next, segment['end_date']],  # Start after the gap
                y=[segment['lcl'], segment['lcl']],
                mode='lines',
                line=dict(color='red', dash='dash'),
                showlegend=False
            ))

            # Add connecting lines between segments
            # Centerline connection
            fig.add_trace(go.Scatter(
                x=[segments[i-1]['end_date'] - timedelta(days=0.5), segment['start_date'] + timedelta(days=0.5)], # Connect across the 0.5 day gaps
                y=[segments[i-1]['centerline'], segment['centerline']],
                mode='lines',
                line=dict(color='green', dash='dash'),
                showlegend=False
            ))

            # UCL connection
            fig.add_trace(go.Scatter(
                x=[segments[i-1]['end_date'] - timedelta(days=0.5), segment['start_date'] + timedelta(days=0.5)], # Connect across the 0.5 day gaps
                y=[segments[i-1]['ucl'], segment['ucl']],
                mode='lines',
                line=dict(color='red', dash='dash'),
                showlegend=False
            ))

            # LCL connection
            fig.add_trace(go.Scatter(
                x=[segments[i-1]['end_date'] - timedelta(days=0.5), segment['start_date'] + timedelta(days=0.5)], # Connect across the 0.5 day gaps
                y=[segments[i-1]['lcl'], segment['lcl']],
                mode='lines',
                line=dict(color='red', dash='dash'),
                showlegend=False
            ))

    # Add Cpk to the legend if available
    if segments and segments[-1]['cpk'] is not None:
        fig.add_trace(go.Scatter(
            x=[None],
            y=[None],
            mode='markers',
            marker=dict(size=0),
            name=f"Cpk = {segments[-1]['cpk']:.2f}",
            showlegend=True
        ))

    # Add events if enabled
    if show_events and not events.empty:
        machine_events = events[events['Machine'] == machine].copy()
        min_data_date = daily_summary['Date'].min()
        max_data_date = daily_summary['Date'].max()
        machine_events = machine_events[(machine_events['Date'] >= min_data_date) & (machine_events['Date'] <= max_data_date)].copy()

        for index, event in machine_events.iterrows():
            event_date = event['Date']
            description = event['Description']

            # Find the closest date in daily_summary
            closest_date_index = daily_summary['Date'].sub(event_date).abs().idxmin()
            closest_date_data = daily_summary.loc[closest_date_index]

            # Add annotation
            fig.add_annotation(
                x=closest_date_data['Date'],
                y=closest_date_data['Bad %'],
                text=description,
                showarrow=True,
                arrowhead=2,
                ax=0,  # Horizontal offset of arrow
                ay=-120,  # Double the vertical offset
                bgcolor="#ff0000",  # Strong red
                bordercolor="black",
                borderwidth=1,
                borderpad=4,  # Back to 4 pixels padding
                opacity=1.0,  # Full opacity
                font=dict(
                    color="black",
                    size=12
                )
            )

    # Update layout
    fig.update_layout(
        title=dict(
            text=f"{machine} - {product} Control Chart",
            y=0.95,
            x=0.5,
            xanchor='center',
            yanchor='top'
        ),
        xaxis_title="Date",
        yaxis_title="Bad %",
        showlegend=True,
        height=600,
        plot_bgcolor='white',
        paper_bgcolor='white',
        title_font_color='black',
        xaxis=dict(
            tickangle=45,
            tickformat="%d-%m-%Y",
            type='date',
            # Force Monday-based ticks
            tickmode='array',
            # Generate ticks for every Monday in the date range
            ticktext=[d.strftime("%d-%m-%Y") for d in pd.date_range(
                start=daily_summary['Date'].min(),
                end=daily_summary['Date'].max(),
                freq='W-MON'
            )],
            tickvals=pd.date_range(
                start=daily_summary['Date'].min(),
                end=daily_summary['Date'].max(),
                freq='W-MON'
            ),
            showgrid=True,
            gridcolor='lightgray',
            gridwidth=1,
            title_font_color='black',
            tickfont_color='black',
            range=[daily_summary['Date'].min(), daily_summary['Date'].max()]  # Ensure full date range is shown
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='lightgray',
            gridwidth=1,
            title_font_color='black',
            tickfont_color='black'
        ),
        legend=dict(
            font_color='black'
        )
    )

    # Add shift pattern overlay if enabled and machine is LWS #010
    if show_shift_pattern and machine == "LWS #010":
        # Force x-axis to show dates after adding shift pattern
        fig.update_xaxes(
            type='date',
            # Force Monday-based ticks
            tickmode='array',
            # Generate ticks for every Monday in the date range
            ticktext=[d.strftime("%d-%m-%Y") for d in pd.date_range(
                start=daily_summary['Date'].min(),
                end=daily_summary['Date'].max(),
                freq='W-MON'
            )],
            tickvals=pd.date_range(
                start=daily_summary['Date'].min(),
                end=daily_summary['Date'].max(),
                freq='W-MON'
            ),
            range=[daily_summary['Date'].min(), daily_summary['Date'].max()]
        )

    # Display the plot with explicit configuration
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={'displayModeBar': True},
        height=600
    )

# --- STREAMLIT APP ---

with st.expander("ℹ️ Help: Statistical Process Charts", expanded=False):
    st.markdown("""
    Enable **Detection Rules** in the sidebar to highlight these key statistical signals in your process:

    - **Outside Limits**: One point beyond the upper or lower control limits.
    - **Zone Shift**: 8 or more consecutive points on one side of the centerline.
    - **Trend**: 6 or more points trending upward or downward.
    - **Alternating**: 14 or more points alternating up and down.

    **Specification Limits:**
    - USL (Upper Specification Limit): The maximum acceptable value for % Bad
    - LSL (Lower Specification Limit): The minimum acceptable value for % Bad
    - These limits define the acceptable range for your process
    - They are used to calculate Cpk, which measures how well your process fits within these limits

    **Cpk (Process Capability) Guide:**
    - Cpk > 1.67: Excellent process
    - 1.33 < Cpk ≤ 1.67: Good process
    - 1.0 < Cpk ≤ 1.33: Marginal process
    - Cpk ≤ 1.0: Process needs improvement

    Higher Cpk values indicate better process performance and less risk of producing out-of-specification results.

    **Events and Recalculation Points:**
    - Events are significant occurrences that may affect process performance
    - They are displayed as red annotations on the chart when "Show Events" is enabled
    - Events can be marked for recalculation (Yes/No in Events sheet)
    - When "Include Event Recalculations" is enabled, these events will trigger new control limit calculations
    - You can also manually add recalculation points using the date picker
    - Recalculation points help identify when process behavior changes significantly
    - Each segment between recalculation points has its own control limits
    """)

st.title("PikPak Inaccuracy Dashboard")

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
    
    # Store the selected machine in session state
    if 'selected_machine' not in st.session_state:
        st.session_state.selected_machine = sheets_to_plot[0]
    
    with st.form(key="chart_form"):
        # Primary selection controls (kept inside form)
        machine = st.selectbox("Select Machine", sheets_to_plot, 
                             index=sheets_to_plot.index(st.session_state.selected_machine),
                             key="form_machine_select")
        if machine:
            product_list = load_machine_products(file_path, machine)
        else:
            product_list = ['All Products']

        product = st.selectbox("Select Product", product_list, index=product_list.index("All Products") if "All Products" in product_list else 0, key="form_product_select")

        # Submit button moved to top
        submitted = st.form_submit_button("Show Chart", type='primary')

        # Checkboxes (kept inside form as they affect plot on submit)
        detect_rules = st.checkbox("Enable Detection Rules", key="form_detect_rules")
        show_events = st.checkbox("Show Events", key="form_show_events")
        include_event_recalcs = st.checkbox("Include Event Recalculations", value=False, help="Include dates from the Events sheet marked for recalculation.", key="form_include_event_recalcs")

        # Add the shift pattern checkbox here, inside the form, but conditionally displayed
        show_shift_pattern_dynamic = False
        if st.session_state.get('form_machine_select') == "LWS #010":
             show_shift_pattern_dynamic = st.checkbox("Overlay Shift Pattern", help="Show shift pattern overlay for LWS 010", key="shift_pattern_checkbox")

        # Recalculation date input (kept inside form)
        recalc_date_input = st.date_input(
            "Select Recalculation Date",
            value=None,
            format="DD-MM-YYYY",
            help="Select a date to add as a recalculation point for control limits.",
            key="form_recalc_date_input"
        )

        # Add Recalculation Point button
        add_date_button = st.form_submit_button("Add Recalculation Point")
        
        # Initialize recalc_dates in session state if not present
        if 'recalc_dates' not in st.session_state:
            st.session_state.recalc_dates = []
        
        # Store the new date in a temporary list that will be processed on form submission
        if 'temp_recalc_dates' not in st.session_state:
            st.session_state.temp_recalc_dates = []
        
        if add_date_button and recalc_date_input:
            if recalc_date_input not in st.session_state.temp_recalc_dates:
                st.session_state.temp_recalc_dates.append(recalc_date_input)
                st.session_state.temp_recalc_dates.sort()

        # Add specification limits at the bottom of the form
        st.markdown("---")  # Add a separator line
        st.markdown("### Specification Limits")
        usl = st.number_input("USL (% Bad)", value=2.0, step=0.5, key="form_usl")
        lsl = st.number_input("LSL (% Bad)", value=0.0, step=0.5, key="form_lsl")

        # Update session state with selected machine when form is submitted
        if submitted:
            st.session_state.selected_machine = machine
            st.session_state['submitted_machine'] = machine
            st.session_state['submitted_product'] = product
            st.session_state['submitted_detect_rules'] = detect_rules
            st.session_state['submitted_show_events'] = show_events
            st.session_state['submitted_include_event_recalcs'] = include_event_recalcs
            st.session_state['submitted_usl'] = usl
            st.session_state['submitted_lsl'] = lsl
            st.session_state['submitted_show_shift_pattern'] = st.session_state.get('shift_pattern_checkbox', False)
            # Update the actual recalculation dates when Show Chart is clicked
            if 'temp_recalc_dates' in st.session_state:
                st.session_state.recalc_dates = st.session_state.temp_recalc_dates.copy()
                st.session_state.temp_recalc_dates = []  # Clear temporary list

    # Display selected recalculation dates and add a clear button (moved outside the form)
    # This part should react dynamically, so keep outside the form
    if 'recalc_dates' in st.session_state and st.session_state.recalc_dates:
        st.sidebar.write("Recalculation Points:")
        # Create columns for each date and its remove button
        for date in st.session_state.recalc_dates:
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                st.write(date.strftime("%Y-%m-%d"))
            with col2:
                if st.button("❌", key=f"remove_{date.strftime('%Y%m%d')}"):
                    st.session_state.recalc_dates.remove(date)
                    if 'temp_recalc_dates' in st.session_state:
                        st.session_state.temp_recalc_dates = st.session_state.recalc_dates.copy()
                    st.rerun()

# --- Data Loading and Filtering ---
# Use submitted values from session state for data loading and plotting
submitted_machine = st.session_state.get('submitted_machine')
submitted_product = st.session_state.get('submitted_product')

df = pd.DataFrame() # Initialize empty DataFrame

# Only load data if the form has been submitted at least once with valid machine/product
if submitted_machine and submitted_product:
    try:
        df = load_machine_data(submitted_machine)
        df = filter_data_by_product(df, submitted_product)

    except Exception as e:
        st.error(f"Error loading or filtering data after form submission: {e}")
        df = pd.DataFrame() # Ensure df is empty on error

# --- Chart Generation and Display ---
# Only generate and display chart if data is loaded and available (i.e., form submitted and data found)
if not df.empty:
    try:
        events = load_events()
        # Use submitted values from session state for plotting
        submitted_detect_rules = st.session_state.get('submitted_detect_rules', False)
        submitted_show_events = st.session_state.get('submitted_show_events', False)
        submitted_include_event_recalcs = st.session_state.get('submitted_include_event_recalcs', False)
        submitted_usl = st.session_state.get('submitted_usl', 2.0)
        submitted_lsl = st.session_state.get('submitted_lsl', 0.0)
        # Use the submitted shift pattern checkbox state
        submitted_show_shift_pattern = st.session_state.get('submitted_show_shift_pattern', False)

        # Recalculation dates are handled dynamically outside the form
        user_recalc_dates = st.session_state.get('recalc_dates', [])

        fig = plot_chart(
            df,
            events,
            submitted_machine,
            submitted_product,
            "Shewhart",
            submitted_usl,
            submitted_lsl,
            submitted_detect_rules,
            submitted_show_events,
            user_recalc_dates, # Use the dynamically updated recalc dates
            submitted_include_event_recalcs,
            submitted_show_shift_pattern # Pass the submitted shift pattern state
        )

    except Exception as e:
         st.error(f"Error generating or displaying chart: {e}")
         # Optionally display the raw dataframe for debugging
         st.write("Debug - Raw dataframe:", df)

else:
    # Show initial message or warning if no data is loaded yet
    if submitted_machine is None:
        st.info("Please select a Machine and Product and click 'Show Chart' to display the control chart.")
    else:
        st.warning("No data available for the selected filters.")
