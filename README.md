# GRIDLINE: Software-Driven Design and Simulation of a Smart Energy Metering System
GRIDLINE is a software-based smart energy monitoring and analytics platform designed around Indian household electricity consumption scenarios.
It provides a dashboard for generating simulated electricity readings, importing CSV data, monitoring consumption, estimating electricity costs, and identifying unusual power usage patterns.
> **Important:** GRIDLINE currently operates as a software simulation and data-analysis platform. It does not directly measure electricity from a physical smart meter. Simulated readings are labelled separately from imported or device readings.
## Features
- Household electricity consumption simulation (1BHK, 2BHK, 3BHK and 3BHK+).- CSV-based electricity reading import.- Voltage, current and active power monitoring.- Energy consumption calculations in kWh.- Electricity cost estimation in Indian Rupees (₹).- Configurable electricity tariff.- Hourly consumption profiling.- Statistical anomaly detection using Modified Z-Score and Median Absolute Deviation.- SQLite-based data storage.- CSV data export.- REST API for data ingestion.
## Technology Stack
| Component | Technology ||---|---|| Backend | Python, FastAPI || Frontend | HTML, CSS, JavaScript || Database | SQLite || API | REST || Data processing | Python || Server | Uvicorn |
## Project Structure
```textsmart-energy-meter-Gridline/├── app.py├── requirements.txt├── GRIDLINE.spec├── smartgrid.db├── static/├── templates/└── README.md```
## Installation
### 1. Clone the repository
```bashgit clone https://github.com/namanpawar2806-commits/smart-energy-meter-Gridline.gitcd smart-energy-meter-Gridline```
### 2. Create a virtual environment
```bashpython -m venv .venv```
### 3. Activate it on Windows
```powershell.venv\Scripts\activate```
### 4. Install dependencies
```bashpython -m pip install -r requirements.txt```
### 5. Start the application
```bashpython -m uvicorn app:app --host 127.0.0.1 --port 8001```
Open this address in your browser:
http://127.0.0.1:8001
API documentation:
http://127.0.0.1:8001/docs
## Data Sources
GRIDLINE supports three data sources:
- **Simulation:** Synthetic household electricity readings generated for demonstration and testing.- **Import:** Readings uploaded through CSV files.- **Device:** Readings submitted through the authenticated API ingestion endpoint.
Simulation data must not be interpreted as actual electricity measurements.
## CSV Import Format
Required columns:
```csvdevice_id,timestamp,voltage_v,current_a,active_power_w```
Optional columns include:
```textenergy_kwh,power_factor,frequency_hz```
Timestamps should be valid ISO 8601 datetime values.
## API Endpoints
| Method | Endpoint | Purpose ||---|---|---|| GET | `/api/status` | Application status || POST | `/api/simulate` | Generate synthetic readings || POST | `/api/import-csv` | Import CSV readings || GET | `/api/readings` | Retrieve readings || GET | `/api/analytics` | Consumption analytics || POST | `/api/tariff` | Update electricity tariff || GET | `/api/export.csv` | Export readings || POST | `/api/readings` | Authenticated device ingestion |
Device ingestion requires the `SMARTGRID_INGEST_KEY` environment variable to be configured on the server.
## Project Objective
The objective of GRIDLINE is to demonstrate how software-based metering infrastructure can support electricity consumption monitoring, data management, household energy analytics, and anomaly identification.
## Limitations
- No physical electricity meter is currently connected.- Simulation values are representative synthetic data.- Actual device integration requires compatible hardware and secure data transmission.- Cost estimates depend on the configured tariff and available readings.
## License
Specify the project's license before permitting reuse or redistribution.
