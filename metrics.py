def calculate_metrics(df):
    metrics = {}

    metrics['total_collection'] = df.get('Total Amount', []).sum()
    metrics['total_emi'] = df.get('EMI received', []).sum()
    metrics['total_share'] = df.get('Share Amount for the month', []).sum()
    metrics['total_loans'] = df.get('Loan', []).sum()
    metrics['loan_processed'] = df.get('No of Application processed', []).sum()
    metrics['loan_cleared'] = df.get('No of Loan cleared', []).sum()

    metrics['balance_available'] = metrics['total_collection'] - metrics['total_loans']

    return metrics
