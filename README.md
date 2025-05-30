# Product Data Analysis with LLM Enrichment

This project provides tools for analyzing e-commerce product data with the help of Large Language Models (LLM), specifically using Google's Gemini API for generating strategic insights.

## Features

- Product data enrichment using Google's Gemini LLM
- Strategic analysis of product positioning
- Market opportunity identification
- Data-driven business recommendations
- Automated insights generation

## Prerequisites

- Python 3.8 or higher
- Google Gemini API key
- Required Python packages (see Installation)
- Docker (optional, for containerized deployment)

## Installation

### Local Installation

1. Clone the repository:
```bash
git clone [your-repository-url]
cd [repository-name]
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory and add your Gemini API key:
```
GEMINI_API_KEY=your_api_key_here
```

### Docker Installation

1. Build the Docker image:
```bash
docker build -t llm-enricher .
```

2. Run the container:
```bash
docker run -d --env-file .env llm-enricher
```

## Usage

The main component is the `SimpleLLMEnricher` class which provides product data enrichment capabilities:

```python
from Analyse.LLMEnricher import SimpleLLMEnricher

# Initialize the enricher
enricher = SimpleLLMEnricher()

# Example product and store data
product_data = {
    "title": "Product Name",
    "price": "99.99",
    "available": True,
    # ... other product fields
}

store_data = {
    "name": "Store Name",
    "domain": "store.com",
    "url": "https://store.com"
}

# Enrich the product data
enriched_data = enricher.enrich_product_data(product_data, store_data)
```

## Project Structure

```
.
├── Analyse/
│   └── LLMEnricher.py    # Main LLM enrichment module
├── .env                  # Environment variables (not tracked in git)
├── .gitignore           # Git ignore rules
├── .dockerignore        # Docker ignore rules
├── Dockerfile           # Docker configuration
├── README.md            # This file
└── requirements.txt     # Python dependencies
```

## Features

The LLM enricher provides the following analysis:

- Market positioning analysis
- Price competitiveness assessment
- Product optimization recommendations
- Business opportunity identification
- Data utilization strategies

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Google Gemini API for LLM capabilities
- Python community for various libraries and tools 