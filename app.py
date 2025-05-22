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

def fetch_contacts(use_cache=True):
    """Fetch contacts with caching"""
    if not check_auth():
        return []
    
    if use_cache and st.session_state.contacts_cache is not None:
        return st.session_state.contacts_cache
    
    response = make_api_request("subscribers?per_page=100")
    if response and response.status_code == 200:
        data = response.json()
        contacts = data.get('data', [])
        st.session_state.contacts_cache = contacts
        return contacts
    else:
        if response:
            st.error(f"Failed to fetch contacts: {response.status_code}")
        return []

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
    
    # Add refresh button
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh"):
            st.session_state.contacts_cache = None
    
    # Fetch contacts
    with st.spinner("Loading contacts..."):
        contacts = fetch_contacts(use_cache=False if st.button("🔄 Refresh", key="hidden") else True)
    
    if not contacts:
        st.info("📭 No contacts found or unable to fetch contacts.")
        return
    
    st.success(f"📊 Found {len(contacts)} contacts")
    
    # Display contacts in a table
    contact_data = []
    for c in contacts:
        contact_data.append({
            "ID": c.get("id", ""),
            "Name": c.get("full_name", ""),
            "Email": c.get("email", ""),
            "Status": c.get("status", ""),
            "Phone": c.get("phone", ""),
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
                col1, col2 = st.columns(2)
                
                with col1:
                    photo_url = selected_contact.get("photo", "https://www.gravatar.com/avatar/00000000000000000000000000000000?s=128")
                    st.image(photo_url, width=100)
                    
                    st.write(f"**👤 Name:** {selected_contact.get('prefix', '')} {selected_contact.get('full_name', 'Unknown')}")
                    st.write(f"**📧 Email:** {selected_contact.get('email', 'N/A')}")
                    st.write(f"**📱 Phone:** {selected_contact.get('phone', 'N/A')}")
                    st.write(f"**📊 Status:** {selected_contact.get('status', 'N/A')}")
                    st.write(f"**🎂 Date of Birth:** {selected_contact.get('date_of_birth', 'N/A')}")
                
                with col2:
                    st.write(f"**🏠 Address:** {selected_contact.get('address_line_1', 'N/A')}")
                    st.write(f"**🏠 Address Line 2:** {selected_contact.get('address_line_2', 'N/A')}")
                    st.write(f"**🏙️ City:** {selected_contact.get('city', 'N/A')}")
                    st.write(f"**🗺️ State:** {selected_contact.get('state', 'N/A')}")
                    st.write(f"**📮 Postal Code:** {selected_contact.get('postal_code', 'N/A')}")
                    st.write(f"**🌍 Country:** {selected_contact.get('country', 'N/A')}")
                
                # Tags and Lists
                st.subheader("🏷️ Tags")
                tags = selected_contact.get("tags", [])
                if tags:
                    tag_names = [tag.get("title", "Unknown") for tag in tags if isinstance(tag, dict)]
                    st.write(", ".join(tag_names))
                else:
                    st.write("No tags")
                
                st.subheader("📋 Lists")
                lists = selected_contact.get("lists", [])
                if lists:
                    list_names = [lst.get("title", "Unknown") for lst in lists if isinstance(lst, dict)]
                    st.write(", ".join(list_names))
                else:
                    st.write("No lists")
                
                # Export individual contact
                if st.button("💾 Export this contact"):
                    st.markdown(
                        get_download_link(
                            selected_contact, 
                            f"contact_{selected_contact.get('id')}.json", 
                            "📥 Download Contact JSON"
                        ),
                        unsafe_allow_html=True
                    )

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
