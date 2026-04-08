def get_month_options(df):
    return sorted(df['Month'].dropna().unique(), reverse=True) if 'Month' in df.columns else []


def get_year_options(df):
    years = set()

    if 'Month' in df.columns:
        for m in df['Month']:
            if '-' in m:
                y = m.split('-')[1]
                years.add('20' + y if len(y) == 2 else y)

    return sorted(years, reverse=True)