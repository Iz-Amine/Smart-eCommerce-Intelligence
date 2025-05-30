import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from ..utils import load_data

def show_dashboard():
    st.title("Shopify Analytics Dashboard")
    
    # Load data
    logs_df, products_df, stores_df = load_data()
    
    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Products", len(products_df))
    
    with col2:
        st.metric("Total Stores", len(stores_df))
    
    with col3:
        if not stores_df.empty:
            active_surveillance = stores_df["active_surveillance"].sum()
        else:
            active_surveillance = 0
        st.metric("Active Surveillance", active_surveillance)
    
    with col4:
        if not products_df.empty:
            avg_price = products_df["price"].mean()
        else:
            avg_price = 0
        st.metric("Average Price", f"${avg_price:.2f}")
    
    # Add new metrics
    col5, col6 = st.columns(2)
    with col5:
        if not products_df.empty:
            total_inventory = products_df["total_inventory"].sum()
            st.metric("Total Inventory", total_inventory)
    
    with col6:
        if not products_df.empty:
            out_of_stock = len(products_df[~products_df["available"]])
            st.metric("Out of Stock Items", out_of_stock)
    
    # Enhanced Charts
    if not products_df.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Price Distribution")
            fig = px.histogram(
                products_df, 
                x="price", 
                nbins=20, 
                title="Product Price Distribution",
                color_discrete_sequence=['#1f77b4']
            )
            fig.update_layout(
                xaxis_title="Price",
                yaxis_title="Number of Products",
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Product Availability")
            availability_counts = products_df['available'].value_counts()
            fig = px.pie(
                values=availability_counts.values, 
                names=availability_counts.index, 
                title="Product Availability",
                color_discrete_sequence=['#2ecc71', '#e74c3c']
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Add new charts
        col3, col4 = st.columns(2)
        with col3:
            st.subheader("Products by Vendor")
            vendor_counts = products_df['vendor'].value_counts().head(10)
            fig = px.bar(
                x=vendor_counts.index,
                y=vendor_counts.values,
                title="Top 10 Vendors",
                labels={'x': 'Vendor', 'y': 'Number of Products'}
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col4:
            st.subheader("Products by Type")
            type_counts = products_df['product_type'].value_counts().head(10)
            fig = px.bar(
                x=type_counts.index,
                y=type_counts.values,
                title="Top 10 Product Types",
                labels={'x': 'Product Type', 'y': 'Number of Products'}
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Recent activity with more details
    if not stores_df.empty:
        st.subheader("Recent Activity")
        recent_stores = stores_df.sort_values("updated_at", ascending=False).head(5)
        
        for _, store in recent_stores.iterrows():
            with st.expander(f"{store['name']} - Last updated: {store['updated_at']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Status:** {'🟢 Active' if store['active_surveillance'] else '⭕ Inactive'}")
                    st.write(f"**Domain:** {store['domain']}")
                with col2:
                    st.write(f"**URL:** {store['url']}")
                    st.write(f"**Created:** {store['created_at']}") 