# Product Data Synchronization Service

This project implements a service for synchronizing product data from various external sources (e.g., ECC API, [EAN Availability API](https://ecc-online.net)) into a MySQL database with option to export it to Excel. It is designed with a layered architecture, incorporating Domain-Driven Design (DDD) principles and Data Transfer Objects (DTOs) to ensure scalability, maintainability, and extensibility for future integrations with marketplaces like Amazon and eBay.

- [Architecture Overview](#architecture-overview)
- [Getting Started](#getting-started)
- [Testing](#testing)
- [Contributing](#contributing)

## Architecture Overview

The project follows a modular, layered architecture:

1.  **`src/`**: Contains all source code.

    - **`common/`**: Houses shared components used across different parts of the application.
      - `dtos/`: Data Transfer Objects (DTOs) for structured data exchange between layers and modules (e.g., `ArticleDataDTO`, `EANAvailabilityItemDTO`).
      - `exceptions/`: Custom exception classes for consistent error handling.
      - `utils/`: General utility functions (e.g., date formatting).
      - `config/`: Manages application settings, including sensitive information (API keys, database credentials) loaded from environment variables (`.env` file).
    - **`core/`**: (Optional) For very generic, shared domain-level concepts if applicable.
    - **`article_domain/`**: Represents the primary Bounded Context for **Article data management**. This module encapsulates all logic related to detailed product information (e.g., descriptions, images, attributes).
      - `application/`: Contains application services that orchestrate operations, coordinating domain services and infrastructure components. Handles use cases like "sync article details from ECC".
      - `domain/`: The core business logic. Defines `Article` entities, `Attribute` and `Image` value objects, and abstract `IArticleRepository` interfaces.
      - `infrastructure/`: Provides concrete implementations for `IArticleRepository` (e.g., `MySQLArticleRepository` saving to `pds_articles` tables) and `ECCApiClient`.
    - **`product_availability_domain/`**: A dedicated Bounded Context for **Product Availability and Pricing data**. This module handles the synchronization of EAN (GTIN) codes, quantities, and prices, typically associated with a specific retailer and supplier context.
      - `application/`: Application services for use cases like "sync EAN availability data".
      - `domain/`: Defines `EANAvailability` entities, `SupplierInfo` value objects, and abstract `IGtinStockRepository` interfaces.
      - `infrastructure/`: Provides concrete implementations for `IGtinStockRepository` (e.g., `MySQLGtinStockRepository` saving to `pds_gtins_stock` table) and `GlobalStockApiClient` for external API integration.
    - **`marketplace_integration/`**: A separate Bounded Context for future integrations with marketplaces (e.g., Amazon, eBay). It mirrors the layered structure of other domains for similar reasons of modularity and scalability.

2.  **`main.py`**: The entry point of the application, responsible for setting up dependency injection and initiating the main process flows for different domains. It also handles initial database table creation.

For now use only `step1_main.py`.

3.  **`tests/`**: Contains unit and integration tests, mirroring the `src/` directory structure.

4.  **`requirements.txt`**: Lists all project dependencies.

5.  **`.env.example`**: A template file for environment variables. **Sensitive information should be stored in a `.env` file (not committed to Git).**

6.  **`.gitignore`**: Specifies files and directories to be ignored by Git (e.g., `.env`, `__pycache__`).

This architecture promotes a clear separation of concerns, making the system easier to understand, develop, test, and maintain, especially as new features and external integrations are added.

### Database Table Naming Convention

To ensure clear identification and avoid conflicts with other projects, all tables managed by this Product Data Synchronization (PDS) service are prefixed with `pds_`.

- **Article Domain Tables:**
  - `pds_articles`: Stores main article data.
  - `pds_article_attributes`: Stores attributes related to articles.
  - `pds_article_images`: Stores image URLs related to articles.
- **Product Availability Domain Tables:**
  - `pds_gtins_stock`: Stores GTIN codes, quantities, prices, and associated supplier/retailer context (`RETAILER_ID`, `RETAILER_GLN`, `SUPPLIER_ID`, `SUPPLIER_GLN`, `SUPPLIER_NAME`).

This naming convention helps in quickly identifying which tables belong to this project and specific domains within it.

## Getting Started

Follow these steps to set up and run the application.

### 1. Clone the Repository

First, clone the project from GitHub to your local machine:

```bash
git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
cd your-repo-name
```

### 2. Set Up a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# .\venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

### 5. Open the `.env` file and fill in your actual credentials

### 6. Run the Application

```bash
python main.py
```

## Testing

The project uses `pytest` for unit and integration testing.

```bash
export PYTHONPATH=$PYTHONPATH:/Users/alexander/Documents/Marcus/
pytest
```

### Run Tests

Navigate to the root directory of your project (where `src/` and `tests/` are located) and run `pytest`

```bash
cd /path/to/your-repo-name/ # Make sure you are in the project root
pytest
```

This command will discover and run all tests defined in the tests/ directory. The tests use mocking to simulate external API calls and database interactions, ensuring they are fast and isolated.

## Contributing

Contributions are welcome! Please feel free to open issues or submit pull requests.
