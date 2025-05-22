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

initialize_session_state()

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
                except requests.exceptions.Timeout:
                    st.error("⏱️ Connection timeout. Please check your URL.")
                    st.session_state.authenticated = False
                except requests.exceptions.ConnectionError:
                    st.error("🔌 Connection error. Please check your URL.")
                    st.session_state.authenticated = False
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    st.session_state.authenticated = False
    
    # Show connection status
    if st.session_state.authenticated:
        st.success("🟢 Connected")
    else:
        st.warning("🔴 Not connected")
    
    # Navigation
    st.title("📋 Navigation")
    page = st.radio(
        "Select a page",
        ["View Contacts", "Create Contact", "Custom Fields", "Export Options"]
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
        return None
    except requests.exceptions.ConnectionError:
        st.error("🔌 Connection error. Please check your connection.")
        return None
    except Exception as e:
        st.error(f"❌ Request error: {str(e)}")
        return None

def get_download_link(data, filename, text):
    """Generate a link to download the data"""
    json_str = json.dumps(data, indent=4)
    b64 = base64.b64encode(json_str.encode()).decode()
    href = f'<a href="data:file/json;base64,{b64}" download="{filename}">{text}</a>'
    return href

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
            break
        
        data = response.json()
        
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
        
        all_contacts.extend(contacts_batch)
        
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
        data = response.json()
        fields = data.get('fields', []) if isinstance(data, dict) else data
        st.session_state.custom_fields_cache = fields
        return fields
    else:
        if response:
            st.error(f"Failed to fetch custom fields: {response.status_code}")
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
        tags_data = tags_response.json()
        tags = tags_data.get('data', []) if isinstance(tags_data, dict) and 'data' in tags_data else tags_data
    
    if lists_response and lists_response.status_code == 200:
        lists_data = lists_response.json()
        lists = lists_data.get('data', []) if isinstance(lists_data, dict) and 'data' in lists_data else lists_data
    
    return tags, lists

def convert_to_n8n(contacts):
    """Convert contacts to n8n workflow format"""
    n8n_nodes = {
        "nodes": [],
        "connections": {}
    }
    
    for i, contact in enumerate(contacts):
        node_id = f"contact_{i}"
        n8n_nodes["nodes"].append({
            "id": node_id,
            "name": f"Contact: {contact.get('full_name', 'Unknown')}",
            "type": "n8n-nodes-base.set",
            "position": [i * 300, 300],
            "parameters": {
                "values": {
                    "string": [
                        {"name": "id", "value": str(contact.get('id', ''))},
                        {"name": "email", "value": contact.get('email', '')},
                        {"name": "full_name", "value": contact.get('full_name', '')},
                        {"name": "status", "value": contact.get('status', '')}
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
            name = c.get("full_name", "").lower()
            email = c.get("email", "").lower()
            if search_lower in name or search_lower in email:
                filtered_contacts.append(c)
        contacts = filtered_contacts
        st.info(f"🔍 Found {len(contacts)} contacts matching '{search_term}'")
    
    # Display contacts in a table
    if contacts:
        contact_data = []
        for c in contacts:
            contact_data.append({
                "ID": c.get("id", ""),
                "Name": c.get("full_name", ""),
                "Email": c.get("email", ""),
                "Status": c.get("status", ""),
                "Phone": c.get("phone", ""),
                "Type": c.get("contact_type", ""),
                "Source": c.get("source", ""),
                "Created": c.get("created_at", "")
            })
        
        contact_df = pd.DataFrame(contact_data)
        st.dataframe(contact_df, use_container_width=True)
        
        # Contact details
        st.subheader("📋 Contact Details")
        
        contact_options = []
        for c in contacts:
            name = c.get("full_name", "Unknown")
            email = c.get("email", "")
            display_name = f"{name} ({email})" if email else name
            contact_options.append((c.get("id"), display_name))
        
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
        photo_url = contact.get("photo", "https://www.gravatar.com/avatar/00000000000000000000000000000000?s=128")
        try:
            st.image(photo_url, width=100)
        except:
            st.write("📷 Photo not available")
        
        st.write(f"**👤 Name:** {contact.get('prefix', '')} {contact.get('full_name', 'Unknown')}")
        st.write(f"**📧 Email:** {contact.get('email', 'N/A')}")
        st.write(f"**📱 Phone:** {contact.get('phone', 'N/A')}")
        st.write(f"**📊 Status:** {contact.get('status', 'N/A')}")
        st.write(f"**👥 Type:** {contact.get('contact_type', 'N/A')}")
        st.write(f"**🎂 Date of Birth:** {contact.get('date_of_birth', 'N/A')}")
    
    with col2:
        st.write(f"**🏠 Address:** {contact.get('address_line_1', 'N/A')}")
        st.write(f"**🏠 Address Line 2:** {contact.get('address_line_2', 'N/A')}")
        st.write(f"**🏙️ City:** {contact.get('city', 'N/A')}")
        st.write(f"**🗺️ State:** {contact.get('state', 'N/A')}")
        st.write(f"**📮 Postal Code:** {contact.get('postal_code', 'N/A')}")
        st.write(f"**🌍 Country:** {contact.get('country', 'N/A')}")
        st.write(f"**📍 Source:** {contact.get('source', 'N/A')}")
        st.write(f"**💰 Lifetime Value:** {contact.get('life_time_value', '0')}")
    
    # Additional information
    col3, col4 = st.columns(2)
    
    with col3:
        # Tags
        st.subheader("🏷️ Tags")
        tags = contact.get("tags", [])
        if tags:
            tag_names = [tag.get("title", "Unknown") for tag in tags if isinstance(tag, dict)]
            for tag in tags:
                if isinstance(tag, dict):
                    st.badge(tag.get("title", "Unknown"), type="secondary")
        else:
            st.write("No tags")
    
    with col4:
        # Lists
        st.subheader("📋 Lists")
        lists = contact.get("lists", [])
        if lists:
            for lst in lists:
                if isinstance(lst, dict):
                    st.badge(lst.get("title", "Unknown"), type="primary")
        else:
            st.write("No lists")
    
    # Custom fields if available
    if contact.get("custom_fields"):
        st.subheader("⚙️ Custom Fields")
        custom_fields = contact.get("custom_fields", {})
        if isinstance(custom_fields, dict):
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
                    f"contact_{contact.get('id')}.json", 
                    "📥 Download Contact JSON"
                ),
                unsafe_allow_html=True
            )
    
    with col_export2:
        if st.button("📋 Copy Contact ID"):
            st.code(contact.get('id', ''), language=None)

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
                        with st.expander("📋 Created Contact Details"):
                            st.json(response.json())
                    else:
                        if response:
                            st.error(f"❌ Failed to create contact: {response.status_code}")
                            if response.text:
                                st.error(f"Details: {response.text}")

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
                st.write(f"**🔑 Field Key:** {field.get('field_key', 'N/A')}")
                st.write(f"**📝 Slug:** {field.get('slug', 'N/A')}")
            
            with col2:
                st.write(f"**🔧 Type:** {field_type}")
                st.write(f"**📋 Group:** {field.get('group', 'N/A')}")
                st.write(f"**✅ Required:** {field.get('required', False)}")
            
            if field.get('options'):
                st.write("**📋 Options:**")
                options_text = ", ".join(field.get('options', []))
                st.write(options_text)
            
            if field.get('help_text'):
                st.write(f"**ℹ️ Help Text:** {field.get('help_text')}")

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
        name = c.get("full_name", "Unknown")
        email = c.get("email", "")
        display_name = f"{name} ({email})" if email else name
        contact_options.append((c.get("id"), display_name))
    
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

if __name__ == "__main__":
    main()
