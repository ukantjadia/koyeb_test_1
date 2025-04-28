# TODO:
# include all the fields mention by Patrik
# creating web for field mapping
# handling error if new user don't have each and every column data
#

import pandas as pd
import io
import re
from datetime import datetime
from backend.models.lead_model import db, Lead

# Helper: Clean and Normalize Email
def clean_email(email):
    if pd.isna(email):
        return None
    return str(email).strip().lower()

# Helper: Clean and Normalize Phone
def clean_phone(phone):
    if pd.isna(phone):
        return None
    return re.sub(r'\D', '', str(phone))  # keep only numbers

# Helper: Validate Email Format
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
def is_valid_email(email):
    if not email or pd.isna(email):
        return False
    return bool(EMAIL_REGEX.match(str(email).strip()))

# Helper: Validate Phone (at least 8 digits, all numeric)
def is_valid_phone(phone):
    if not phone or pd.isna(phone):
        return False
    phone_str = re.sub(r'\D', '', str(phone))
    return phone_str.isdigit() and len(phone_str) >= 8

# Update is_valid_row to use new checks
def is_valid_row(name, email, phone):
    return bool(name and str(name).strip()) and is_valid_email(email) and is_valid_phone(phone)

def process_csv_file(file, name_col, email_col, phone_col):
    """
    Process a CSV file and return statistics about the upload
    Returns: tuple (added, skipped_duplicates, errors)
    """
    try:
        # Read the file content
        content = file.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        
        # Create DataFrame from CSV
        df = pd.read_csv(io.StringIO(content))
        
        # Convert column names to string and strip whitespace
        df.columns = df.columns.str.strip()
        
        # Check if required columns exist
        missing_cols = [col for col in [name_col, email_col, phone_col] if col not in df.columns]
        if missing_cols:
            raise Exception(f"Missing required columns: {', '.join(missing_cols)}")

        # Initialize default values for optional columns
        optional_cols = {
            'Company': 'company',
            'City': 'city',
            'State': 'state',
            'First Name': 'first_name',
            'Last Name': 'last_name'
        }

        # Process required fields
        df['name'] = df[name_col].astype(str).fillna("").str.strip()
        df['email'] = df[email_col].apply(clean_email)
        df['phone'] = df[phone_col].apply(clean_phone)

        # Split 'name' into 'first_name' and 'last_name'
        def split_name(name):
            parts = name.strip().split()
            if len(parts) == 0:
                return "", ""
            elif len(parts) == 1:
                return parts[0], ""
            else:
                return parts[0], " ".join(parts[1:])
        df['first_name'], df['last_name'] = zip(*df['name'].map(split_name))

        # Process optional fields with safe fallback
        for csv_col, db_col in optional_cols.items():
            if csv_col in df.columns:
                df[db_col] = df[csv_col].astype(str).fillna("").str.strip()
            else:
                if db_col not in ['first_name', 'last_name']:
                    df[db_col] = ""

        added = 0
        skipped_duplicates = 0
        errors = 0

        # Process each lead
        for idx, row in df.iterrows():
            name = row['name']
            email = row['email']
            phone = row['phone']
            first_name = row['first_name']
            last_name = row['last_name']

            # Check if required fields are present and valid
            if not is_valid_row(name, email, phone):
                errors += 1
                continue

            # Check for duplicates
            existing_lead = Lead.query.filter(
                (Lead.email == email) | (Lead.phone == phone)
            ).first()

            if existing_lead:
                skipped_duplicates += 1
                continue

            # Create new lead
            try:
                lead = Lead(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    phone=phone,
                    company=row['company'],
                    city=row['city'],
                    state=row['state']
                )
                db.session.add(lead)
                added += 1
            except Exception as e:
                errors += 1
                continue

        return added, skipped_duplicates, errors

    except pd.errors.EmptyDataError:
        raise Exception("The CSV file is empty")
    except pd.errors.ParserError:
        raise Exception("Invalid CSV format")
    except Exception as e:
        raise Exception(f"Error processing CSV: {str(e)}")
