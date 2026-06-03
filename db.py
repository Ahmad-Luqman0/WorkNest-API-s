import pymssql
import os

# Connection parameters with defaults pointing to the public environment
DB_SERVER = os.getenv("DB_SERVER", "119.159.146.178")
DB_PORT = int(os.getenv("DB_PORT", "1450"))
DB_USER = os.getenv("DB_USER", "workernet")
DB_PASSWORD = os.getenv("DB_PASSWORD", "workernet123")
DB_NAME = os.getenv("DB_NAME", "SAC400")

def get_connection():
    """Establishes and returns a connection to the SQL Server database."""
    return pymssql.connect(
        server=DB_SERVER,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

def book_tour(name: str, email: str, message: str, phone_number: str):
    """
    Inserts a tour booking record directly into the database using a parameterized SQL query.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        query = """
            INSERT INTO dbo.WN_BookTour (Name, Email, Message, CreatedAt, PhoneNumber)
            VALUES (%s, %s, %s, GETDATE(), %s)
        """
        cursor.execute(query, (name, email, message, phone_number))
        conn.commit()
        
        cursor.execute("SELECT @@IDENTITY")
        row = cursor.fetchone()
        new_id = row[0] if row else None
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
        query = """
            SELECT 
                s.Id AS id,
                s.Name AS name,
                l.Name AS locationName,
                st.Description AS spaceTypeName,
                st.Capacity AS capacity,
                s.PricePerDay AS pricePerDay,
                s.Amenities AS amenities,
                s.ImageUrl AS imageUrl,
                CASE 
                    WHEN s.Status = 1 THEN 'available'
                    ELSE 'inactive'
                END AS status
            FROM dbo.WN_Spaces s
            LEFT JOIN dbo.WN_Locations l ON s.LocationId = l.Id
            LEFT JOIN dbo.WN_SpaceTypes st ON s.SpaceTypeId = st.Id
        """
        cursor.execute(query)
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
        query = """
            SELECT 
                g.Id AS id,
                g.Title AS title,
                g.Description AS description,
                g.ImageUrl AS imageUrl,
                l.Name AS locationName
            FROM dbo.WN_GalleryImages g
            LEFT JOIN dbo.WN_Locations l ON g.LocationId = l.Id
            WHERE g.Status = 1
        """
        cursor.execute(query)
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
        query = """
            SELECT 
                p.Id AS plan_id,
                p.Name AS name,
                p.Price AS price,
                p.Description AS description,
                f.FeatureName AS featureName
            FROM dbo.WN_PricingPlans p
            LEFT JOIN dbo.WN_PlanFeatures f ON p.Id = f.PlanId
            WHERE p.IsActive = 1
        """
        cursor.execute(query)
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
        query = """
            SELECT 
                b.Id AS id,
                s.Name AS spaceName,
                b.StartDateTime AS startDateTime,
                b.EndDateTime AS endDateTime,
                b.TotalAmount AS totalAmount,
                CASE 
                    WHEN b.BookingStatus = 2 THEN 'Cancelled'
                    WHEN b.BookingStatus = 3 THEN 'Rejected'
                    ELSE 'Confirmed'
                END AS bookingStatus
            FROM dbo.WN_Bookings b
            LEFT JOIN dbo.WN_Spaces s ON b.SpaceId = s.Id
            WHERE b.UserId = %s AND b.Status = 1
            ORDER BY b.BookingDate DESC
        """
        cursor.execute(query, (user_id,))
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
        booking_query = """
            INSERT INTO dbo.WN_Bookings 
                (IdGUID, BookingDate, UserId, SpaceId, StartDateTime, EndDateTime, TotalAmount, BookingStatus, Status, Notes, CreatedOn)
            VALUES 
                (NEWID(), GETDATE(), %s, %s, %s, %s, %s, 1, 1, %s, GETDATE())
        """
        cursor.execute(booking_query, (user_id, space_id, start_date, end_date, amount, notes))
        
        # Fetch newly created Booking ID
        cursor.execute("SELECT @@IDENTITY")
        booking_id = cursor.fetchone()[0]
        
        # 2. Insert into WN_Payments if payment exists
        if payment_method:
            payment_query = """
                INSERT INTO dbo.WN_Payments 
                    (UserId, BookingId, Amount, Currency, PaymentMethod, PaymentStatus, TransactionRef, PaidAt, CreatedAt)
                VALUES 
                    (%s, %s, %s, 'PKR', %s, 'Paid', %s, GETDATE(), GETDATE())
            """
            cursor.execute(payment_query, (user_id, booking_id, amount, payment_method, reference_number))
            
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
        query = """
            UPDATE dbo.WN_Bookings 
            SET BookingStatus = 2, UpdatedOn = GETDATE()
            WHERE Id = %s AND UserId = %s
        """
        cursor.execute(query, (booking_id, user_id))
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
        query = """
            SELECT 
                p.Id AS id,
                p.Amount AS amount,
                p.PaymentMethod AS paymentMethod,
                p.PaymentStatus AS paymentStatus,
                p.PaidAt AS paidAt,
                s.Name AS workspaceName,
                p.TransactionRef AS referenceNumber,
                p.TransactionRef AS bankDepositId,
                b.StartDateTime AS start_date,
                b.EndDateTime AS end_date
            FROM dbo.WN_Payments p
            LEFT JOIN dbo.WN_Bookings b ON p.BookingId = b.Id
            LEFT JOIN dbo.WN_Spaces s ON b.SpaceId = s.Id
            WHERE p.UserId = %s
            ORDER BY p.PaidAt DESC
        """
        cursor.execute(query, (user_id,))
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
