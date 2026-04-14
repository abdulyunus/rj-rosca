from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_pdf(month, metrics, df_disbursed, df_closed, df_to_close, df_team_upcoming_collection=None, df_overall_collection=None):
    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    elements = []

    elements.append(Paragraph("RJ-ROSCA Financial Report", styles["Title"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Month: {month}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("Key Metrics", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    kpi_data = [
        ["Metric", "Value"],
        ["Total Collection", f"₹{metrics['total_collection']:,.2f}"],
        ["Total EMI", f"₹{metrics['total_emi']:,.2f}"],
        ["Loans Disbursed", f"₹{metrics['total_loans']:,.2f}"],
        ["Loans Cleared", metrics["loan_cleared"]],
        ["Balance", f"₹{metrics['balance_available']:,.2f}"],
    ]

    kpi_table = Table(kpi_data)
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.blue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )

    elements.append(kpi_table)
    elements.append(Spacer(1, 20))

    def df_to_table(df, title):
        if df is None or getattr(df, "empty", True):
            return

        elements.append(Paragraph(title, styles["Heading3"]))
        elements.append(Spacer(1, 8))

        data = [df.columns.tolist()] + df.values.tolist()
        table = Table(data)

        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]
            )
        )

        elements.append(table)
        elements.append(Spacer(1, 20))

    df_to_table(df_disbursed, "Loans Disbursed")
    df_to_table(df_closed, "Loans Closed")
    df_to_table(df_to_close, "Loans To Close")

    if df_team_upcoming_collection is not None and not df_team_upcoming_collection.empty:
        pdf_team_collection = df_team_upcoming_collection.copy()
        for column_name in ["Monthly Share", "Monthly EMI", "Upcoming Payment"]:
            if column_name in pdf_team_collection.columns:
                pdf_team_collection[column_name] = pdf_team_collection[column_name].map(lambda value: f"₹{float(value):,.2f}")
        df_to_table(pdf_team_collection, "Upcoming Team Collection")

    if df_overall_collection is not None and not df_overall_collection.empty:
        pdf_overall_collection = df_overall_collection.copy()
        for column_name in ["Monthly Share", "Monthly EMI", "Total"]:
            if column_name in pdf_overall_collection.columns:
                pdf_overall_collection[column_name] = pdf_overall_collection[column_name].map(lambda value: f"₹{float(value):,.2f}" if isinstance(value, str) and value.startswith("₹") else f"₹{float(value):,.2f}")
        df_to_table(pdf_overall_collection, "Overall Collection Summary")

    doc.build(elements)

    buffer.seek(0)
    return buffer
