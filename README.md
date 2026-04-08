# RJ-ROSCA Automation Dashboard

A modern, mobile-friendly Streamlit dashboard for managing and visualizing ROSCA (Rotating Savings and Credit Association) data, integrated with Google Sheets.

## Features
- 📅 Year and month selection with automatic current/next month detection
- 📈 Key financial metrics: collection, loans, EMI, share amount, and more
- 💸 Tables for Loans Disbursed, Loans to be Closed (next month), and Loans Closed
- 🎨 Colorful, responsive UI for desktop and mobile
- 🔒 Secure Google Sheets integration using service account credentials

## Project Structure
```
ROSCA_Automation/
├── app.py                # Main Streamlit dashboard app
├── config.py             # Configuration (sheet names, etc.)
├── gsheet_client.py      # Google Sheets authentication
├── data_loader.py        # Data loading functions
├── data_processor.py     # Data cleaning and filtering
├── metrics.py            # Metric calculation functions
├── utils.py              # Utility functions (month/year extraction, etc.)
├── requirements.txt      # Python dependencies
├── credentials.json      # Google service account credentials (not committed)
```

## Setup Instructions

1. **Clone the repository**
   ```sh
   git clone <repo-url>
   cd ROSCA_Automation
   ```

2. **Install dependencies**
   ```sh
   pip install -r requirements.txt
   ```

3. **Google Sheets API Setup**
   - Create a Google Cloud project and enable the Google Sheets API.
   - Create a service account and download the `credentials.json` file.
   - Share your Google Sheet with the service account email.

4. **Configure the app**
   - Set your sheet name and other config in `config.py`.
   - Place `credentials.json` in the project root.

5. **Run the dashboard**
   ```sh
   streamlit run app.py
   ```
   - Open the provided URL in your browser (e.g., http://localhost:8501)

## Usage
- Select the desired year and month from the dropdowns.
- View key metrics and loan tables for the selected period.
- The dashboard is responsive and works on both desktop and mobile devices.

## Security
- **Never commit your `credentials.json` to public repositories.**
- Use environment variables or secret management for production deployments.

## License
MIT License

---
*Powered by ROSCA Automation | © 2026*
