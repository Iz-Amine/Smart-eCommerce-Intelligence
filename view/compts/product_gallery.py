import streamlit as st
from ..utils import load_data, get_related_products

def show_product_details(product_id, products_df, stores_df):
    """Show detailed product information"""
    if products_df.empty:
        st.error("No products found")
        return
    
    try:
        product = products_df[products_df['id'] == product_id].iloc[0]
        store = stores_df[stores_df['id'] == product['store_id']].iloc[0]
    except (IndexError, KeyError):
        st.error("Product not found")
        return
    
    # Back button
    if st.button("← Back to Gallery"):
        st.session_state['selected_product'] = None
        st.rerun()
    
    st.title("Product Details")
    
    # Product header
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if product['image_url']:
            st.image(product['image_url'], width=300)
        else:
            st.write("No image available")
    
    with col2:
        st.subheader(product['title'])
        
        # Price
        if product['max_price'] and product['max_price'] > product['price']:
            st.write(f"**Price:** ${product['price']:.2f} - ${product['max_price']:.2f}")
        else:
            st.write(f"**Price:** ${product['price']:.2f}")
        
        # Availability
        if product['available']:
            st.success("✅ In Stock")
        else:
            st.error("❌ Out of Stock")
        
        # Basic info
        st.write(f"**Vendor:** {product['vendor']}")
        st.write(f"**Type:** {product['product_type']}")
        
        if product['total_inventory']:
            st.write(f"**Inventory:** {product['total_inventory']}")
        
        if product['variant_count'] > 1:
            st.write(f"**Variants:** {product['variant_count']}")
    
    # Description
    if product['description']:
        st.subheader("Description")
        st.write(product['description'])
    
    # Store information
    st.subheader("Store Information")
    st.write(f"**Store:** {store['name']}")
    st.write(f"**URL:** {store['url']}")
    st.write(f"**Domain:** {store['domain']}")
    st.write(f"**Last Updated:** {store['updated_at']}")
    
    # Related Products
    st.subheader("Related Products")
    related_products = get_related_products(product, products_df)
    
    if not related_products.empty:
        cols = st.columns(min(4, len(related_products)))
        for i, (_, related_product) in enumerate(related_products.iterrows()):
            if i < len(cols):
                with cols[i]:
                    if related_product['image_url']:
                        st.image(related_product['image_url'], width=150)
                    st.write(f"**{related_product['title'][:30]}...**")
                    st.write(f"${related_product['price']:.2f}")
                    
                    if st.button("View", key=f"related_{related_product['id']}"):
                        st.session_state['selected_product'] = related_product['id']
                        st.rerun()
    else:
        st.write("No related products found")

def show_product_gallery():
    st.title("Product Gallery")
    
    # Load data
    _, products_df, stores_df = load_data()
    
    if products_df.empty:
        st.info("No products found. Add products using the Scrape Data page.")
        return
    
    # Filters in sidebar
    st.sidebar.header("Filters")
    
    # Store filter
    if not stores_df.empty:
        store_options = ["All Stores"] + stores_df['name'].tolist()
        selected_store = st.sidebar.selectbox("Select Store", store_options)
    else:
        selected_store = "All Stores"
    
    # Price range filter
    if not products_df.empty:
        min_price = float(products_df['price'].min())
        max_price = float(products_df['price'].max())
        if min_price < max_price:
            price_range = st.sidebar.slider(
                "Price Range",
                min_value=min_price,
                max_value=max_price,
                value=(min_price, max_price)
            )
        else:
            price_range = (min_price, min_price)
    else:
        price_range = (0, 100)
    
    # Availability filter
    availability = st.sidebar.multiselect(
        "Availability",
        ["Available", "Out of Stock"],
        default=["Available", "Out of Stock"]
    )
    
    # Vendor filter
    if not products_df.empty:
        vendors = ["All Vendors"] + sorted(products_df['vendor'].dropna().unique().tolist())
        selected_vendor = st.sidebar.selectbox("Vendor", vendors)
    else:
        selected_vendor = "All Vendors"
    
    # Product type filter
    if not products_df.empty:
        product_types = ["All Types"] + sorted(products_df['product_type'].dropna().unique().tolist())
        selected_type = st.sidebar.selectbox("Product Type", product_types)
    else:
        selected_type = "All Types"
    
    # Apply filters
    filtered_products = products_df.copy()
    
    if selected_store != "All Stores" and not stores_df.empty:
        store_id = stores_df[stores_df['name'] == selected_store]['id'].iloc[0]
        filtered_products = filtered_products[filtered_products['store_id'] == store_id]
    
    if not filtered_products.empty:
        filtered_products = filtered_products[
            (filtered_products['price'] >= price_range[0]) &
            (filtered_products['price'] <= price_range[1])
        ]
        
        if "Available" not in availability:
            filtered_products = filtered_products[~filtered_products['available']]
        if "Out of Stock" not in availability:
            filtered_products = filtered_products[filtered_products['available']]
        
        if selected_vendor != "All Vendors":
            filtered_products = filtered_products[filtered_products['vendor'] == selected_vendor]
        
        if selected_type != "All Types":
            filtered_products = filtered_products[filtered_products['product_type'] == selected_type]
    
    # Display results
    st.write(f"Showing {len(filtered_products)} products")
    
    if filtered_products.empty:
        st.info("No products match your current filters.")
        return
    
    # Display products in grid
    cols_per_row = 3
    for i in range(0, len(filtered_products), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j < len(filtered_products):
                product = filtered_products.iloc[i + j]
                
                with col:
                    # Product image
                    if product['image_url']:
                        st.image(product['image_url'], width=200)
                    else:
                        st.write("No image")
                    
                    # Product info
                    st.write(f"**{product['title'][:50]}**")
                    st.write(f"Price: ${product['price']:.2f}")
                    
                    # Availability
                    if product['available']:
                        st.success("In Stock")
                    else:
                        st.error("Out of Stock")
                    
                    # Additional info
                    if product['vendor']:
                        st.write(f"Vendor: {product['vendor']}")
                    
                    if product['product_type']:
                        st.write(f"Type: {product['product_type']}")
                    
                    # View Details button
                    if st.button("View Details", key=f"view_{product['id']}"):
                        st.session_state['selected_product'] = product['id']
                        st.rerun()
                    
                    st.divider() 