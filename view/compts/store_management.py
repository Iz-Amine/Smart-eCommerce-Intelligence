import streamlit as st
from ..utils import load_data, toggle_surveillance

def show_store_management():
    st.title("Store Management")
    
    # Load stores data
    _, _, stores_df = load_data()
    
    if not stores_df.empty:
        st.subheader("Your Stores")
        
        for _, store in stores_df.iterrows():
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.write(f"**{store['name']}**")
                st.write(f"URL: {store['url']}")
                st.write(f"Domain: {store['domain']}")
            
            with col2:
                st.write(f"Last Updated: {store['updated_at']}")
                if store['active_surveillance']:
                    st.success("Surveillance: Active")
                else:
                    st.warning("Surveillance: Inactive")
            
            with col3:
                button_text = "Deactivate" if store['active_surveillance'] else "Activate"
                if st.button(button_text, key=f"toggle_{store['id']}"):
                    new_status = not store['active_surveillance']
                    if toggle_surveillance(store['id'], new_status):
                        status_text = "activated" if new_status else "deactivated"
                        st.success(f"Surveillance {status_text}")
                        st.rerun()
                    else:
                        st.error("Failed to update surveillance")
            
            st.divider()
    else:
        st.info("No stores found. Add a store using the Scrape Data page.") 