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

# Add caching for better performance
@st.cache_data
def load_excel_file_cached(file_path):
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

# Function to load Excel file with better error handling
def load_excel_file(file_path):
    return load_excel_file_cached(file_path)

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

@st.cache_data
def load_machine_data_cached(machine):
    """Load data for a specific machine from the Excel file or CSV with caching."""
    try:
        if machine == "LWS #010":
            st.write(f"Debug: Attempting to load CSV for {machine}")
            
            # Check if file exists
            import os
            csv_file = "PikPak Pick Accuracy(LWS #010).csv"
            if not os.path.exists(csv_file):
                st.error(f"CSV file not found: {csv_file}")
                st.info("Note: CSV file may not be available in cloud environment. Please ensure the file is uploaded to the repository.")
                
                # Create sample data for demonstration
                st.warning("Creating sample data for LWS #010 (CSV file not available)")
                sample_data = create_sample_lws_data()
                return sample_data
            
            st.write(f"Debug: CSV file exists, size: {os.path.getsize(csv_file)} bytes")
            
            # Try reading with different parameters
            try:
                df = pd.read_csv(csv_file, encoding='utf-8', low_memory=False)
                st.write(f"Debug: CSV loaded with UTF-8 encoding. Columns: {list(df.columns)}")
            except Exception as e1:
                st.write(f"Debug: UTF-8 failed, trying default encoding: {e1}")
                try:
                    df = pd.read_csv(csv_file, low_memory=False)
                    st.write(f"Debug: CSV loaded with default encoding. Columns: {list(df.columns)}")
                except Exception as e2:
                    st.error(f"Failed to read CSV file: {e2}")
                    return pd.DataFrame()
            
            st.write(f"Debug: DataFrame shape: {df.shape}")
            st.write(f"Debug: First few rows: {df.head()}")
            
            # Check if Date column exists
            if 'Date' not in df.columns:
                st.error(f"Date column not found in CSV for {machine}. Available columns: {list(df.columns)}")
                return pd.DataFrame()
            
            # Optimize date parsing with explicit format (DD/MM/YY)
            df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%y', errors='coerce')
            st.write(f"Debug: Date parsing completed. Sample dates: {df['Date'].head()}")
            
        else:
            df = pd.read_excel("PikPak Pick Accuracy.xlsx", sheet_name=machine)
            df['Date'] = pd.to_datetime(df['Date'])
        return df
    except Exception as e:
        st.error(f"Error loading data for {machine}: {e}")
        st.write(f"Debug: Full error details: {str(e)}")
        import traceback
        st.write(f"Debug: Traceback: {traceback.format_exc()}")
        return pd.DataFrame()

def create_sample_lws_data():
    """Create sample data for LWS #010 when CSV is not available."""
    import numpy as np
    from datetime import datetime, timedelta
    
    # Create sample dates (last 30 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Create sample data
    data = []
    for date in dates:
        # Generate 50-100 picks per day
        num_picks = np.random.randint(50, 100)
        for i in range(num_picks):
            # 95% good picks, 5% bad picks
            status = np.random.choice(['Good', 'Bad'], p=[0.95, 0.05])
            data.append({
                'Date': date,
                'Time': f"{np.random.randint(8, 18):02d}:{np.random.randint(0, 60):02d}:{np.random.randint(0, 60):02d}",
                'Index': i,
                'Status': status,
                'Product': 'Sample Product',
                'Operator': 'Sample Operator',
                'Comments': ''
            })
    
    df = pd.DataFrame(data)
    df['Date'] = pd.to_datetime(df['Date'])
    return df

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

@st.cache_data
def load_events_cached():
    try:
        # Read the Events sheet with hyperlink handling
        df = pd.read_excel(file_path, sheet_name='Events', parse_dates=['Date'])
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        
        # Add Time column if it doesn't exist
        if 'Time' not in df.columns:
            # Use the same dataframe we already loaded
            original_dates = pd.to_datetime(df['Date'])
            
            # Extract time if available, otherwise set default
            if original_dates.dt.time.notna().any():
                df['Time'] = original_dates.dt.time
            else:
                df['Time'] = '00:00:00'
        
        # Handle hyperlinks from Excel
        if 'URL' not in df.columns:
            df['URL'] = ''
        
        # Clean up URL column - remove any NaN values and handle Excel hyperlink format
        df['URL'] = df['URL'].fillna('')
        
        # Convert Excel hyperlink format if needed (Excel sometimes stores as HYPERLINK formula)
        for idx, url in enumerate(df['URL']):
            if isinstance(url, str) and url.startswith('=HYPERLINK('):
                # Extract URL from Excel HYPERLINK formula
                try:
                    # Extract URL from HYPERLINK("url","text") format
                    url_start = url.find('"') + 1
                    url_end = url.find('"', url_start)
                    if url_end > url_start:
                        df.at[idx, 'URL'] = url[url_start:url_end]
                except:
                    df.at[idx, 'URL'] = ''
        
        return df
    except Exception as e:
        st.warning(f"Error loading events: {e}")
        return pd.DataFrame(columns=['Date', 'Time', 'Machine', 'Description', 'URL', 'Recalculate Mean (Yes/No)'])

def load_events():
    """Load events data from the Excel file."""
    return load_events_cached()

def calculate_control_limits(segment_data, usl=None, lsl=None):
    total_picks_sum = segment_data['Total Picks'].sum()
    if total_picks_sum == 0:
        return 0, 0, 0, None
        
    p_bar = segment_data['Bad Picks'].sum() / total_picks_sum
    centerline = p_bar * 100
    mu = centerline  # Use centerline instead of mean of Bad %
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

def plot_chart(data, events, machine, product, chart_type, usl, lsl, detect_rules, show_events, user_recalc_dates, include_event_recalcs, show_shift_pattern, exclude_low_data_days):
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
    # Calculate daily summary with Bad % calculation - optimize with groupby
    daily_summary = data.groupby('Date').agg({
        'Status': lambda x: (x == 'Bad').sum(),
        '_count': 'sum'
    }).reset_index()
    daily_summary.rename(columns={'Status': 'Bad Picks', '_count': 'Total Picks'}, inplace=True)
    daily_summary['Bad %'] = daily_summary['Bad Picks'] / daily_summary['Total Picks'] * 100
    daily_summary = daily_summary[daily_summary['Total Picks'] >= min_samples]
    daily_summary = daily_summary.sort_values('Date')
    data = data.drop('_count', axis=1)

    # Filter out low data days if enabled
    if exclude_low_data_days and not daily_summary.empty:
        avg_daily_count = daily_summary['Total Picks'].mean()
        threshold = avg_daily_count * 0.3  # 30% of average
        original_count = len(daily_summary)
        daily_summary = daily_summary[daily_summary['Total Picks'] >= threshold]
        filtered_count = len(daily_summary)
        
        if original_count != filtered_count:
            st.info(f"Filtered out {original_count - filtered_count} days with insufficient data (less than {threshold:.1f} picks per day)")

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

    # Always include user-selected recalculation dates
    user_recalc_dates_dt = [pd.to_datetime(d) for d in user_recalc_dates if d is not None]

    if include_event_recalcs:
        event_recalc_dates_df = events[(events['Machine'] == machine) & (events['Recalculate Mean (Yes/No)'].str.upper() == 'YES')].copy()
        event_recalc_dates = event_recalc_dates_df['Date'].tolist()
        all_recalc_dates = sorted(list(set(user_recalc_dates_dt + event_recalc_dates)))
    else:
        all_recalc_dates = sorted(user_recalc_dates_dt)

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
        cpk_value = segments[-1]['cpk']
        cpk_text = f"Cpk = {cpk_value:.2f}"
        
        # Determine color based on Cpk value
        if cpk_value > 1.67:
            cpk_color = "green"
        elif cpk_value > 1.33:
            cpk_color = "yellow"
        elif cpk_value > 1.0:
            cpk_color = "orange"
        else:
            cpk_color = "red"
        
        fig.add_trace(go.Scatter(
            x=[None],
            y=[None],
            mode='markers',
            marker=dict(
                size=15,
                color=cpk_color,
                symbol='diamond',
                line=dict(width=2, color='black')
            ),
            name=cpk_text,
            showlegend=True
        ))

    # Add events if enabled
    if show_events and not events.empty:
        machine_events = events[events['Machine'] == machine].copy()
        min_data_date = daily_summary['Date'].min()
        max_data_date = daily_summary['Date'].max()
        machine_events = machine_events[(machine_events['Date'] >= min_data_date) & (machine_events['Date'] <= max_data_date)].copy()

        # Add legend for event colors only when events are enabled
        if not machine_events.empty:
            st.markdown("**📅 Event Annotations:**")
            st.markdown("- 🟠 **Orange**: Events with additional information (clickable in table below)")
            st.markdown("- 🔴 **Red**: Informational events only")
            st.markdown("")

        for index, event in machine_events.iterrows():
            event_date = event['Date']
            description = event['Description']
            url = event.get('URL', '')

            # Find the closest date in daily_summary
            closest_date_index = daily_summary['Date'].sub(event_date).abs().idxmin()
            closest_date_data = daily_summary.loc[closest_date_index]

            # Set color based on whether URL exists
            if url and url != '':
                bg_color = "#ff8c00"  # Orange for events with URLs
            else:
                bg_color = "#ff0000"  # Red for events without URLs

            # Add annotation
            fig.add_annotation(
                x=closest_date_data['Date'],
                y=closest_date_data['Bad %'],
                text=description,
                showarrow=True,
                arrowhead=2,
                ax=0,  # Horizontal offset of arrow
                ay=-120,  # Double the vertical offset
                bgcolor=bg_color,  # Use conditional color
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

    # After displaying the chart, show events table if enabled
    if show_events and not events.empty:
        machine_events = events[events['Machine'] == machine].copy()
        if not df.empty and 'Date' in df.columns:
            min_data_date = df['Date'].min()
            max_data_date = df['Date'].max()
            machine_events = machine_events[(machine_events['Date'] >= min_data_date) & (machine_events['Date'] <= max_data_date)].copy()
        
        if not machine_events.empty:
            st.markdown('### Events Table')
            
            # Create a DataFrame for display with proper formatting
            display_data = []
            for _, row in machine_events.iterrows():
                # Format date
                date_str = row['Date'].strftime('%d/%m/%y')
                
                # Create issue description with hyperlink if URL exists
                issue_desc = row['Description']
                url = row.get('URL', '')
                
                if url and url != '':
                    # Create HTML hyperlink for the dataframe
                    issue_desc = f'<a href="{url}" target="_blank">{row["Description"]}</a>'
                
                display_data.append({
                    'Date': date_str,
                    'Issue': issue_desc
                })
            
            # Create DataFrame for display
            events_df = pd.DataFrame(display_data)
            
            # Display the table using Streamlit's native dataframe with HTML
            # Add CSS for clean, minimal styling
            css = """
            <style>
            .events-table {
                width: 100%;
                margin: 10px 0;
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                border: none;
                background-color: transparent;
            }
            .events-table th {
                text-align: left;
                padding: 8px 0;
                font-weight: bold;
                color: white;
                border: none;
                background-color: transparent;
            }
            .events-table td {
                text-align: left;
                padding: 8px 0;
                border: none;
                background-color: transparent;
                color: white;
            }
            .events-table a {
                color: #0066cc;
                text-decoration: none;
            }
            .events-table a:hover {
                text-decoration: underline;
            }
            </style>
            """
            
            # Create HTML table manually for better control
            html_table = css + "<table class='events-table'>"
            html_table += "<thead><tr><th>Date</th><th>Issue</th></tr></thead>"
            html_table += "<tbody>"
            
            for _, row in events_df.iterrows():
                html_table += f"<tr><td>{row['Date']}</td><td>{row['Issue']}</td></tr>"
            
            html_table += "</tbody></table>"
            
            st.write(html_table, unsafe_allow_html=True)
            
            # Add note about event colors and clickable links
            if not events_df.empty:
                st.markdown("")
                st.markdown("**💡 Tip:** Orange events in the chart above have clickable links in this table. Click on the blue text to access additional information.")
        else:
            st.info("No events found for the selected machine and date range.")
    elif show_events:
        st.info("No events data available. Please ensure the Events sheet exists in the Excel file.")

# --- STREAMLIT APP ---

with st.expander("ℹ️ Help: Statistical Process Charts", expanded=False):
    st.markdown("""
    ## **Statistical Process Control (SPC) Dashboard Guide**
    
    ### **Detection Rules** 🔍
    Enable **Detection Rules** to highlight key statistical signals in your process:
    
    - **Outside Limits** ⚠️: One point beyond the upper or lower control limits
    - **Zone Shift** 📈: 8 or more consecutive points on one side of the centerline
    - **Trend** 📊: 6 or more points trending upward or downward
    - **Alternating** 🔄: 14 or more points alternating up and down
    
    ### **Specification Limits** 📏
    - **USL (Upper Specification Limit)**: Maximum acceptable value for % Bad
    - **LSL (Lower Specification Limit)**: Minimum acceptable value for % Bad
    - These limits define your process requirements and are used to calculate **Cpk**
    
    ### **Process Capability (Cpk) Guide** 📊
    - **Cpk > 1.67**: 🟢 Excellent process capability
    - **1.33 < Cpk ≤ 1.67**: 🟡 Good process capability  
    - **1.0 < Cpk ≤ 1.33**: 🟠 Marginal process capability
    - **Cpk ≤ 1.0**: 🔴 Process needs improvement
    
    ### **Events and Recalculation Points** 📅
    - **Events**: Significant occurrences that may affect process performance
    - **Event Annotations**: Red markers on the chart when "Show Events" is enabled
    - **Recalculation Points**: Trigger new control limit calculations
    - **Manual Recalculation**: Add dates using the date picker
    - **Event Recalculations**: Automatically include events marked "Yes" for recalculation
    
    ### **Data Quality Features** 🎯
    - **Exclude Low Data Days**: Remove days with insufficient data (< 30% of average)
    - **Product Filtering**: Focus on specific products or view all products
    - **Machine Selection**: Analyze specific machines (EVG #006, EVG #007, LWS #010)
    
    ### **Chart Features** 📈
    - **Control Limits**: UCL (Upper), LCL (Lower), and Centerline
    - **Shift Pattern Overlay**: For LWS #010, shows A/B shift cycles
    - **Interactive Plot**: Zoom, pan, and hover for detailed information
    - **Export Ready**: Charts can be saved as images
    
    ### **Best Practices** 💡
    1. **Start with "All Products"** to see overall process performance
    2. **Enable Detection Rules** to identify process issues
    3. **Use Events** to correlate process changes with performance
    4. **Exclude Low Data Days** for more accurate analysis
    5. **Set appropriate USL/LSL** based on customer requirements
    """)

st.title("PikPak Statistical Process Control (SPC) Dashboard")

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
        detect_rules = st.checkbox("Enable Detection Rules", key="form_detect_rules", 
                                 help="Highlight statistical process control violations: Outside Limits (points beyond UCL/LCL), Zone Shift (8+ consecutive points on one side), Trend (6+ points trending up/down), Alternating (14+ points alternating)")
        show_events = st.checkbox("Show Events", key="form_show_events", 
                                help="Display significant events from the Excel Events sheet as annotations on the chart and in a table below. Events can include maintenance, operator changes, or process modifications.")
        include_event_recalcs = st.checkbox("Include Event Recalculations", value=False, 
                                          help="Automatically include dates from the Events sheet marked 'Yes' for recalculation. This creates new control limit segments when significant events occur, improving chart accuracy.")
        exclude_low_data_days = st.checkbox("Exclude Low Data Days", value=False, 
                                          help="Remove days with insufficient data points (less than 30% of average daily count). This improves control chart accuracy by eliminating days that could skew the analysis.")

        # Add the shift pattern checkbox here, inside the form, but conditionally displayed
        show_shift_pattern_dynamic = False
        if st.session_state.get('form_machine_select') == "LWS #010":
             show_shift_pattern_dynamic = st.checkbox("Overlay Shift Pattern", 
                                                   help="Display shift pattern overlay (A/B shifts) for LWS #010. Shows 8-day cycle starting from January 1st, 2025 with 4 days per shift.", 
                                                   key="shift_pattern_checkbox")

        # Recalculation date input (kept inside form)
        recalc_date_input = st.date_input(
            "Select Recalculation Date",
            value=None,
            format="DD-MM-YYYY",
            help="Add a specific date as a recalculation point. Control limits will be recalculated from this date forward, creating a new segment. Useful for process changes, maintenance, or significant events.",
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
            # Do NOT update st.session_state.recalc_dates here

        # Add specification limits at the bottom of the form
        st.markdown("---")  # Add a separator line
        st.markdown("### Specification Limits")
        usl = st.number_input("USL (% Bad)", value=2.0, step=0.5, 
                             help="Upper Specification Limit: Maximum acceptable percentage of bad picks. Values above this indicate the process is not meeting customer requirements.", 
                             key="form_usl")
        lsl = st.number_input("LSL (% Bad)", value=0.0, step=0.5, 
                             help="Lower Specification Limit: Minimum acceptable percentage of bad picks. Used with USL to calculate process capability (Cpk).", 
                             key="form_lsl")

        # Update session state with selected machine when form is submitted
        if submitted:
            st.session_state.selected_machine = machine
            st.session_state['submitted_machine'] = machine
            st.session_state['submitted_product'] = product
            st.session_state['submitted_detect_rules'] = detect_rules
            st.session_state['submitted_show_events'] = show_events
            st.session_state['submitted_include_event_recalcs'] = include_event_recalcs
            st.session_state['submitted_exclude_low_data_days'] = exclude_low_data_days
            st.session_state['submitted_usl'] = usl
            st.session_state['submitted_lsl'] = lsl
            st.session_state['submitted_show_shift_pattern'] = st.session_state.get('shift_pattern_checkbox', False)
            # Only update recalc_dates when Show Chart is clicked
            if 'temp_recalc_dates' in st.session_state:
                st.session_state.recalc_dates = st.session_state.temp_recalc_dates.copy()
                st.session_state.temp_recalc_dates = []  # Clear temporary list after applying

    # Display both Pending and Active recalculation dates in the sidebar
    # Pending: temp_recalc_dates (to be applied on next Show Chart)
    # Active: recalc_dates (currently applied to the chart)
    if 'temp_recalc_dates' in st.session_state and st.session_state.temp_recalc_dates:
        st.sidebar.write("Pending Recalculation Points:")
        for date in st.session_state.temp_recalc_dates:
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                st.write(date.strftime("%d-%m-%Y"))
            with col2:
                if st.button("❌", key=f"remove_pending_{date.strftime('%Y%m%d')}"):
                    st.session_state.temp_recalc_dates.remove(date)
                    # Do NOT call st.rerun() here; only update chart on 'Show Chart'

    if 'recalc_dates' in st.session_state and st.session_state.recalc_dates:
        st.sidebar.write("Active Recalculation Points:")
        for date in st.session_state.recalc_dates:
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                st.write(date.strftime("%d-%m-%Y"))
            with col2:
                if st.button("❌", key=f"remove_active_{date.strftime('%Y%m%d')}"):
                    st.session_state.recalc_dates.remove(date)
                    st.rerun()

# --- Data Loading and Filtering ---
# Use submitted values from session state for data loading and plotting
submitted_machine = st.session_state.get('submitted_machine')
submitted_product = st.session_state.get('submitted_product')

df = pd.DataFrame() # Initialize empty DataFrame

# Only load data if the form has been submitted at least once with valid machine/product
if submitted_machine and submitted_product:
    try:
        df = load_machine_data_cached(submitted_machine)
        df = filter_data_by_product(df, submitted_product)

    except Exception as e:
        st.error(f"Error loading or filtering data after form submission: {e}")
        df = pd.DataFrame() # Ensure df is empty on error

# --- Chart Generation and Display ---
# Only generate and display chart if data is loaded and available (i.e., form submitted and data found)
if not df.empty:
    try:
        events = load_events_cached()
        # Use submitted values from session state for plotting
        submitted_detect_rules = st.session_state.get('submitted_detect_rules', False)
        submitted_show_events = st.session_state.get('submitted_show_events', False)
        submitted_include_event_recalcs = st.session_state.get('submitted_include_event_recalcs', False)
        submitted_exclude_low_data_days = st.session_state.get('submitted_exclude_low_data_days', False)
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
            submitted_show_shift_pattern, # Pass the submitted shift pattern state
            submitted_exclude_low_data_days # Pass the submitted exclude_low_data_days state
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
