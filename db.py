import pymssql
import os

env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

DB_SERVER   = os.getenv("DB_SERVER")
DB_PORT     = int(os.getenv("DB_PORT")) if os.getenv("DB_PORT") else None
DB_USER     = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME     = os.getenv("DB_NAME")

def get_connection():
    return pymssql.connect(
        server=DB_SERVER, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )

# Stored procedure constants
SP_GET_USER_BY_EMAIL  = "EXEC dbo.WN_Users_GetByEmail %s"
SP_UPDATE_USER        = "EXEC dbo.WN_Users_Update %s, %s, %s, %s"
SP_INSERT_USER        = "EXEC dbo.WN_Users_Insert %s, %s, %s, %s, %s"
SP_BOOK_TOUR          = "EXEC dbo.WN_BookTour_Insert %s, %s, %s, %s, %s"
SP_GET_ALL_SPACES     = "EXEC dbo.WN_Spaces_GetList"
SP_GET_GALLERY_IMAGES = "EXEC dbo.WN_GalleryImages_GetList"
SP_GET_PRICING_PLANS  = "EXEC dbo.WN_PricingPlans_GetList"
SP_GET_MY_BOOKINGS    = "EXEC dbo.WN_Bookings_GetListByUserId %s"
SP_CREATE_BOOKING     = "EXEC dbo.WN_Bookings_Insert %s, %s, %s, %s, %s, %s"
SP_CREATE_PAYMENT     = "EXEC dbo.WN_Payments_Insert %s, %s, %s, %s, %s"
SP_CANCEL_BOOKING     = "EXEC dbo.WN_Bookings_Cancel %s, %s"
SP_GET_MY_PAYMENTS    = "EXEC dbo.WN_Payments_GetMyList %s"
SP_GET_ALL_LOCATIONS  = "EXEC dbo.WN_Locations_GetList"
SP_GET_ALL_USERS      = "EXEC dbo.WN_Users_GetList"
SP_GET_ALL_BOOKINGS   = "EXEC dbo.WN_Bookings_GetList"
SP_GET_ALL_PAYMENTS   = "EXEC dbo.WN_Payments_GetList"
SP_GET_ALL_SPACE_TYPES = "EXEC dbo.WN_SpaceTypes_GetList"
SP_GET_ALL_CONTACTS   = "EXEC dbo.WN_Contacts_GetList"
SP_GET_ALL_MEMBERSHIPS = "EXEC dbo.WN_Memberships_GetList"
SP_UPDATE_PAYMENT_STATUS = "EXEC dbo.WN_Payments_UpdateStatusByRef %s, %s"


def _iso(val):
    return val.isoformat() if val and hasattr(val, "isoformat") else val


def sync_user(email: str, first_name: str, last_name: str, phone: str = None) -> int:
    if not email:
        return 1
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(SP_GET_USER_BY_EMAIL, (email,))
        row = cursor.fetchone()
        if row:
            user_id = row[0]
            cursor.execute(SP_UPDATE_USER, (first_name, last_name, phone, user_id))
            conn.commit()
            return user_id
        else:
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
    if not email:
        return None
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(SP_GET_USER_BY_EMAIL, (email,))
        row = cursor.fetchone()
        if row:
            return row[0]
        default_name = email.split("@")[0]
        return sync_user(email, default_name, "")
    except Exception:
        return None
    finally:
        conn.close()


def book_tour(name: str, email: str, message: str, phone_number: str, user_id: int = None):
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
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT s.Id, s.Name, s.Code, s.Description, s.Floor,
                   s.PricePerDay, s.PricePerHour, s.Amenities, s.ImageUrl, s.Status,
                   l.Name AS LocationName, l.Id AS LocationId,
                   st.Description AS SpaceTypeName, st.Id AS SpaceTypeId,
                   st.Capacity
            FROM dbo.WN_Spaces s
            LEFT JOIN dbo.WN_Locations l ON s.LocationId = l.IdGUID
            LEFT JOIN dbo.WN_SpaceTypes st ON s.SpaceTypeId = st.IdGUID
            WHERE s.Status != 0
        """)
        rows = cursor.fetchall()
        result = []
        for row in rows:
            price_val = row.get("PricePerDay") or row.get("pricePerDay")
            result.append({
                "id":           row.get("Id") or row.get("id"),
                "name":         row.get("Name") or row.get("name"),
                "code":         row.get("Code") or row.get("code"),
                "locationId":   row.get("LocationId") or row.get("locationId"),
                "spaceTypeId":  row.get("SpaceTypeId") or row.get("spaceTypeId"),
                "locationName": row.get("LocationName") or row.get("locationName"),
                "spaceTypeName":row.get("SpaceTypeName") or row.get("spaceTypeName"),
                "capacity":     row.get("Capacity") or row.get("capacity"),
                "pricePerDay":  float(price_val) if price_val is not None else 0.0,
                "pricePerHour": float(row.get("PricePerHour") or row.get("pricePerHour") or 0),
                "amenities":    row.get("Amenities") or row.get("amenities"),
                "imageUrl":     row.get("ImageUrl") or row.get("imageUrl"),
                "status":       row.get("Status") or row.get("status"),
                "spaceStatus":  "Available" if (row.get("Status") or row.get("status")) == 1 else "Inactive",
            })
        return result
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_gallery_images():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_GALLERY_IMAGES)
        return cursor.fetchall()
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_pricing_plans():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_PRICING_PLANS)
        rows = cursor.fetchall()
        plans_dict = {}
        for row in rows:
            plan_id = row.get("Id") or row.get("id") or row.get("plan_id")
            if not plan_id:
                continue
            if plan_id not in plans_dict:
                price_val = row.get("Price") or row.get("price")
                plans_dict[plan_id] = {
                    "id":          plan_id,
                    "name":        row.get("Name") or row.get("name"),
                    "price":       float(price_val) if price_val is not None else 0.0,
                    "description": row.get("Description") or row.get("description") or "",
                    "features":    [],
                }
            feature_name = row.get("FeatureName") or row.get("featureName")
            if feature_name:
                plans_dict[plan_id]["features"].append({"featureName": feature_name})
        return list(plans_dict.values())
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_my_bookings(user_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_MY_BOOKINGS, (user_id,))
        rows = cursor.fetchall()
        for row in rows:
            if row.get("totalAmount") is not None:
                row["totalAmount"] = float(row["totalAmount"])
            row["startDateTime"] = _iso(row.get("startDateTime"))
            row["endDateTime"]   = _iso(row.get("endDateTime"))
            row["createdAt"]     = _iso(row.get("createdAt"))
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()


def create_booking(user_id, space_id, start_date, end_date, notes, amount, payment_method, reference_number):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(SP_CREATE_BOOKING, (user_id, space_id, start_date, end_date, amount, notes))
        row = cursor.fetchone()
        booking_id = row[0] if row else None
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
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_MY_PAYMENTS, (user_id,))
        rows = cursor.fetchall()
        for row in rows:
            if row.get("amount") is not None:
                row["amount"] = float(row["amount"])
            row["paidAt"] = _iso(row.get("paidAt"))
            workspace  = row.get("workspaceName") or "Workspace"
            start_str  = row["start_date"].strftime("%Y-%m-%d") if row.get("start_date") else ""
            end_str    = row["end_date"].strftime("%Y-%m-%d")   if row.get("end_date")   else ""
            row["bookingSummary"] = f"{workspace} ({start_str} to {end_str})"
            row.pop("start_date", None)
            row.pop("end_date",   None)
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_all_locations():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_ALL_LOCATIONS)
        rows = cursor.fetchall()
        for row in rows:
            status = row.get("status") or row.get("Status") or row.get("IsActive") or row.get("isActive")
            row["isActive"] = bool(status) if status is not None else True
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_booking_by_id(user_id: int, booking_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute("SELECT IdGUID FROM dbo.WN_Users WHERE Id = %d", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        user_guid = row["IdGUID"]
        query = """
            SELECT
                b.Id AS id,
                st.Description AS spaceName,
                b.StartDateTime AS startDateTime,
                b.EndDateTime AS endDateTime,
                b.TotalAmount AS totalAmount,
                CASE
                    WHEN b.BookingStatus = 2 THEN 'Cancelled'
                    WHEN b.BookingStatus = 3 THEN 'Rejected'
                    ELSE 'Confirmed'
                END AS bookingStatus
            FROM dbo.WN_Bookings b
            LEFT JOIN dbo.WN_SpaceTypes st ON b.SpaceGuid = st.IdGUID
            WHERE b.Id = %d AND b.UserGuid = %s AND b.Status = 1
        """
        cursor.execute(query, (booking_id, user_guid))
        res = cursor.fetchone()
        if res:
            if res.get("totalAmount") is not None:
                res["totalAmount"] = float(res["totalAmount"])
            res["startDateTime"] = _iso(res.get("startDateTime"))
            res["endDateTime"]   = _iso(res.get("endDateTime"))
        return res
    except Exception as e:
        raise e
    finally:
        conn.close()


def create_payment(user_id, booking_id, amount, payment_method, transaction_ref):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(SP_CREATE_PAYMENT, (user_id, booking_id, amount, payment_method, transaction_ref))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ── Admin list functions ──────────────────────────────────────────────────────

def get_all_users():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_ALL_USERS)
        rows = cursor.fetchall()
        for row in rows:
            row["createdAt"] = _iso(row.get("createdAt") or row.get("CreatedAt"))
            if row.get("isActive") is None and row.get("IsActive") is None:
                row["isActive"] = True
            elif "IsActive" in row:
                row["isActive"] = bool(row["IsActive"])
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_all_bookings():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_ALL_BOOKINGS)
        rows = cursor.fetchall()
        for row in rows:
            amount = row.get("totalAmount") or row.get("TotalAmount") or row.get("Total_Amount") or 0
            row["totalAmount"] = float(amount) if amount is not None else 0.0
            row["startDateTime"] = _iso(row.get("startDateTime") or row.get("StartDateTime"))
            row["endDateTime"]   = _iso(row.get("endDateTime")   or row.get("EndDateTime"))
            row["createdAt"]     = _iso(row.get("createdAt")     or row.get("CreatedAt"))
            row["userEmail"]     = row.get("userEmail")     or row.get("UserEmail")     or row.get("Email") or ""
            row["spaceName"]     = row.get("spaceName")     or row.get("SpaceName")     or row.get("Name") or ""
            row["bookingStatus"] = row.get("bookingStatus") or row.get("BookingStatus") or ""
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_all_payments():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_ALL_PAYMENTS)
        rows = cursor.fetchall()
        for row in rows:
            if row.get("amount") is not None:
                row["amount"] = float(row["amount"])
            row["paidAt"] = _iso(row.get("paidAt"))
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_all_space_types():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_ALL_SPACE_TYPES)
        rows = cursor.fetchall()
        return [{
            "id":           row.get("Id") or row.get("id"),
            "name":         row.get("Description") or row.get("description") or row.get("Name") or row.get("name"),
            "capacity":     row.get("Capacity") or row.get("capacity"),
            "hourlyAllowed":row.get("HourlyAllowed") or row.get("hourlyAllowed"),
            "isActive":     (row.get("Status") or row.get("status")) == 1,
        } for row in rows]
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_all_contacts():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_ALL_CONTACTS)
        rows = cursor.fetchall()
        for row in rows:
            row["createdAt"] = _iso(row.get("createdAt"))
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_all_memberships():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT m.Id AS id, u.Email AS userEmail,
                   pp.Name AS planName, pp.Price AS planPrice, pp.BillingCycle AS planCycle,
                   m.StartDate AS startDate, m.EndDate AS endDate, m.Status AS status
            FROM dbo.WN_Memberships m
            LEFT JOIN dbo.WN_Users u ON m.UserGuid = u.IdGUID
            LEFT JOIN dbo.WN_PricingPlans pp ON m.PlanId = pp.Id
            WHERE m.Status != 0
        """)
        rows = cursor.fetchall()
        for row in rows:
            row["startDate"] = _iso(row.get("startDate"))
            row["endDate"]   = _iso(row.get("endDate"))
            row["planPrice"] = float(row["planPrice"]) if row.get("planPrice") else 0.0
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()

def insert_space(name, location_id, space_type_id, code, description, floor, price_per_day, price_per_hour, image_url, amenities):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            EXEC dbo.WN_Spaces_Insert %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        """, (name, location_id, space_type_id, code, description, floor, price_per_day, price_per_hour, image_url, amenities))
        row = cursor.fetchone()
        new_id = row[0] if row else None
        conn.commit()
        return new_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_space(space_id, name, location_id, space_type_id, code, description, floor, price_per_day, price_per_hour, image_url, amenities):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("EXEC dbo.WN_Spaces_Update %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s",
            (space_id, name, location_id, space_type_id, code, description, floor, price_per_day, price_per_hour, image_url, amenities))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_space(space_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_Spaces SET Status = 0 WHERE Id = %d", (space_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def update_payment_status(transaction_ref: str, status: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(SP_UPDATE_PAYMENT_STATUS, (transaction_ref, status))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
