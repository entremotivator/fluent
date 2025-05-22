import streamlit as st
import requests
import json
import pandas as pd
import base64
from datetime import datetime
import os

# Set page configuration
st.set_page_config(
    page_title="Fluent CRM Contact Manager",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
def initialize_session_state():
    if 'api_username' not in st.session_state:
        st.session_state.api_username = ""
    if 'api_password' not in st.session_state:
        st.session_state.api_password = ""
    if 'base_url' not in st.session_state:
        st.session_state.base_url = "https://videmicorp.com"
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'contacts_cache' not in st.session_state:
        st.session_state.contacts_cache = None
    if 'custom_fields_cache' not in st.session_state:
        st.session_state.custom_fields_cache = None
    if 'error_log' not in st.session_state:
        st.session_state.error_log = []

initialize_session_state()

# Helper function to log errors
def log_error(error_message, error_details=None):
    """Log errors to session state for debugging"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    error_entry = {
        "timestamp": timestamp,
        "message": error_message,
        "details": error_details
    }
    st.session_state.error_log.append(error_entry)
    # Keep only the last 100 errors
    if len(st.session_state.error_log) > 100:
        st.session_state.error_log = st.session_state.error_log[-100:]

# Authentication in sidebar
with st.sidebar:
    st.title("🔐 Authentication")
    
    # Input fields for authentication
    st.session_state.base_url = st.text_input("Base URL", st.session_state.base_url)
    st.session_state.api_username = st.text_input("API Username", st.session_state.api_username)
    st.session_state.api_password = st.text_input("API Password", st.session_state.api_password, type="password")
    
    # Test connection button
    if st.button("🔗 Test Connection"):
        if not st.session_state.api_username or not st.session_state.api_password:
            st.error("Please enter API credentials")
        else:
            with st.spinner("Testing connection..."):
                try:
                    # Clean up base URL
                    base_url = st.session_state.base_url.rstrip('/')
                    
                    response = requests.get(
                        f"{base_url}/wp-json/fluent-crm/v2/subscribers?per_page=1",
                        auth=(st.session_state.api_username, st.session_state.api_password),
                        timeout=10
                    )
                    if response.status_code == 200:
                        st.success("✅ Connection successful!")
                        st.session_state.authenticated = True
                        # Clear caches on successful authentication
                        st.session_state.contacts_cache = None
                        st.session_state.custom_fields_cache = None
                    else:
                        st.error(f"❌ Connection failed: {response.status_code}")
                        if response.status_code == 401:
                            st.error("Invalid credentials")
                        elif response.status_code == 404:
                            st.error("FluentCRM API not found. Check your base URL.")
                        st.session_state.authenticated = False
                        log_error(f"Connection failed with status code {response.status_code}", 
                                 response.text if hasattr(response, 'text') else None)
                except requests.exceptions.Timeout:
                    st.error("⏱️ Connection timeout. Please check your URL.")
                    st.session_state.authenticated = False
                    log_error("Connection timeout")
                except requests.exceptions.ConnectionError:
                    st.error("🔌 Connection error. Please check your URL.")
                    st.session_state.authenticated = False
                    log_error("Connection error")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    st.session_state.authenticated = False
                    log_error(f"Authentication error: {str(e)}")
    
    # Show connection status
    if st.session_state.authenticated:
        st.success("🟢 Connected")
    else:
        st.warning("🔴 Not connected")
    
    # Navigation
    st.title("📋 Navigation")
    page = st.radio(
        "Select a page",
        ["View Contacts", "Create Contact", "Custom Fields", "Export Options", "Debug Log"]
    )

# Helper functions
def get_auth():
    return (st.session_state.api_username, st.session_state.api_password)

def get_base_url():
    return st.session_state.base_url.rstrip('/')

def check_auth():
    if not st.session_state.authenticated:
        st.warning("⚠️ Please authenticate in the sidebar first")
        return False
    return True

def safe_get(obj, key, default=""):
    """Safely get a value from a dictionary"""
    try:
        value = obj.get(key, default)
        return str(value) if value is not None else default
    except:
        return default

def make_api_request(endpoint, method='GET', data=None, timeout=15):
    """Make API request with proper error handling"""
    try:
        url = f"{get_base_url()}/wp-json/fluent-crm/v2/{endpoint}"
        
        if method == 'GET':
            response = requests.get(url, auth=get_auth(), timeout=timeout)
        elif method == 'POST':
            response = requests.post(url, auth=get_auth(), json=data, timeout=timeout)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return response
    except requests.exceptions.Timeout:
        st.error("⏱️ Request timeout. Please try again.")
        log_error(f"API request timeout for {endpoint}")
        return None
    except requests.exceptions.ConnectionError:
        st.error("🔌 Connection error. Please check your connection.")
        log_error(f"API connection error for {endpoint}")
        return None
    except Exception as e:
        st.error(f"❌ Request error: {str(e)}")
        log_error(f"API request error for {endpoint}", str(e))
        return None

def get_download_link(data, filename, text):
    """Generate a link to download the data"""
    try:
        json_str = json.dumps(data, indent=4)
        b64 = base64.b64encode(json_str.encode()).decode()
        href = f'<a href="data:file/json;base64,{b64}" download="{filename}">{text}</a>'
        return href
    except Exception as e:
        log_error(f"Error generating download link: {str(e)}")
        return f"<p>Error generating download link: {str(e)}</p>"

def fetch_contacts(use_cache=True, max_contacts=None):
    """Fetch contacts with caching and pagination support"""
    if not check_auth():
        return []
    
    if use_cache and st.session_state.contacts_cache is not None:
        return st.session_state.contacts_cache
    
    all_contacts = []
    page = 1
    per_page = 100
    
    # Show progress for large datasets
    progress_placeholder = st.empty()
    
    while True:
        progress_placeholder.info(f"📥 Fetching contacts... Page {page}")
        
        # Build the query parameters
        params = f"per_page={per_page}&page={page}&custom_fields=true"
        response = make_api_request(f"subscribers?{params}")
        
        if not response or response.status_code != 200:
            if response:
                st.error(f"Failed to fetch contacts on page {page}: {response.status_code}")
                log_error(f"Failed to fetch contacts on page {page}", 
                         f"Status code: {response.status_code}, Response: {response.text if hasattr(response, 'text') else 'No response text'}")
            break
        
        try:
            data = response.json()
        except Exception as e:
            st.error(f"Failed to parse JSON response: {str(e)}")
            log_error("Failed to parse JSON response", str(e))
            break
        
        # Handle the paginated response structure
        if isinstance(data, dict) and 'data' in data:
            contacts_batch = data['data']
            pagination_info = {
                'current_page': data.get('current_page', page),
                'per_page': data.get('per_page', per_page),
                'total': data.get('total', 0),
                'last_page': data.get('last_page', 1)
            }
        else:
            # Fallback for non-paginated response
            contacts_batch = data if isinstance(data, list) else []
            pagination_info = {'current_page': 1, 'last_page': 1, 'total': len(contacts_batch)}
        
        if not contacts_batch:
            break
        
        # Validate each contact has an ID before adding to the list
        valid_contacts = 0
        for contact in contacts_batch:
            if isinstance(contact, dict) and contact.get("id") is not None:
                all_contacts.append(contact)
                valid_contacts += 1
            else:
                log_error("Skipped invalid contact without ID", str(contact))
        
        if valid_contacts == 0:
            st.warning(f"No valid contacts found on page {page}")
        
        # Check if we've reached the maximum requested contacts
        if max_contacts and len(all_contacts) >= max_contacts:
            all_contacts = all_contacts[:max_contacts]
            break
        
        # Check if we've reached the last page
        if pagination_info['current_page'] >= pagination_info['last_page']:
            break
        
        page += 1
        
        # Safety limit to prevent infinite loops
        if page > 1000:  # Reasonable limit
            st.warning("⚠️ Reached maximum page limit (1000). Some contacts may not be loaded.")
            log_error("Reached maximum page limit (1000)")
            break
    
    progress_placeholder.empty()
    
    # Cache the results
    st.session_state.contacts_cache = all_contacts
    
    return all_contacts

def fetch_custom_fields(use_cache=True):
    """Fetch custom fields with caching"""
    if not check_auth():
        return []
    
    if use_cache and st.session_state.custom_fields_cache is not None:
        return st.session_state.custom_fields_cache
    
    response = make_api_request("custom-fields/contacts")
    if response and response.status_code == 200:
        try:
            data = response.json()
            fields = data.get('fields', []) if isinstance(data, dict) else data
            st.session_state.custom_fields_cache = fields
            return fields
        except Exception as e:
            st.error(f"Failed to parse custom fields: {str(e)}")
            log_error("Failed to parse custom fields", str(e))
            return []
    else:
        if response:
            st.error(f"Failed to fetch custom fields: {response.status_code}")
            log_error(f"Failed to fetch custom fields: {response.status_code}", 
                     response.text if hasattr(response, 'text') else None)
        return []

def fetch_tags_and_lists():
    """Fetch tags and lists"""
    if not check_auth():
        return [], []
    
    tags_response = make_api_request("tags")
    lists_response = make_api_request("lists")
    
    tags = []
    lists = []
    
    if tags_response and tags_response.status_code == 200:
        try:
            tags_data = tags_response.json()
            tags = tags_data.get('data', []) if isinstance(tags_data, dict) and 'data' in tags_data else tags_data
        except Exception as e:
            st.error(f"Failed to parse tags: {str(e)}")
            log_error("Failed to parse tags", str(e))
    
    if lists_response and lists_response.status_code == 200:
        try:
            lists_data = lists_response.json()
            lists = lists_data.get('data', []) if isinstance(lists_data, dict) and 'data' in lists_data else lists_data
        except Exception as e:
            st.error(f"Failed to parse lists: {str(e)}")
            log_error("Failed to parse lists", str(e))
    
    return tags, lists

def convert_to_n8n(contacts):
    """Convert contacts to n8n workflow format"""
    try:
        n8n_nodes = {
            "nodes": [],
            "connections": {}
        }
        
        for i, contact in enumerate(contacts):
            node_id = f"contact_{i}"
            n8n_nodes["nodes"].append({
                "id": node_id,
                "name": f"Contact: {safe_get(contact, 'full_name', 'Unknown')}",
                "type": "n8n-nodes-base.set",
                "position": [i * 300, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "id", "value": safe_get(contact, 'id', '')},
                            {"name": "email", "value": safe_get(contact, 'email', '')},
                            {"name": "full_name", "value": safe_get(contact, 'full_name', '')},
                            {"name": "status", "value": safe_get(contact, 'status', '')}
                        ]
                    }
                }
            })
            
            if i > 0:
                prev_node_id = f"contact_{i-1}"
                n8n_nodes["connections"][prev_node_id] = {
                    "main": [[{"node": node_id, "type": "main", "index": 0}]]
                }
        
        return n8n_nodes
    except Exception as e:
        log_error("Error converting contacts to n8n format", str(e))
        st.error(f"Error converting contacts to n8n format: {str(e)}")
        return {"nodes": [], "connections": {}}

# Page functions
def view_contacts_page():
    st.title("👥 View Contacts")
    
    if not check_auth():
        return
    
    # Add refresh and options
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        if st.button("🔄 Refresh"):
            st.session_state.contacts_cache = None
            st.rerun()
    
    with col2:
        max_contacts = st.number_input("Max contacts to load", min_value=10, max_value=10000, value=1000, step=10)
    
    # Fetch contacts
    with st.spinner("Loading contacts..."):
        contacts = fetch_contacts(use_cache=False if st.session_state.get('refresh_contacts', False) else True, 
                                max_contacts=max_contacts)
    
    if not contacts:
        st.info("📭 No contacts found or unable to fetch contacts.")
        return
    
    st.success(f"📊 Loaded {len(contacts)} contacts")
    
    # Add search functionality
    search_term = st.text_input("🔍 Search contacts", placeholder="Search by name or email...")
    
    # Filter contacts based on search
    if search_term:
        filtered_contacts = []
        search_lower = search_term.lower()
        for c in contacts:
            name = str(c.get("full_name", "")).lower()
            email = str(c.get("email", "")).lower()
            if search_lower in name or search_lower in email:
                filtered_contacts.append(c)
        contacts = filtered_contacts
        st.info(f"🔍 Found {len(contacts)} contacts matching '{search_term}'")
    
    # Display contacts in a table
    if contacts:
        contact_data = []
        for c in contacts:
            # Safely get values with proper error handling
            try:
                contact_data.append({
                    "ID": str(c.get("id", "")) if c.get("id") is not None else "",
                    "Name": str(c.get("full_name", "")),
                    "Email": str(c.get("email", "")),
                    "Status": str(c.get("status", "")),
                    "Phone": str(c.get("phone", "")),
                    "Type": str(c.get("contact_type", "")),
                    "Source": str(c.get("source", "")),
                    "Created": str(c.get("created_at", ""))
                })
            except Exception as e:
                st.warning(f"Skipped a contact due to error: {str(e)}")
                log_error("Error processing contact for display", str(e))
                continue
        
        if not contact_data:
            st.warning("No valid contacts to display after filtering")
            return
            
        contact_df = pd.DataFrame(contact_data)
        st.dataframe(contact_df, use_container_width=True)
        
        # Contact details
        st.subheader("📋 Contact Details")
        
        contact_options = []
        for c in contacts:
            try:
                contact_id = c.get("id")
                if contact_id is None:
                    continue
                    
                name = str(c.get("full_name", "Unknown"))
                email = str(c.get("email", ""))
                display_name = f"{name} ({email})" if email else name
                contact_options.append((contact_id, display_name))
            except Exception as e:
                log_error("Error processing contact for selection", str(e))
                continue
        
        if contact_options:
            selected_contact_id = st.selectbox(
                "Select a contact to view details",
                options=[option[0] for option in contact_options],
                format_func=lambda x: next((option[1] for option in contact_options if option[0] == x), "")
            )
            
            if selected_contact_id:
                selected_contact = next((c for c in contacts if c.get("id") == selected_contact_id), None)
                if selected_contact:
                    display_contact_details(selected_contact)

def display_contact_details(contact):
    """Display detailed contact information"""
    col1, col2 = st.columns(2)
    
    with col1:
        photo_url = safe_get(contact, "photo", "https://www.gravatar.com/avatar/00000000000000000000000000000000?s=128")
        try:
            st.image(photo_url, width=100)
        except:
            st.write("📷 Photo not available")
        
        st.write(f"**👤 Name:** {safe_get(contact, 'prefix', '')} {safe_get(contact, 'full_name', 'Unknown')}")
        st.write(f"**📧 Email:** {safe_get(contact, 'email', 'N/A')}")
        st.write(f"**📱 Phone:** {safe_get(contact, 'phone', 'N/A')}")
        st.write(f"**📊 Status:** {safe_get(contact, 'status', 'N/A')}")
        st.write(f"**👥 Type:** {safe_get(contact, 'contact_type', 'N/A')}")
        st.write(f"**🎂 Date of Birth:** {safe_get(contact, 'date_of_birth', 'N/A')}")
    
    with col2:
        st.write(f"**🏠 Address:** {safe_get(contact, 'address_line_1', 'N/A')}")
        st.write(f"**🏠 Address Line 2:** {safe_get(contact, 'address_line_2', 'N/A')}")
        st.write(f"**🏙️ City:** {safe_get(contact, 'city', 'N/A')}")
        st.write(f"**🗺️ State:** {safe_get(contact, 'state', 'N/A')}")
        st.write(f"**📮 Postal Code:** {safe_get(contact, 'postal_code', 'N/A')}")
        st.write(f"**🌍 Country:** {safe_get(contact, 'country', 'N/A')}")
        st.write(f"**📍 Source:** {safe_get(contact, 'source', 'N/A')}")
        st.write(f"**💰 Lifetime Value:** {safe_get(contact, 'life_time_value', '0')}")
    
    # Additional information
    col3, col4 = st.columns(2)
    
    with col3:
        # Tags
        st.subheader("🏷️ Tags")
        tags = contact.get("tags", [])
        if tags and isinstance(tags, list):
            tag_names = []
            for tag in tags:
                if isinstance(tag, dict):
                    tag_title = tag.get("title", "Unknown")
                    st.badge(tag_title, type="secondary")
                    tag_names.append(tag_title)
            if not tag_names:
                st.write("No valid tags")
        else:
            st.write("No tags")
    
    with col4:
        # Lists
        st.subheader("📋 Lists")
        lists = contact.get("lists", [])
        if lists and isinstance(lists, list):
            list_names = []
            for lst in lists:
                if isinstance(lst, dict):
                    list_title = lst.get("title", "Unknown")
                    st.badge(list_title, type="primary")
                    list_names.append(list_title)
            if not list_names:
                st.write("No valid lists")
        else:
            st.write("No lists")
    
    # Custom fields if available
    custom_fields = contact.get("custom_fields")
    if custom_fields and isinstance(custom_fields, dict):
        st.subheader("⚙️ Custom Fields")
        for key, value in custom_fields.items():
            if value:  # Only show non-empty values
                st.write(f"**{key}:** {value}")
    
    # Export individual contact
    col_export1, col_export2 = st.columns(2)
    with col_export1:
        if st.button("💾 Export this contact"):
            st.markdown(
                get_download_link(
                    contact, 
                    f"contact_{safe_get(contact, 'id')}.json", 
                    "📥 Download Contact JSON"
                ),
                unsafe_allow_html=True
            )
    
    with col_export2:
        if st.button("📋 Copy Contact ID"):
            st.code(safe_get(contact, 'id', ''), language=None)

def create_contact_page():
    st.title("➕ Create New Contact")
    
    if not check_auth():
        return
    
    # Fetch required data
    with st.spinner("Loading form data..."):
        custom_fields = fetch_custom_fields()
        tags, lists = fetch_tags_and_lists()
    
    # Contact form
    with st.form(key="contact_form"):
        st.subheader("👤 Contact Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            prefix = st.text_input("Prefix (Mr, Mrs, etc.)")
            first_name = st.text_input("First Name")
            last_name = st.text_input("Last Name")
            email = st.text_input("Email *", help="Required field")
            phone = st.text_input("Phone")
            dob = st.date_input("Date of Birth", value=None)
            
        with col2:
            address_line_1 = st.text_input("Address Line 1")
            address_line_2 = st.text_input("Address Line 2")
            city = st.text_input("City")
            state = st.text_input("State")
            postal_code = st.text_input("Postal Code")
            country = st.text_input("Country")
        
        status = st.selectbox(
            "Status",
            options=["subscribed", "pending", "unsubscribed", "bounced", "complained"],
            index=0
        )
        
        # Tags and Lists
        selected_tags = []
        selected_lists = []
        
        if tags:
            tag_options = [(tag.get("id"), tag.get("title", "Unknown")) for tag in tags if isinstance(tag, dict)]
            if tag_options:
                selected_tag_ids = st.multiselect(
                    "🏷️ Tags",
                    options=[option[0] for option in tag_options],
                    format_func=lambda x: next((option[1] for option in tag_options if option[0] == x), "Unknown")
                )
                selected_tags = selected_tag_ids
        
        if lists:
            list_options = [(lst.get("id"), lst.get("title", "Unknown")) for lst in lists if isinstance(lst, dict)]
            if list_options:
                selected_list_ids = st.multiselect(
                    "📋 Lists",
                    options=[option[0] for option in list_options],
                    format_func=lambda x: next((option[1] for option in list_options if option[0] == x), "Unknown")
                )
                selected_lists = selected_list_ids
        
        # Custom fields
        custom_values = {}
        if custom_fields:
            st.subheader("⚙️ Custom Fields")
            
            for field in custom_fields:
                if not isinstance(field, dict):
                    continue
                    
                field_type = field.get("type")
                field_key = field.get("slug")
                field_label = field.get("label")
                field_options = field.get("options", [])
                
                if not field_key or not field_label:
                    continue
                
                if field_type == "text":
                    custom_values[field_key] = st.text_input(field_label)
                elif field_type == "select-one" and field_options:
                    custom_values[field_key] = st.selectbox(field_label, options=[""] + field_options)
                elif field_type == "radio" and field_options:
                    custom_values[field_key] = st.radio(field_label, options=field_options)
                elif field_type == "checkbox" and field_options:
                    selected_options = st.multiselect(field_label, options=field_options)
                    custom_values[field_key] = selected_options
        
        # Submit button
        submitted = st.form_submit_button("✅ Create Contact")
        
        if submitted:
            if not email:
                st.error("❌ Email is required")
            elif not email.strip():
                st.error("❌ Email cannot be empty")
            else:
                # Prepare data
                contact_data = {
                    "email": email.strip(),
                    "status": status,
                }
                
                # Add optional fields only if they have values
                if first_name.strip():
                    contact_data["first_name"] = first_name.strip()
                if last_name.strip():
                    contact_data["last_name"] = last_name.strip()
                if prefix.strip():
                    contact_data["prefix"] = prefix.strip()
                if phone.strip():
                    contact_data["phone"] = phone.strip()
                if address_line_1.strip():
                    contact_data["address_line_1"] = address_line_1.strip()
                if address_line_2.strip():
                    contact_data["address_line_2"] = address_line_2.strip()
                if city.strip():
                    contact_data["city"] = city.strip()
                if state.strip():
                    contact_data["state"] = state.strip()
                if postal_code.strip():
                    contact_data["postal_code"] = postal_code.strip()
                if country.strip():
                    contact_data["country"] = country.strip()
                
                if dob:
                    contact_data["date_of_birth"] = dob.strftime("%Y-%m-%d")
                
                if selected_tags:
                    contact_data["tags"] = selected_tags
                
                if selected_lists:
                    contact_data["lists"] = selected_lists
                
                # Add custom values (only non-empty ones)
                filtered_custom_values = {k: v for k, v in custom_values.items() if v}
                if filtered_custom_values:
                    contact_data["custom_values"] = filtered_custom_values
                
                # Create contact
                with st.spinner("Creating contact..."):
                    response = make_api_request("subscribers", method="POST", data=contact_data)
                    
                    if response and response.status_code in [200, 201]:
                        st.success("✅ Contact created successfully!")
                        # Clear contacts cache
                        st.session_state.contacts_cache = None
                        # Show created contact details
                        try:
                            with st.expander("📋 Created Contact Details"):
                                st.json(response.json())
                        except Exception as e:
                            st.error(f"Error displaying contact details: {str(e)}")
                            log_error("Error displaying created contact details", str(e))
                    else:
                        if response:
                            st.error(f"❌ Failed to create contact: {response.status_code}")
                            if response.text:
                                st.error(f"Details: {response.text}")
                            log_error(f"Failed to create contact: {response.status_code}", response.text)

def custom_fields_page():
    st.title("⚙️ Custom Fields")
    
    if not check_auth():
        return
    
    # Add refresh button
    if st.button("🔄 Refresh Custom Fields"):
        st.session_state.custom_fields_cache = None
    
    # Fetch custom fields
    with st.spinner("Loading custom fields..."):
        custom_fields = fetch_custom_fields()
    
    if not custom_fields:
        st.info("📭 No custom fields found or unable to fetch custom fields.")
        return
    
    st.success(f"📊 Found {len(custom_fields)} custom fields")
    
    # Display custom fields
    for field in custom_fields:
        if not isinstance(field, dict):
            continue
            
        field_label = field.get('label', 'Unknown')
        field_type = field.get('type', 'Unknown')
        
        with st.expander(f"{field_label} ({field_type})"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**🏷️ Label:** {field_label}")
                st.write(f"**🔑 Field Key:** {safe_get(field, 'field_key', 'N/A')}")
                st.write(f"**📝 Slug:** {safe_get(field, 'slug', 'N/A')}")
            
            with col2:
                st.write(f"**🔧 Type:** {field_type}")
                st.write(f"**📋 Group:** {safe_get(field, 'group', 'N/A')}")
                st.write(f"**✅ Required:** {field.get('required', False)}")
            
            if field.get('options'):
                st.write("**📋 Options:**")
                options = field.get('options', [])
                if isinstance(options, list):
                    options_text = ", ".join(str(opt) for opt in options)
                    st.write(options_text)
                else:
                    st.write(f"Invalid options format: {options}")
            
            if field.get('help_text'):
                st.write(f"**ℹ️ Help Text:** {safe_get(field, 'help_text')}")

def export_options_page():
    st.title("📤 Export Options")
    
    if not check_auth():
        return
    
    # Fetch contacts
    with st.spinner("Loading contacts for export..."):
        contacts = fetch_contacts()
    
    if not contacts:
        st.info("📭 No contacts found or unable to fetch contacts.")
        return
    
    # Export all contacts to JSON
    st.subheader("📊 Export All Contacts")
    st.write(f"Total contacts available: {len(contacts)}")
    
    if st.button("💾 Export All Contacts to JSON"):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        st.markdown(
            get_download_link(
                contacts, 
                f"all_contacts_{timestamp}.json", 
                "📥 Download All Contacts JSON"
            ),
            unsafe_allow_html=True
        )
    
    # Export to n8n format
    st.subheader("🔄 Export to n8n Format")
    
    # Allow selecting contacts to export
    contact_options = []
    for c in contacts:
        try:
            contact_id = c.get("id")
            if contact_id is None:
                continue
                
            name = safe_get(c, "full_name", "Unknown")
            email = safe_get(c, "email", "")
            display_name = f"{name} ({email})" if email else name
            contact_options.append((contact_id, display_name))
        except Exception as e:
            log_error("Error processing contact for export selection", str(e))
            continue
    
    if contact_options:
        selected_contact_ids = st.multiselect(
            "Select contacts to export to n8n",
            options=[option[0] for option in contact_options],
            format_func=lambda x: next((option[1] for option in contact_options if option[0] == x), "")
        )
        
        if selected_contact_ids:
            selected_contacts = [c for c in contacts if c.get("id") in selected_contact_ids]
            st.write(f"Selected {len(selected_contacts)} contacts for export")
            
            if st.button("🔄 Export Selected Contacts to n8n Format"):
                n8n_data = convert_to_n8n(selected_contacts)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                st.markdown(
                    get_download_link(
                        n8n_data, 
                        f"n8n_workflow_{timestamp}.json", 
                        "📥 Download n8n Workflow JSON"
                    ),
                    unsafe_allow_html=True
                )
    
    # Export custom fields
    st.subheader("⚙️ Export Custom Fields")
    if st.button("💾 Export Custom Fields to JSON"):
        custom_fields = fetch_custom_fields()
        if custom_fields:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            st.markdown(
                get_download_link(
                    custom_fields, 
                    f"custom_fields_{timestamp}.json", 
                    "📥 Download Custom Fields JSON"
                ),
                unsafe_allow_html=True
            )
        else:
            st.warning("⚠️ No custom fields found to export")

def debug_log_page():
    """Display debug logs for troubleshooting"""
    st.title("🐞 Debug Log")
    
    if st.button("🧹 Clear Log"):
        st.session_state.error_log = []
        st.success("Log cleared")
    
    if not st.session_state.error_log:
        st.info("No errors logged yet.")
        return
    
    st.write(f"Total errors logged: {len(st.session_state.error_log)}")
    
    # Display logs in reverse chronological order
    for i, log_entry in enumerate(reversed(st.session_state.error_log)):
        with st.expander(f"{log_entry['timestamp']} - {log_entry['message']}"):
            st.write(f"**Timestamp:** {log_entry['timestamp']}")
            st.write(f"**Message:** {log_entry['message']}")
            if log_entry['details']:
                st.write("**Details:**")
                st.code(str(log_entry['details']))

# Main app logic
def main():
    # Add app info
    st.markdown("---")
    st.markdown("*Fluent CRM Contact Manager - A Streamlit application for managing FluentCRM contacts*")
    
    # Route to appropriate page
    if page == "View Contacts":
        view_contacts_page()
    elif page == "Create Contact":
        create_contact_page()
    elif page == "Custom Fields":
        custom_fields_page()
    elif page == "Export Options":
        export_options_page()
    elif page == "Debug Log":
        debug_log_page()

if __name__ == "__main__":
    main()
