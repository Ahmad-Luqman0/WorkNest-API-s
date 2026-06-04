import pymssql
import os

# Connection parameters with defaults pointing to the public environment
DB_SERVER = os.getenv("DB_SERVER")
DB_PORT = int(os.getenv("DB_PORT")) if os.getenv("DB_PORT") else None
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")  
DB_NAME = os.getenv("DB_NAME")

def get_connection():
    """Establishes and returns a connection to the SQL Server database."""
    return pymssql.connect(
        server=DB_SERVER,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

# --- Stored Procedures (Calling WN_TABLENAME_OPERATION Database Procedures) ---
SP_GET_USER_BY_EMAIL = "EXEC dbo.WN_Users_GetByEmail %s"
SP_UPDATE_USER = "EXEC dbo.WN_Users_Update %s, %s, %s, %s"
SP_INSERT_USER = "EXEC dbo.WN_Users_Insert %s, %s, %s, %s, %s"
SP_BOOK_TOUR = "EXEC dbo.WN_BookTour_Insert %s, %s, %s, %s, %s"
SP_GET_ALL_SPACES = "EXEC dbo.WN_Spaces_GetList"
SP_GET_GALLERY_IMAGES = "EXEC dbo.WN_GalleryImages_GetList"
SP_GET_PRICING_PLANS = "EXEC dbo.WN_PricingPlans_GetList"
SP_GET_MY_BOOKINGS = "EXEC dbo.WN_Bookings_GetListByUserId %s"
SP_CREATE_BOOKING = "EXEC dbo.WN_Bookings_Insert %s, %s, %s, %s, %s, %s"
SP_CREATE_PAYMENT = "EXEC dbo.WN_Payments_Insert %s, %s, %s, %s, %s"
SP_CANCEL_BOOKING = "EXEC dbo.WN_Bookings_Cancel %s, %s"
SP_GET_MY_PAYMENTS = "EXEC dbo.WN_Payments_GetMyList %s"
SP_GET_ALL_LOCATIONS = "EXEC dbo.WN_Locations_GetList"

def sync_user(email: str, first_name: str, last_name: str, phone: str = None) -> int:
    """
    Finds or creates a user by Email in WN_Users and returns their database Id.
    """
    if not email:
        return 1 # Fallback
        
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Check if user exists
        cursor.execute(SP_GET_USER_BY_EMAIL, (email,))
        row = cursor.fetchone()
        if row:
            user_id = row[0]
            # Update user fields
            cursor.execute(SP_UPDATE_USER, (first_name, last_name, phone, user_id))
            conn.commit()
            return user_id
        else:
            # Create user
            cursor.execute(SP_INSERT_USER, (first_name, last_name, email, email, phone))
            row = cursor.fetchone()
            new_id = row[0] if row else None
            conn.commit()
            return new_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_user_id_by_email(email: str):
    """
    Looks up a user's database Id by email.
    If the user does not exist, automatically syncs/creates a stub user.
    """
    if not email:
        return None
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(SP_GET_USER_BY_EMAIL, (email,))
        row = cursor.fetchone()
        if row:
            return row[0]
        # Fallback: auto-create user stub if they don't exist yet
        default_name = email.split('@')[0]
        return sync_user(email, default_name, "")
    except Exception:
        return None
    finally:
        conn.close()


def book_tour(name: str, email: str, message: str, phone_number: str, user_id: int = None):
    """
    Inserts a tour booking record directly into the database using a parameterized SQL query.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(SP_BOOK_TOUR, (name, email, message, phone_number, user_id))
        row = cursor.fetchone()
        new_id = row[0] if row else None
        conn.commit()
        return new_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_all_spaces():
    """
    Fetches all active spaces from WN_Spaces, joining their Location and SpaceType details.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_ALL_SPACES)
        rows = cursor.fetchall()
        
        for row in rows:
            if row.get("pricePerDay") is not None:
                row["pricePerDay"] = float(row["pricePerDay"])
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()

def get_gallery_images():
    """
    Fetches all active gallery images, joining their Location details.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_GALLERY_IMAGES)
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()

def get_pricing_plans():
    """
    Fetches active pricing plans alongside their included features.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_PRICING_PLANS)
        rows = cursor.fetchall()
        
        plans_dict = {}
        for row in rows:
            plan_id = row['plan_id']
            if plan_id not in plans_dict:
                plans_dict[plan_id] = {
                    "id": plan_id,
                    "name": row['name'],
                    "price": float(row['price']) if row['price'] is not None else 0.0,
                    "description": row['description'] or "",
                    "features": []
                }
            if row['featureName']:
                plans_dict[plan_id]["features"].append({"featureName": row['featureName']})
                
        return list(plans_dict.values())
    except Exception as e:
        raise e
    finally:
        conn.close()

def get_my_bookings(user_id: int):
    """
    Fetches the bookings made by the specified user.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_MY_BOOKINGS, (user_id,))
        rows = cursor.fetchall()
        
        for row in rows:
            if row.get("totalAmount") is not None:
                row["totalAmount"] = float(row["totalAmount"])
            # Format datetime objects into strings for JSON response
            if row.get("startDateTime") is not None:
                row["startDateTime"] = row["startDateTime"].isoformat()
            if row.get("endDateTime") is not None:
                row["endDateTime"] = row["endDateTime"].isoformat()
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()

def create_booking(user_id: int, space_id: int, start_date: str, end_date: str, notes: str, amount: float, payment_method: str, reference_number: str):
    """
    Inserts a new booking in WN_Bookings and a payment record in WN_Payments.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Insert into WN_Bookings
        cursor.execute(SP_CREATE_BOOKING, (user_id, space_id, start_date, end_date, amount, notes))
        
        # Fetch newly created Booking ID
        row = cursor.fetchone()
        booking_id = row[0] if row else None
        
        # 2. Insert into WN_Payments if payment exists
        if payment_method and booking_id:
            cursor.execute(SP_CREATE_PAYMENT, (user_id, booking_id, amount, payment_method, reference_number))
            
        conn.commit()
        return booking_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def cancel_booking(user_id: int, booking_id: int):
    """
    Sets booking status to Cancelled (2) in WN_Bookings.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(SP_CANCEL_BOOKING, (booking_id, user_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_my_payments(user_id: int):
    """
    Fetches payment records for a user, building details from associated bookings and spaces.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_MY_PAYMENTS, (user_id,))
        rows = cursor.fetchall()
        
        for row in rows:
            if row.get("amount") is not None:
                row["amount"] = float(row["amount"])
            if row.get("paidAt") is not None:
                row["paidAt"] = row["paidAt"].isoformat()
            
            # Format custom bookingSummary
            workspace = row.get("workspaceName") or "Workspace"
            start_str = row['start_date'].strftime('%Y-%m-%d') if row.get('start_date') else ''
            end_str = row['end_date'].strftime('%Y-%m-%d') if row.get('end_date') else ''
            row['bookingSummary'] = f"{workspace} ({start_str} to {end_str})"
            
            # Clean temporary datetime keys
            if 'start_date' in row:
                del row['start_date']
            if 'end_date' in row:
                del row['end_date']
                
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()

def get_all_locations():
    """
    Fetches all active locations from WN_Locations.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_ALL_LOCATIONS)
        return cursor.fetchall()
    except Exception as e:
        raise e
    finally:
        conn.close()
