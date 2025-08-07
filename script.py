import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import re
from datetime import datetime
from collections import defaultdict

def parse_time_to_minutes(time_str):
    """Convert time string to minutes for sorting"""
    if not time_str or time_str == 'No time found':
        return 0
    
    # Extract time range (e.g., "10:30 AM - 12:00 PM")
    time_parts = time_str.split(' - ')
    if not time_parts:
        return 0
    
    # Use the start time for sorting
    start_time = time_parts[0].strip()
    
    try:
        # Parse time like "10:30 AM" or "2:00 PM"
        time_obj = datetime.strptime(start_time, "%I:%M %p")
        return time_obj.hour * 60 + time_obj.minute
    except:
        return 0

def organize_events_by_date(events_data):
    """Organize events by date and sort by time within each date"""
    events_by_date = defaultdict(list)
    
    for event in events_data:
        date = event.get('date', 'No date found')
        events_by_date[date].append(event)
    
    # Sort events within each date by time
    for date in events_by_date:
        events_by_date[date].sort(key=lambda x: parse_time_to_minutes(x.get('time', '')))
    
    # Convert to regular dict and sort dates
    organized_events = dict(events_by_date)
    
    # Sort dates (assuming format like "Monday, Aug 1, 2025")
    def parse_date_for_sorting(date_str):
        try:
            # Extract date part and parse
            date_part = date_str.split(', ')[1] + ', ' + date_str.split(', ')[2]
            return datetime.strptime(date_part, "%b %d, %Y")
        except:
            return datetime.max
    
    sorted_dates = sorted(organized_events.keys(), key=parse_date_for_sorting)
    
    # Create final organized structure
    final_organized = {}
    for date in sorted_dates:
        final_organized[date] = organized_events[date]
    
    return final_organized

def extract_description(soup):
    """Extract description based on the three different cases using specific selectors"""
    
    description_parts = []
    
    # Search in all containers, not just the first one with content
    containers = soup.select('div.container')
    
    for container in containers:
        if not container.get_text(strip=True):
            continue
            
        # Case 1: Extract all p tags using selector div.container > p
        p_tags = container.select('p')
        if p_tags:
            for p_tag in p_tags:
                p_text = p_tag.get_text(strip=True)
                if p_text and p_text not in description_parts and len(p_text) > 10:
                    description_parts.append(p_text)
        
        # Case 2: Extract i tags within p tags using selector div.container > p > i
        i_tags = container.select('p > i')
        if i_tags:
            for i_tag in i_tags:
                i_text = i_tag.get_text(strip=True)
                if i_text and i_text not in description_parts and len(i_text) > 5:
                    description_parts.append(i_text)
        
        # Case 3: Extract ul > li elements using selector div.container > ul > li
        li_tags = container.select('ul > li')
        if li_tags:
            for li_tag in li_tags:
                li_text = li_tag.get_text(strip=True)
                if li_text and li_text not in description_parts and len(li_text) > 5:
                    description_parts.append(li_text)
        
        # Case 4: Extract a tags within p tags
        a_tags = container.select('p > a')
        if a_tags:
            for a_tag in a_tags:
                a_text = a_tag.get_text(strip=True)
                if a_text and a_text not in description_parts and len(a_text) > 5:
                    description_parts.append(a_text)
    
    # Case 5: Extract direct text using xpath /html/body/main/div/text()
    # Since we're using BeautifulSoup, we'll simulate xpath by finding the main div and getting text nodes
    main_div = soup.select_one('main > div')
    if main_div:
        # Get all direct text nodes (similar to xpath text())
        for child in main_div.children:
            if hasattr(child, 'string') and child.string and child.string.strip():
                text = child.string.strip()
                if text and len(text) > 10 and text not in description_parts:  # Only substantial text
                    description_parts.append(text)
    
    # Filter out navigation and menu text from the results
    filtered_parts = []
    for part in description_parts:
        # Skip if it contains navigation-related text
        if any(skip in part.lower() for skip in [
            'open', 'close', 'menu', 'navigation', 'contact us', 'get involved', 
            'submit a request', 'careers', 'about us', 'site feedback', 'events', 
            'disclaimer', 'privacy policy', 'accessibility policy', 'your city hall',
            'strategic priorities', 'city management', 'departments', 'council and commissions',
            'transparency', 'get involved', 'participating in government', 'working at the city'
        ]):
            continue
        # Skip if it's just a list of services/links
        if len(part.split()) > 20 and any(word in part.lower() for word in ['services', 'programs', 'departments']):
            continue
        filtered_parts.append(part)
    
    # Combine all description parts
    if filtered_parts:
        return ' '.join(filtered_parts)
    else:
        return 'No description found'

def filter_events_by_week(events_data, target_week_start, week_start_day='Monday'):
    """Filter events to only show data for a specific week"""
    from datetime import datetime, timedelta
    
    # Map day names to numbers (Monday=0, Sunday=6)
    day_mapping = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    
    week_start_num = day_mapping.get(week_start_day, 0)  # Default to Monday
    
    # Parse the target week start date
    try:
        target_date = datetime.strptime(target_week_start, "%Y-%m-%d")
    except:
        print(f"Error: Invalid date format. Please use YYYY-MM-DD format (e.g., 2025-08-04)")
        return []
    
    # Calculate the start of the target week
    days_since_week_start = (target_date.weekday() - week_start_num) % 7
    week_start = target_date - timedelta(days=days_since_week_start)
    week_end = week_start + timedelta(days=6)
    
    print(f"Filtering events for week: {week_start.strftime('%b %d, %Y')} - {week_end.strftime('%b %d, %Y')}")
    
    filtered_events = []
    
    for event in events_data:
        date_str = event.get('date', 'No date found')
        if date_str == 'No date found':
            continue
            
        try:
            # Parse date like "Monday, Aug 1, 2025"
            date_part = date_str.split(', ')[1] + ', ' + date_str.split(', ')[2]
            event_date = datetime.strptime(date_part, "%b %d, %Y")
            
            # Check if event is within the target week (inclusive of start and end dates)
            if week_start <= event_date <= week_end:
                filtered_events.append(event)
                
        except Exception as e:
            print(f"Error parsing date '{date_str}': {e}")
            continue
    
    # Sort events by date first, then by time
    def sort_key(event):
        date_str = event.get('date', 'No date found')
        if date_str == 'No date found':
            return (datetime.max, 0)
        
        try:
            # Parse date like "Monday, Aug 1, 2025"
            date_part = date_str.split(', ')[1] + ', ' + date_str.split(', ')[2]
            event_date = datetime.strptime(date_part, "%b %d, %Y")
            time_minutes = parse_time_to_minutes(event.get('time', ''))
            return (event_date, time_minutes)
        except:
            return (datetime.max, 0)
    
    filtered_events.sort(key=sort_key)
    
    return filtered_events

def scrape_and_save_events(week_start_day=None, target_week=None):
    """Scrape event links, extract titles, dates, times, locations, and descriptions, and save to JSON"""
    
    # If no week start day provided, ask user for input
    if week_start_day is None:
        print("\nChoose your preferred week start day:")
        print("1. Monday")
        print("2. Tuesday") 
        print("3. Wednesday")
        print("4. Thursday")
        print("5. Friday")
        print("6. Saturday")
        print("7. Sunday")
        
        while True:
            try:
                choice = input("\nEnter your choice (1-7): ").strip()
                if choice in ['1', '2', '3', '4', '5', '6', '7']:
                    day_mapping = {
                        '1': 'Monday', '2': 'Tuesday', '3': 'Wednesday', '4': 'Thursday',
                        '5': 'Friday', '6': 'Saturday', '7': 'Sunday'
                    }
                    week_start_day = day_mapping[choice]
                    print(f"\nYou chose: {week_start_day}")
                    break
                else:
                    print("Please enter a number between 1 and 7.")
            except KeyboardInterrupt:
                print("\n\nScript cancelled by user.")
                return
            except:
                print("Invalid input. Please try again.")
    
    # If no target week provided, ask user for input
    if target_week is None:
        print(f"\nEnter the start date of the week you want (YYYY-MM-DD format)")
        print("Example: 2025-08-04 for the week starting August 4, 2025")
        
        while True:
            try:
                target_week = input("\nEnter date (YYYY-MM-DD): ").strip()
                # Validate date format
                datetime.strptime(target_week, "%Y-%m-%d")
                print(f"\nYou chose week starting: {target_week}")
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD format (e.g., 2025-08-04)")
            except KeyboardInterrupt:
                print("\n\nScript cancelled by user.")
                return
            except:
                print("Invalid input. Please try again.")
    
    # Target URL for August 2025 calendar
    url = "https://www.santamonica.gov/events?category=4egeeekbnhfx1xw1c1jd0jtvmv&viewMode=month&calendarView=true&dateRange=20250801-20250831"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        # Fetch the calendar page
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract event links
        event_links = []
        for link in soup.select('div.calendar-day-events > a[href]'):
            absolute_url = urljoin("https://www.santamonica.gov", link['href'])
            if absolute_url not in event_links:
                event_links.append(absolute_url)
        
        print(f"Found {len(event_links)} event links")
        
        # Scrape titles, dates, times, locations, and descriptions from each event
        events_data = []
        for i, event_url in enumerate(event_links):
            print(f"Scraping event {i+1}/{len(event_links)}")
            
            try:
                response = requests.get(event_url, headers=headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find container for debugging - look for the one with content
                containers = soup.select('div.container')
                container = None
                for cont in containers:
                    if cont.get_text(strip=True):  # Find container with actual text content
                        container = cont
                        break
                
                if not container and containers:
                    container = containers[-1]  # Use the last one if no content found
                
                # Extract title
                title_element = soup.select_one('h1.title')
                title = title_element.get_text(strip=True) if title_element else 'No title found'
                
                # Extract date
                date_element = soup.select_one('div.row > div:nth-child(1) > div > div > div:nth-child(1)')
                date = date_element.get_text(strip=True) if date_element else 'No date found'
                
                # Extract time
                time_element = soup.select_one('div.row > div:nth-child(1) > div > div > div:nth-child(2)')
                time = time_element.get_text(strip=True) if time_element else 'No time found'
                
                # Extract location link and text
                location_link_element = soup.select_one('div.row > div:nth-child(2) > div > div > div:nth-child(1) > a')
                location_link = location_link_element.get('href') if location_link_element else 'No location link found'
                location_name = location_link_element.get_text(strip=True) if location_link_element else ''
                
                # If no location name from link, try the broader selector for virtual events
                if not location_name:
                    location_container = soup.select_one('div.row > div:nth-child(2) > div > div > div:nth-child(1)')
                    if location_container:
                        location_name = location_container.get_text(strip=True)
                
                # Extract additional location details
                location_detail1 = soup.select_one('div.row > div:nth-child(2) > div > div > div:nth-child(2)')
                location_detail1_text = location_detail1.get_text(strip=True) if location_detail1 else ''
                
                location_detail2 = soup.select_one('div.row > div:nth-child(2) > div > div > div:nth-child(3)')
                location_detail2_text = location_detail2.get_text(strip=True) if location_detail2 else ''
                
                # Combine location information
                location_parts = [location_name, location_detail1_text, location_detail2_text]
                location_parts = [part for part in location_parts if part]  # Remove empty parts
                location = ', '.join(location_parts) if location_parts else 'No location found'
                
                # Extract description
                description = extract_description(soup)
                
                # Debug for first event
                if i == 0:
                    print(f"First event description: {description}")
                    if container:
                        print(f"Container text length: {len(container.get_text(strip=True))}")
                        print(f"Container text preview: {container.get_text(strip=True)[:300]}...")
                    else:
                        print("No container found")
                
                events_data.append({
                    'url': event_url,
                    'title': title,
                    'date': date,
                    'time': time,
                    'location': location,
                    'location_link': location_link,
                    'description': description
                })
                
            except Exception as e:
                print(f"Error scraping {event_url}: {e}")
                events_data.append({
                    'url': event_url,
                    'title': 'Failed to scrape title',
                    'date': 'Failed to scrape date',
                    'time': 'Failed to scrape time',
                    'location': 'Failed to scrape location',
                    'location_link': 'Failed to scrape location link',
                    'description': 'Failed to scrape description'
                })
        
        # Save to JSON file
        with open('events.json', 'w', encoding='utf-8') as f:
            json.dump(events_data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved {len(events_data)} events to events.json")
        
        # Filter events by the target week
        filtered_events = filter_events_by_week(events_data, target_week, week_start_day)
        
        # Save filtered events to JSON file
        filename = f'events_week_{target_week}_{week_start_day.lower()}.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(filtered_events, f, indent=2, ensure_ascii=False)
        
        print(f"\nSaved {len(filtered_events)} events for the specified week to {filename}")
        
        # Print summary
        print(f"\nEvents for week starting on {target_week} (week starts on {week_start_day}):")
        if filtered_events:
            for event in filtered_events:
                print(f"  - {event['date']} {event['time']}: {event['title']}")
        else:
            print("  No events found for this week.")
        
    except Exception as e:
        print(f"Error: {e}")

def run_with_week_start(week_start_day, target_week=None):
    """Run the script with a specific week start day and optional target week"""
    print(f"Running script with week starting on {week_start_day}")
    if target_week:
        print(f"Filtering for week starting: {target_week}")
    scrape_and_save_events(week_start_day, target_week)

if __name__ == "__main__":
    # You can either run with user input:
    scrape_and_save_events()
    
    # Or run with specific parameters:
    # run_with_week_start('Wednesday', '2025-08-06')  # Uncomment and change to your preferred settings