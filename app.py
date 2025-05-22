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

# Authentication in sidebar
with st.sidebar:
    st.title("Authentication")
    
    # Store credentials in session state if not already there
    if 'api_username' not in st.session_state:
        st.session_state.api_username = ""
    if 'api_password' not in st.session_state:
        st.session_state.api_password = ""
    if 'base_url' not in st.session_state:
        st.session_state.base_url = "https://videmicorp.com"
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    # Input fields for authentication
    st.session_state.base_url = st.text_input("Base URL", st.session_state.base_url)
    st.session_state.api_username = st.text_input("API Username", st.session_state.api_username)
    st.session_state.api_password = st.text_input("API Password", st.session_state.api_password, type="password")
    
    # Test connection button
    if st.button("Test Connection"):
        if not st.session_state.api_username or not st.session_state.api_password:
            st.error("Please enter API credentials")
        else:
            try:
                response = requests.get(
                    f"{st.session_state.base_url}/wp-json/fluent-crm/v2/subscribers",
                    auth=(st.session_state.api_username, st.session_state.api_password),
                    timeout=10
                )
                if response.status_code == 200:
                    st.success("Connection successful!")
                    st.session_state.authenticated = True
                else:
                    st.error(f"Connection failed: {response.status_code} - {response.text}")
                    st.session_state.authenticated = False
            except Exception as e:
                st.error(f"Connection error: {str(e)}")
                st.session_state.authenticated = False
    
    # Navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select a page",
        ["View Contacts", "Create Contact", "Custom Fields", "Export Options"]
    )

# Helper function to get auth headers
def get_auth():
    return (st.session_state.api_username, st.session_state.api_password)

# Helper function to check authentication
def check_auth():
    if not hasattr(st.session_state, 'authenticated') or not st.session_state.authenticated:
        st.warning("Please authenticate in the sidebar first")
        return False
    return True

# Helper function to download data
def get_download_link(data, filename, text):
    """Generate a link to download the data"""
    json_str = json.dumps(data, indent=4)
    b64 = base64.b64encode(json_str.encode()).decode()
    href = f'<a href="data:file/json;base64,{b64}" download="{filename}">{text}</a>'
    return href

# Helper function to fetch all contacts
def fetch_contacts():
    if not check_auth():
        return []
    
    try:
        st.write("Attempting to fetch contacts...")  # Debug message
        response = requests.get(
            f"{st.session_state.base_url}/wp-json/fluent-crm/v2/subscribers?per_page=100",
            auth=get_auth(),
            timeout=15  # Increased timeout
        )
        st.write(f"Response status: {response.status_code}")  # Debug message
        
        if response.status_code == 200:
            data = response.json()
            st.write(f"Fetched {len(data.get('data', []))} contacts")  # Debug message
            return data.get('data', [])
        else:
            st.error(f"Failed to fetch contacts: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        st.error(f"Error fetching contacts: {str(e)}")
        return []

# Helper function to fetch custom fields
def fetch_custom_fields():
    if not check_auth():
        return []
    
    try:
        st.write("Attempting to fetch custom fields...")  # Debug message
        response = requests.get(
            f"{st.session_state.base_url}/wp-json/fluent-crm/v2/custom-fields/contacts",
            auth=get_auth(),
            timeout=15  # Increased timeout
        )
        st.write(f"Response status: {response.status_code}")  # Debug message
        
        if response.status_code == 200:
            data = response.json()
            st.write(f"Fetched {len(data.get('fields', []))} custom fields")  # Debug message
            return data.get('fields', [])
        else:
            st.error(f"Failed to fetch custom fields: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        st.error(f"Error fetching custom fields: {str(e)}")
        return []

# Helper function to convert contacts to n8n format
def convert_to_n8n(contacts):
    n8n_nodes = {
        "nodes": [],
        "connections": {}
    }
    
    # Create a simple workflow with contacts
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
                        {
                            "name": "id",
                            "value": contact.get('id', '')
                        },
                        {
                            "name": "email",
                            "value": contact.get('email', '')
                        },
                        {
                            "name": "full_name",
                            "value": contact.get('full_name', '')
                        },
                        {
                            "name": "status",
                            "value": contact.get('status', '')
                        }
                    ]
                }
            }
        })
        
        # Add connections between nodes
        if i > 0:
            prev_node_id = f"contact_{i-1}"
            if prev_node_id not in n8n_nodes["connections"]:
                n8n_nodes["connections"][prev_node_id] = {"main": [[{"node": node_id, "type": "main", "index": 0}]]}
    
    return n8n_nodes

# View Contacts Page
def view_contacts_page():
    st.title("View Contacts")
    
    if not check_auth():
        return
    
    # Fetch contacts
    with st.spinner("Loading contacts..."):
        contacts = fetch_contacts()
    
    if not contacts:
        st.info("No contacts found or unable to fetch contacts.")
        return
    
    # Display contacts in a table
    contact_df = pd.DataFrame([
        {
            "ID": c.get("id"),
            "Name": c.get("full_name"),
            "Email": c.get("email"),
            "Status": c.get("status"),
            "Phone": c.get("phone"),
            "Created": c.get("created_at")
        } for c in contacts
    ])
    
    st.dataframe(contact_df, use_container_width=True)
    
    # Contact details
    st.subheader("Contact Details")
    selected_contact_id = st.selectbox(
        "Select a contact to view details",
        options=[c.get("id") for c in contacts],
        format_func=lambda x: next((c.get("full_name", "Unknown") + " (" + c.get("email", "") + ")" for c in contacts if c.get("id") == x), "")
    )
    
    if selected_contact_id:
        selected_contact = next((c for c in contacts if c.get("id") == selected_contact_id), None)
        if selected_contact:
            col1, col2 = st.columns(2)
            
            with col1:
                st.image(selected_contact.get("photo", "https://www.gravatar.com/avatar/00000000000000000000000000000000?s=128"), width=100)
                st.write(f"**Name:** {selected_contact.get('prefix', '')} {selected_contact.get('full_name', 'Unknown')}")
                st.write(f"**Email:** {selected_contact.get('email', 'N/A')}")
                st.write(f"**Phone:** {selected_contact.get('phone', 'N/A')}")
                st.write(f"**Status:** {selected_contact.get('status', 'N/A')}")
                st.write(f"**Date of Birth:** {selected_contact.get('date_of_birth', 'N/A')}")
            
            with col2:
                st.write(f"**Address:** {selected_contact.get('address_line_1', 'N/A')}")
                st.write(f"**Address Line 2:** {selected_contact.get('address_line_2', 'N/A')}")
                st.write(f"**City:** {selected_contact.get('city', 'N/A')}")
                st.write(f"**State:** {selected_contact.get('state', 'N/A')}")
                st.write(f"**Postal Code:** {selected_contact.get('postal_code', 'N/A')}")
                st.write(f"**Country:** {selected_contact.get('country', 'N/A')}")
            
            # Tags and Lists
            st.subheader("Tags")
            tags = selected_contact.get("tags", [])
            if tags:
                st.write(", ".join([tag.get("title", "Unknown") for tag in tags]))
            else:
                st.write("No tags")
            
            st.subheader("Lists")
            lists = selected_contact.get("lists", [])
            if lists:
                st.write(", ".join([lst.get("title", "Unknown") for lst in lists]))
            else:
                st.write("No lists")
            
            # Export individual contact
            if st.button("Export this contact to JSON"):
                st.markdown(
                    get_download_link(
                        selected_contact, 
                        f"contact_{selected_contact.get('id')}.json", 
                        "Download Contact JSON"
                    ),
                    unsafe_allow_html=True
                )

# Create Contact Page
def create_contact_page():
    st.title("Create New Contact")
    
    if not check_auth():
        return
    
    # Fetch custom fields
    custom_fields = fetch_custom_fields()
    
    # Fetch tags and lists for dropdown
    try:
        tags_response = requests.get(
            f"{st.session_state.base_url}/wp-json/fluent-crm/v2/tags",
            auth=get_auth()
        )
        lists_response = requests.get(
            f"{st.session_state.base_url}/wp-json/fluent-crm/v2/lists",
            auth=get_auth()
        )
        
        tags = tags_response.json() if tags_response.status_code == 200 else []
        lists = lists_response.json() if lists_response.status_code == 200 else []
    except Exception as e:
        st.error(f"Error fetching tags/lists: {str(e)}")
        tags, lists = [], []
    
    # Contact form
    with st.form(key="contact_form"):
        st.subheader("Contact Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            prefix = st.text_input("Prefix (Mr, Mrs, etc.)")
            first_name = st.text_input("First Name")
            last_name = st.text_input("Last Name")
            email = st.text_input("Email")  # Removed required=True
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
        if tags:
            selected_tags = st.multiselect(
                "Tags",
                options=[tag.get("id") for tag in tags],
                format_func=lambda x: next((tag.get("title") for tag in tags if tag.get("id") == x), "Unknown")
            )
        else:
            selected_tags = []
            st.info("No tags available")
        
        if lists:
            selected_lists = st.multiselect(
                "Lists",
                options=[lst.get("id") for lst in lists],
                format_func=lambda x: next((lst.get("title") for lst in lists if lst.get("id") == x), "Unknown")
            )
        else:
            selected_lists = []
            st.info("No lists available")
        
        # Custom fields
        if custom_fields:
            st.subheader("Custom Fields")
            custom_values = {}
            
            for field in custom_fields:
                field_type = field.get("type")
                field_key = field.get("slug")
                field_label = field.get("label")
                field_options = field.get("options", [])
                
                if field_type == "text":
                    custom_values[field_key] = st.text_input(field_label)
                elif field_type == "select-one":
                    custom_values[field_key] = st.selectbox(field_label, options=field_options)
                elif field_type == "radio":
                    custom_values[field_key] = st.radio(field_label, options=field_options)
                elif field_type == "checkbox":
                    selected_options = st.multiselect(field_label, options=field_options)
                    custom_values[field_key] = selected_options
        else:
            custom_values = {}
        
        # Submit button - this is required in every form
        submitted = st.form_submit_button("Create Contact")
        
        if submitted:
            if not email:
                st.error("Email is required")
            else:
                # Prepare data
                contact_data = {
                    "email": email,
                    "status": status,
                    "first_name": first_name,
                    "last_name": last_name,
                    "prefix": prefix,
                    "phone": phone,
                    "address_line_1": address_line_1,
                    "address_line_2": address_line_2,
                    "city": city,
                    "state": state,
                    "postal_code": postal_code,
                    "country": country,
                }
                
                # Add date of birth if selected
                if dob:
                    contact_data["date_of_birth"] = dob.strftime("%Y-%m-%d")
                
                # Add tags and lists
                if selected_tags:
                    contact_data["tags"] = selected_tags
                
                if selected_lists:
                    contact_data["lists"] = selected_lists
                
                # Add custom values
                if custom_values:
                    contact_data["custom_values"] = custom_values
                
                # Create contact
                try:
                    st.write("Sending contact creation request...")  # Debug message
                    response = requests.post(
                        f"{st.session_state.base_url}/wp-json/fluent-crm/v2/subscribers",
                        auth=get_auth(),
                        json=contact_data
                    )
                    
                    st.write(f"Response status: {response.status_code}")  # Debug message
                    
                    if response.status_code in [200, 201]:
                        st.success("Contact created successfully!")
                        st.json(response.json())
                    else:
                        st.error(f"Failed to create contact: {response.status_code} - {response.text}")
                except Exception as e:
                    st.error(f"Error creating contact: {str(e)}")

# Custom Fields Page
def custom_fields_page():
    st.title("Custom Fields")
    
    if not check_auth():
        return
    
    # Fetch custom fields
    with st.spinner("Loading custom fields..."):
        custom_fields = fetch_custom_fields()
    
    if not custom_fields:
        st.info("No custom fields found or unable to fetch custom fields.")
        return
    
    # Display custom fields
    for field in custom_fields:
        with st.expander(f"{field.get('label')} ({field.get('type')})"):
            st.write(f"**Field Key:** {field.get('field_key')}")
            st.write(f"**Type:** {field.get('type')}")
            st.write(f"**Slug:** {field.get('slug')}")
            
            if field.get('options'):
                st.write("**Options:**")
                for option in field.get('options'):
                    st.write(f"- {option}")

# Export Options Page
def export_options_page():
    st.title("Export Options")
    
    if not check_auth():
        return
    
    # Fetch contacts
    with st.spinner("Loading contacts for export..."):
        contacts = fetch_contacts()
    
    if not contacts:
        st.info("No contacts found or unable to fetch contacts.")
        return
    
    # Export all contacts to JSON
    st.subheader("Export All Contacts")
    if st.button("Export All Contacts to JSON"):
        st.markdown(
            get_download_link(
                contacts, 
                f"all_contacts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 
                "Download All Contacts JSON"
            ),
            unsafe_allow_html=True
        )
    
    # Export to n8n format
    st.subheader("Export to n8n Format")
    
    # Allow selecting contacts to export
    selected_contact_ids = st.multiselect(
        "Select contacts to export to n8n",
        options=[c.get("id") for c in contacts],
        format_func=lambda x: next((c.get("full_name", "Unknown") + " (" + c.get("email", "") + ")" for c in contacts if c.get("id") == x), "")
    )
    
    if selected_contact_ids:
        selected_contacts = [c for c in contacts if c.get("id") in selected_contact_ids]
        
        if st.button("Export Selected Contacts to n8n Format"):
            n8n_data = convert_to_n8n(selected_contacts)
            st.markdown(
                get_download_link(
                    n8n_data, 
                    f"n8n_workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 
                    "Download n8n Workflow JSON"
                ),
                unsafe_allow_html=True
            )
    
    # Export custom fields
    st.subheader("Export Custom Fields")
    if st.button("Export Custom Fields to JSON"):
        custom_fields = fetch_custom_fields()
        if custom_fields:
            st.markdown(
                get_download_link(
                    custom_fields, 
                    f"custom_fields_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 
                    "Download Custom Fields JSON"
                ),
                unsafe_allow_html=True
            )

# Main app logic
if page == "View Contacts":
    view_contacts_page()
elif page == "Create Contact":
    create_contact_page()
elif page == "Custom Fields":
    custom_fields_page()
elif page == "Export Options":
    export_options_page()
