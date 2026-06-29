import pymssql
import os
from dotenv import load_dotenv

try:
    from api.roles import map_role
except ImportError:
    from roles import map_role

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

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
SP_GET_USER_BY_EMAIL     = "EXEC dbo.WN_Users_GetByEmail %s"
SP_UPDATE_USER           = "EXEC dbo.WN_Users_Update %s, %s, %s, %s"
SP_INSERT_USER           = "EXEC dbo.WN_Users_Insert %s, %s, %s, %s, %s"
SP_BOOK_TOUR             = "EXEC dbo.WN_BookTour_Insert %s, %s, %s, %s, %s"
SP_GET_ALL_SPACES        = "EXEC dbo.WN_Spaces_GetList"
SP_GET_GALLERY_IMAGES    = "EXEC dbo.WN_GalleryImages_GetList"
SP_GET_PRICING_PLANS     = "EXEC dbo.WN_PricingPlans_GetList"
SP_GET_MY_BOOKINGS       = "EXEC dbo.WN_Bookings_GetListByUserId %s"
SP_CREATE_BOOKING        = "EXEC dbo.WN_Bookings_Insert %s, %s, %s, %s, %s, %s"
SP_CREATE_PAYMENT        = "EXEC dbo.WN_Payments_Insert %s, %s, %s, %s, %s"
SP_CANCEL_BOOKING        = "EXEC dbo.WN_Bookings_Cancel %s, %s"
SP_GET_MY_PAYMENTS       = "EXEC dbo.WN_Payments_GetMyList %s"
SP_GET_ALL_LOCATIONS     = "EXEC dbo.WN_Locations_GetList"
SP_GET_ALL_USERS         = "EXEC dbo.WN_Users_GetList"
SP_GET_ALL_BOOKINGS      = "EXEC dbo.WN_Bookings_GetList"
SP_GET_ALL_PAYMENTS      = "EXEC dbo.WN_Payments_GetList"
SP_GET_ALL_SPACE_TYPES   = "EXEC dbo.WN_SpaceTypes_GetList"
SP_GET_ALL_CONTACTS      = "EXEC dbo.WN_Contacts_GetList"
SP_GET_ALL_MEMBERSHIPS   = "EXEC dbo.WN_Memberships_GetList"
SP_UPDATE_PAYMENT_STATUS = "EXEC dbo.WN_Payments_UpdateStatusByRef %s, %s"
SP_GET_ALL_BRANCHES      = "EXEC dbo.WN_Branches_GetList"
SP_GET_ALL_COMPANIES     = "EXEC dbo.WN_Companies_GetList"
SP_GET_ALL_CITIES        = "EXEC dbo.WN_Cities_GetList"

DEFAULT_COMPANY_ID = 484

# Auto-Assignment Booking System Stored Procedures
SP_GET_AVAILABLE_SPACES = "EXEC dbo.WN_GetAvailableSpaces %s, %s, %s"
SP_CREATE_BOOKING_AUTO_ASSIGN = "EXEC dbo.WN_CreateBookingWithAutoAssignment"  # called inline with OUTPUT params
SP_GET_AVAILABILITY_COUNTS = "EXEC dbo.WN_GetAvailabilityCounts"
SP_GET_AVAILABLE_BY_TYPE = "EXEC dbo.WN_GetAvailableSpacesByType %s, %s, %s"
SP_REASSIGN_BOOKING = "EXEC dbo.WN_ReassignBooking %s, %s, %s"
SP_GET_SPACES_FOR_REASSIGNMENT = "EXEC dbo.WN_GetAvailableSpacesForReassignment %s, %s, %s, %s"
SP_GET_BOOKING_CALENDAR = "EXEC dbo.WN_GetBookingCalendar %s, %s, %s"

# Space configuration SPs
SP_GET_SPACE_CONFIG    = "EXEC dbo.WN_SpaceConfig_GetList"
SP_CHECK_OVERLAP       = "EXEC dbo.WN_Booking_CheckOverlap %s, %s, %s"
SP_GET_AVAILABLE_V2    = "EXEC dbo.WN_Booking_GetAvailableSpaces %s, %s, %s, %s"


def _iso(val):
    return val.isoformat() if val and hasattr(val, "isoformat") else val


def sync_user(email: str, first_name: str, last_name: str, phone: str = None) -> tuple:
    """Returns (numeric_id, guid) tuple. Never returns None for id."""
    if not email:
        return (1, None)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(SP_GET_USER_BY_EMAIL, (email,))
        row = cursor.fetchone()
        if row:
            # SP returns Id, IdGUID
            user_id  = row[0]
            user_guid = str(row[1]) if row[1] else None
            cursor.execute(SP_UPDATE_USER, (first_name, last_name, phone, user_id))
            conn.commit()
            return (user_id, user_guid)
        else:
            cursor.execute(SP_INSERT_USER, (first_name, last_name, email, email, phone))
            row = cursor.fetchone()
            new_id   = row[0] if row else None
            new_guid = str(row[1]) if (row and len(row) > 1 and row[1]) else None
            if new_id:
                cursor.execute(
                    "UPDATE dbo.WN_Users SET RoleId = 14, CompanyId = %d WHERE Id = %d",
                    (DEFAULT_COMPANY_ID, new_id)
                )
            conn.commit()
            return (new_id, new_guid)
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_user_id_by_email(email: str) -> tuple:
    """Returns (numeric_id, guid) tuple."""
    if not email:
        return (None, None)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(SP_GET_USER_BY_EMAIL, (email,))
        row = cursor.fetchone()
        if row:
            return (row[0], str(row[1]) if row[1] else None)
        return (None, None)
    except Exception:
        return (None, None)
    finally:
        conn.close()


def book_tour(name: str, email: str, message: str, phone_number: str, user_id: int = None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(SP_BOOK_TOUR, (name, email, message, phone_number, user_id if user_id else None))
        row = cursor.fetchone()
        new_id = row[0] if row else None
        conn.commit()
        if new_id is None:
            # SP did not return an ID — insert directly as fallback
            cursor.execute("""
                INSERT INTO dbo.WN_BookTour (Name, Email, PhoneNumber, Message, UserId, Status, CreatedOn)
                VALUES (%s, %s, %s, %s, %s, 1, GETDATE());
                SELECT SCOPE_IDENTITY() AS id
            """, (name, email, phone_number, message, user_id))
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
        cursor.execute("SELECT Id, Name FROM dbo.WN_Amenities WITH (NOLOCK) WHERE Status = 1")
        amenity_map = {str(row['Id']): row['Name'] for row in cursor.fetchall()}

        cursor.execute(SP_GET_ALL_SPACES)
        rows = cursor.fetchall()

        result = []
        for row in rows:
            guid = str(row.get("idGuid") or row.get("IdGUID") or "")
            price_val = row.get("pricePerDay") or row.get("PricePerDay")
            status_val = row.get("status") or row.get("Status")
            numeric_id = row.get("id") or row.get("Id")
            raw_amenities = row.get("amenities") or row.get("Amenities") or ""
            amenity_ids = [a.strip() for a in raw_amenities.split(",") if a.strip()]
            amenity_names = ",".join(amenity_map.get(aid, aid) for aid in amenity_ids)
            result.append({
                "id":             numeric_id,
                "idGuid":         guid,
                "name":           row.get("name") or row.get("Name") or "",
                "code":           row.get("code") or row.get("Code") or "",
                "floorId":        row.get("floorId") or row.get("FloorId"),
                "floorName":      row.get("floorName") or row.get("FloorName") or "",
                "description":    row.get("description") or row.get("Description") or "",
                "locationId":     row.get("locationId") or row.get("LocationId"),
                "locationIdGuid": str(row.get("locationIdGuid") or row.get("LocationIdGuid") or ""),
                "spaceTypeIdGuid":str(row.get("spaceTypeIdGuid") or row.get("SpaceTypeIdGuid") or ""),
                "locationName":   row.get("locationName") or row.get("LocationName") or "",
                "spaceTypeName":  row.get("spaceTypeName") or row.get("SpaceTypeName") or "",
                "capacity":       row.get("capacity") or row.get("Capacity"),
                "pricePerDay":    float(price_val) if price_val is not None else 0.0,
                "pricePerHour":   float(row.get("pricePerHour") or row.get("PricePerHour") or 0),
                "amenities":      amenity_names,
                "amenityIds":     ",".join(amenity_ids),
                "imageUrl":       row.get("imageUrl") or row.get("ImageUrl") or "",
                "status":         status_val,
                "spaceStatus":    "Available" if status_val == 1 else "Inactive",
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
        cursor.execute("""
            SELECT Id, IdGUID, Title, ImageUrl, SortOrder, IsActive, Status
            FROM dbo.WN_GalleryImages
            WHERE ISNULL(IsActive, 1) = 1 AND ISNULL(Status, 1) != 0
            ORDER BY ISNULL(SortOrder, 9999), Id
        """)
        rows = cursor.fetchall()
        result = []
        for row in rows:
            guid = str(row.get("IdGUID") or "")
            result.append({
                "id":        guid,
                "numericId": row.get("Id"),
                "idGuid":    guid,
                "title":     row.get("Title") or "",
                "imageUrl":  row.get("ImageUrl") or "",
                "sortOrder": row.get("SortOrder") or 0,
                "isActive":  True,
            })
        return result
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
                guid = str(row.get("IdGUID") or row.get("idGuid") or "")
                plans_dict[plan_id] = {
                    "id":          plan_id,
                    "idGuid":      guid,
                    "name":        row.get("Name") or row.get("name"),
                    "price":       float(price_val) if price_val is not None else 0.0,
                    "description": row.get("Description") or row.get("description") or "",
                    "billingCycle": row.get("BillingCycle") or row.get("billingCycle") or "",
                    "includesHours": row.get("IncludesHours") or row.get("includesHours") or 0,
                    "isActive":    bool(row.get("IsActive") or row.get("isActive")),
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
        cursor.execute("""
            SELECT
                b.IdGUID AS idGuid,
                b.Id AS id,
                ISNULL(s.Name, st.Description) AS spaceName,
                st.Description AS spaceTypeName,
                b.StartDateTime AS startDateTime,
                b.EndDateTime AS endDateTime,
                b.TotalAmount AS totalAmount,
                b.Notes AS notes,
                b.CreatedOn AS createdAt,
                CASE b.BookingStatus
                    WHEN 1 THEN 'Confirmed'
                    WHEN 2 THEN 'Cancelled'
                    WHEN 3 THEN 'Rejected'
                    WHEN 4 THEN 'Completed'
                    ELSE 'Confirmed'
                END AS bookingStatus
            FROM dbo.WN_Bookings b WITH (NOLOCK)
            INNER JOIN dbo.WN_Users u ON b.UserGuid = u.IdGUID
            LEFT JOIN dbo.WN_Spaces s ON b.SpaceGuid = s.IdGUID
            LEFT JOIN dbo.WN_SpaceTypes st ON s.SpaceTypeId = st.IdGUID
            WHERE u.Id = %d AND b.Status != 0
            ORDER BY b.CreatedOn DESC
        """, (user_id,))
        rows = cursor.fetchall()
        for row in rows:
            row["idGuid"] = str(row.get("idGuid") or "")
            row["id"]     = row.get("id")
            row["totalAmount"]   = float(row["totalAmount"]) if row.get("totalAmount") is not None else 0.0
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
        booking_guid = None
        if booking_id:
            cursor.execute("SELECT IdGUID FROM dbo.WN_Bookings WHERE Id = %d", (booking_id,))
            r = cursor.fetchone()
            if r:
                booking_guid = r.get("IdGUID") if isinstance(r, dict) else r[0]
        payment_result = None
        if payment_method and booking_id:
            cursor.execute(SP_CREATE_PAYMENT, (user_id, booking_id, amount, payment_method, reference_number))
            prow = cursor.fetchone()
            payment_id = prow[0] if prow else None
            payment_guid = None
            if payment_id:
                cursor.execute("SELECT IdGUID FROM dbo.WN_Payments WHERE Id = %d", (payment_id,))
                pr = cursor.fetchone()
                if pr:
                    payment_guid = pr.get("IdGUID") if isinstance(pr, dict) else pr[0]
            payment_result = {"id": payment_id, "idGuid": payment_guid}
        conn.commit()
        return {"id": booking_id, "idGuid": booking_guid, "payment": payment_result}
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
            row["idGuid"] = row.get("IdGUID") or row.get("idGuid")
            row["id"] = row.get("Id") or row.get("id")
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
            guid = str(row.get("IdGUID") or row.get("idGuid") or "")
            row["id"] = row.get("Id") or row.get("id")
            row["idGuid"] = guid
            if "Name" in row and "name" not in row:
                row["name"] = row["Name"]
            status = row.get("status") or row.get("Status") or row.get("IsActive") or row.get("isActive")
            row["isActive"] = bool(status) if status is not None else True
            row["cityId"]    = row.get("cityId")
            row["cityName"]  = row.get("cityName") or ""
            row["branchId"]  = row.get("branchId")
            row["branchName"]= row.get("branchName") or ""
            row["branchCode"]= row.get("branchCode") or ""
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_all_cities():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_ALL_CITIES)
        rows = cursor.fetchall()
        return [{
            "id":     row.get("id"),
            "idGuid": str(row.get("idGuid") or ""),
            "name":   row.get("name") or "",
        } for row in rows]
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_all_branches():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_ALL_BRANCHES)
        rows = cursor.fetchall()
        return [{
            "id":          row.get("Id"),
            "description": row.get("Description") or "",
            "code":        row.get("Code") or "",
        } for row in rows]
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_all_companies():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_ALL_COMPANIES)
        rows = cursor.fetchall()
        return [{
            "id":   row.get("Id"),
            "name": row.get("CompanyName") or "",
        } for row in rows]
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
                b.IdGUID AS idGuid,
                b.Id AS id,
                ISNULL(s.Name, st.Description) AS spaceName,
                b.StartDateTime AS startDateTime,
                b.EndDateTime AS endDateTime,
                b.TotalAmount AS totalAmount,
                CASE
                    WHEN b.BookingStatus = 2 THEN 'Cancelled'
                    WHEN b.BookingStatus = 3 THEN 'Rejected'
                    ELSE 'Confirmed'
                END AS bookingStatus
            FROM dbo.WN_Bookings b
            LEFT JOIN dbo.WN_Spaces s ON b.SpaceGuid = s.IdGUID
            LEFT JOIN dbo.WN_SpaceTypes st ON s.SpaceTypeId = st.IdGUID
            WHERE b.Id = %d AND b.UserGuid = %s
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
        prow = cursor.fetchone()
        payment_id = prow[0] if prow else None
        payment_guid = None
        if payment_id:
            cursor.execute("SELECT IdGUID FROM dbo.WN_Payments WHERE Id = %d", (payment_id,))
            pr = cursor.fetchone()
            if pr:
                payment_guid = pr.get("IdGUID") if isinstance(pr, dict) else pr[0]
        conn.commit()
        return {"id": payment_id, "idGuid": payment_guid}
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
        result = []
        for row in rows:
            guid = str(row.get("IdGuid") or row.get("idGuid") or row.get("IdGUID") or "")
            result.append({
                "id":        row.get("Id") or row.get("id") or row.get("numericId"),
                "idGuid":    guid,
                "email":     row.get("Email") or row.get("email") or "",
                "name":      row.get("Name") or row.get("name") or "",
                "phone":     row.get("Phone") or row.get("phone") or "",
                "createdAt": _iso(row.get("CreatedAt") or row.get("createdAt")),
                "isActive":  True,
                "role":      map_role(row.get("Roles_Int") or row.get("roles_int")),
                "companyId": row.get("CompanyId") or row.get("companyId") or DEFAULT_COMPANY_ID,
            })
        return result
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_all_bookings():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT
                b.IdGUID AS idGuid,
                b.Id AS id,
                u.Email AS userEmail,
                ISNULL(s.Name, st.Description) AS spaceName,
                st.Description AS spaceTypeName,
                b.StartDateTime AS startDateTime,
                b.EndDateTime AS endDateTime,
                b.TotalAmount AS totalAmount,
                b.Notes AS notes,
                b.CreatedOn AS createdAt,
                CASE b.BookingStatus
                    WHEN 1 THEN 'Confirmed'
                    WHEN 2 THEN 'Cancelled'
                    WHEN 3 THEN 'Rejected'
                    WHEN 4 THEN 'Completed'
                    ELSE 'Confirmed'
                END AS bookingStatus
            FROM dbo.WN_Bookings b WITH (NOLOCK)
            LEFT JOIN dbo.WN_Users u ON b.UserGuid = u.IdGUID
            LEFT JOIN dbo.WN_Spaces s ON b.SpaceGuid = s.IdGUID
            LEFT JOIN dbo.WN_SpaceTypes st ON s.SpaceTypeId = st.IdGUID
            WHERE b.Status != 0
            ORDER BY b.CreatedOn DESC
        """)
        rows = cursor.fetchall()
        for row in rows:
            guid = str(row.get("idGuid") or row.get("IdGUID") or "")
            row["id"]            = row.get("id") or row.get("Id")
            row["idGuid"]        = guid
            row["userEmail"]     = row.get("userEmail") or ""
            row["spaceName"]     = row.get("spaceName") or ""
            row["bookingStatus"] = row.get("bookingStatus") or ""
            row["totalAmount"]   = float(row.get("totalAmount") or 0)
            row["startDateTime"] = _iso(row.get("startDateTime"))
            row["endDateTime"]   = _iso(row.get("endDateTime"))
            row["createdAt"]     = _iso(row.get("createdAt"))
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
            # SP returns camelCase: idGuid, id, userEmail, amount, paymentMethod, paymentStatus, transactionRef, paidAt
            guid = str(row.get("idGuid") or row.get("IdGUID") or "")
            row["id"]            = row.get("id") or row.get("Id")
            row["idGuid"]        = guid
            row["userEmail"]     = row.get("userEmail") or row.get("UserEmail") or ""
            row["paymentMethod"] = row.get("paymentMethod") or row.get("PaymentMethod") or ""
            row["paymentStatus"] = row.get("paymentStatus") or row.get("PaymentStatus") or ""
            row["transactionRef"]= row.get("transactionRef") or row.get("TransactionRef") or ""
            row["amount"]        = float(row.get("amount") or row.get("Amount") or 0)
            row["paidAt"]        = _iso(row.get("paidAt") or row.get("PaidAt"))
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_all_space_types():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT st.Id, st.IdGUID, st.Description, st.Capacity, st.HourlyAllowed, st.Status
            FROM dbo.WN_SpaceTypes st WITH (NOLOCK)
            WHERE st.Status != 0
        """)
        rows = cursor.fetchall()
        return [{
            "id":            row.get("Id"),
            "idGuid":        str(row.get("IdGUID") or ""),
            "name":          row.get("Description") or row.get("Name") or "",
            "capacity":      row.get("Capacity"),
            "hourlyAllowed": bool(row.get("HourlyAllowed")),
            "isActive":      row.get("Status") == 1,
        } for row in rows]
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_all_contacts():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT IdGUID, Id, Name, Email, PhoneNumber, Message, CreatedOn, Status
            FROM dbo.WN_BookTour
            WHERE ISNULL(Status, 1) != 0
            ORDER BY CreatedOn DESC
        """)
        rows = cursor.fetchall()
        result = []
        for row in rows:
            guid = str(row.get("IdGUID") or "")
            result.append({
                "id":        row.get("Id"),
                "idGuid":    guid,
                "fullName":  row.get("Name") or "",
                "email":     row.get("Email") or "",
                "phone":     row.get("PhoneNumber") or "",
                "message":   row.get("Message") or "",
                "status":    row.get("Status"),
                "createdAt": _iso(row.get("CreatedOn")),
            })
        return result
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_all_memberships():
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT m.IdGUID AS idGuid, m.Id AS numericId, u.Email AS userEmail,
                   pp.Name AS planName, pp.Price AS planPrice, pp.BillingCycle AS planCycle,
                   m.StartDate AS startDate, m.EndDate AS endDate, m.Status AS status
            FROM dbo.WN_Memberships m
            LEFT JOIN dbo.WN_Users u ON m.UserGuid = u.IdGUID
            LEFT JOIN dbo.WN_PricingPlans pp ON m.PlanId = pp.Id
            WHERE m.Status != 0
        """)
        rows = cursor.fetchall()
        for row in rows:
            guid = str(row.get("idGuid") or "")
            row["id"] = row.get("numericId") or row.get("id")
            row["idGuid"] = guid
            row["startDate"] = _iso(row.get("startDate"))
            row["endDate"]   = _iso(row.get("endDate"))
            row["planPrice"] = float(row["planPrice"]) if row.get("planPrice") else 0.0
        return rows
    except Exception as e:
        raise e
    finally:
        conn.close()


def insert_space(name, location_id, space_type_id, code, description, floor_id, price_per_day, price_per_hour, image_url, amenities):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        loc_guid = st_guid = None
        if location_id:
            cursor.execute("SELECT IdGUID FROM dbo.WN_Locations WITH (NOLOCK) WHERE Id=%d", (int(location_id),))
            row = cursor.fetchone()
            loc_guid = row[0] if row else None
        if space_type_id:
            cursor.execute("SELECT IdGUID FROM dbo.WN_SpaceTypes WITH (NOLOCK) WHERE Id=%d", (int(space_type_id),))
            row = cursor.fetchone()
            st_guid = row[0] if row else None
        cursor.execute("""
            INSERT INTO dbo.WN_Spaces
                (Name, LocationId, SpaceTypeId, Code, Description, FloorId, PricePerDay, PricePerHour, ImageUrl, Amenities, Status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1);
            SELECT SCOPE_IDENTITY() AS id
        """, (name, loc_guid, st_guid, code, description, floor_id, price_per_day, price_per_hour, image_url, amenities))
        row = cursor.fetchone()
        new_id = row[0] if row else None
        conn.commit()
        return new_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def update_space(space_id, name, location_id, space_type_id, code, description, floor_id, price_per_day, price_per_hour, image_url, amenities):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        loc_guid = st_guid = None
        if location_id:
            cursor.execute("SELECT IdGUID FROM dbo.WN_Locations WITH (NOLOCK) WHERE Id=%d", (int(location_id),))
            row = cursor.fetchone()
            loc_guid = row[0] if row else None
        if space_type_id:
            cursor.execute("SELECT IdGUID FROM dbo.WN_SpaceTypes WITH (NOLOCK) WHERE Id=%d", (int(space_type_id),))
            row = cursor.fetchone()
            st_guid = row[0] if row else None
        # Only update GUID fields if resolved, otherwise keep existing
        if loc_guid and st_guid:
            cursor.execute("""
                UPDATE dbo.WN_Spaces SET
                    Name=%s, LocationId=%s, SpaceTypeId=%s, Code=%s, Description=%s,
                    FloorId=%s, PricePerDay=%s, PricePerHour=%s, ImageUrl=%s, Amenities=%s
                WHERE Id=%d
            """, (name, loc_guid, st_guid, code, description,
                   floor_id, price_per_day, price_per_hour, image_url, amenities, space_id))
        else:
            cursor.execute("""
                UPDATE dbo.WN_Spaces SET
                    Name=%s, Code=%s, Description=%s,
                    FloorId=%s, PricePerDay=%s, PricePerHour=%s, ImageUrl=%s, Amenities=%s
                WHERE Id=%d
            """, (name, code, description,
                   floor_id, price_per_day, price_per_hour, image_url, amenities, space_id))
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


# ============================================================
# Auto-Assignment Booking System Functions
# ============================================================

def get_available_spaces(space_type: str, start_datetime: str, end_datetime: str):
    """Get available spaces for auto-assignment with naming convention priority."""
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_AVAILABLE_SPACES, (space_type, start_datetime, end_datetime))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                "id": row.get("Id"),
                "idGuid": str(row.get("IdGUID") or ""),
                "name": row.get("Name") or "",
                "code": row.get("Code") or "",
                "pricePerDay": float(row.get("PricePerDay") or 0),
                "pricePerHour": float(row.get("PricePerHour") or 0),
                "spaceType": row.get("SpaceType") or "",
                "locationName": row.get("LocationName") or "",
                "priority": row.get("Priority") or 1,
                "isAutoAssigned": True
            })
        return result
    except Exception as e:
        raise e
    finally:
        conn.close()


def create_booking_with_auto_assignment(user_email: str, space_type: str, start_datetime: str,
                                        end_datetime: str, notes: str = "", total_amount: float = 0,
                                        payment_method: str = None, payment_ref: str = None):
    """Create booking with automatic space assignment using WN_CreateBookingWithAutoAssignment SP."""
    conn = pymssql.connect(
        server=DB_SERVER, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME,
        autocommit=True  # required: SP manages its own transaction with COMMIT
    )
    try:
        cursor = conn.cursor(as_dict=True)
        # Ensure user Status = 1 so the SP's WHERE Status = 1 check passes
        cursor.execute("UPDATE dbo.WN_Users SET Status = 1 WHERE Email = %s AND (Status IS NULL OR Status != 1)", (user_email,))
        # pymssql does not support OUTPUT params directly — use a wrapper SELECT
        cursor.execute("""
            DECLARE @BookingId INT, @BookingGuid UNIQUEIDENTIFIER,
                    @AssignedSpaceId INT, @AssignedSpaceName NVARCHAR(255);

            EXEC dbo.WN_CreateBookingWithAutoAssignment
                @Email          = %s,
                @SpaceType      = %s,
                @StartDateTime  = %s,
                @EndDateTime    = %s,
                @Notes          = %s,
                @TotalAmount    = %s,
                @PaymentMethod  = %s,
                @PaymentRef     = %s,
                @BookingId      = @BookingId      OUTPUT,
                @BookingGuid    = @BookingGuid    OUTPUT,
                @AssignedSpaceId   = @AssignedSpaceId   OUTPUT,
                @AssignedSpaceName = @AssignedSpaceName OUTPUT;

            SELECT @BookingId AS bookingId, CAST(@BookingGuid AS NVARCHAR(36)) AS bookingGuid,
                   @AssignedSpaceId AS assignedSpaceId, @AssignedSpaceName AS assignedSpaceName;
        """, (
            user_email, space_type, start_datetime, end_datetime,
            notes or '', total_amount,
            payment_method, payment_ref
        ))

        # Advance past any empty result sets from SET NOCOUNT ON
        row = None
        while True:
            row = cursor.fetchone()
            if row is not None:
                break
            if not cursor.nextset():
                break

        # Fallback: if OUTPUT params came back null, fetch the most recent booking for this user
        if not row or not row.get('bookingId'):
            cursor.execute("""
                SELECT TOP 1 b.Id AS bookingId, CAST(b.IdGUID AS NVARCHAR(36)) AS bookingGuid,
                       s.Id AS assignedSpaceId, s.Name AS assignedSpaceName
                FROM dbo.WN_Bookings b
                INNER JOIN dbo.WN_Users u ON b.UserGuid = u.IdGUID
                LEFT JOIN dbo.WN_Spaces s ON b.SpaceGuid = s.IdGUID
                WHERE u.Email = %s AND b.Status = 1
                ORDER BY b.CreatedOn DESC
            """, (user_email,))
            row = cursor.fetchone()

        if not row or not row.get('bookingId'):
            raise Exception('Auto-assignment booking returned no result')

        return {
            'id':                row['bookingId'],
            'idGuid':            row['bookingGuid'],
            'assignedSpaceId':   row['assignedSpaceId'],
            'assignedSpaceName': row['assignedSpaceName'],
            'spaceType':         space_type,
            'isAutoAssigned':    True
        }
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_availability_counts():
    """Get real-time availability counts by space type."""
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_AVAILABILITY_COUNTS)
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                "spaceType": row.get("spaceType") or "",
                "totalSpaces": row.get("totalSpaces") or 0,
                "availableSpaces": row.get("availableSpaces") or 0,
                "bookedSpaces": row.get("bookedSpaces") or 0
            })
        return result
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_available_spaces_by_type(space_type: str, start_datetime: str = None, end_datetime: str = None):
    """Get availability count for specific space type with optional time filter."""
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_AVAILABLE_BY_TYPE, (space_type, start_datetime, end_datetime))
        row = cursor.fetchone()
        if row:
            return {
                "spaceType": space_type,
                "totalSpaces": row.get("totalSpaces") or 0,
                "availableSpaces": row.get("availableSpaces") or 0
            }
        return {"spaceType": space_type, "totalSpaces": 0, "availableSpaces": 0}
    except Exception as e:
        raise e
    finally:
        conn.close()


def reassign_booking(booking_id: int, new_space_id: int, admin_user_email: str):
    """Reassign booking to different space (admin only)."""
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        # Resolve booking GUID from numeric id
        cursor.execute("SELECT IdGUID FROM dbo.WN_Bookings WITH (NOLOCK) WHERE Id = %d", (booking_id,))
        row = cursor.fetchone()
        if not row:
            raise Exception("Booking not found")
        booking_guid = str(row["IdGUID"])
        # Resolve space GUID from numeric id
        cursor.execute("SELECT IdGUID FROM dbo.WN_Spaces WITH (NOLOCK) WHERE Id = %d", (new_space_id,))
        row = cursor.fetchone()
        if not row:
            raise Exception("Space not found")
        space_guid = str(row["IdGUID"])
        cursor.execute(SP_REASSIGN_BOOKING, (booking_guid, space_guid, admin_user_email))
        result = cursor.fetchone()
        conn.commit()
        
        if result:
            return {
                "bookingId": str(result.get("bookingId") or ""),
                "newSpaceName": result.get("newSpaceName") or "",
                "newSpaceCode": result.get("newSpaceCode") or "",
                "status": result.get("status") or "Success"
            }
        else:
            raise Exception("Failed to reassign booking")
            
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_available_spaces_for_reassignment(space_type: str, start_datetime: str, end_datetime: str, exclude_booking_id: int = None):
    """Get available spaces for admin reassignment."""
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_SPACES_FOR_REASSIGNMENT, (space_type, start_datetime, end_datetime, exclude_booking_id))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                "id": row.get("Id"),
                "idGuid": str(row.get("IdGUID") or ""),
                "name": row.get("Name") or "",
                "code": row.get("Code") or "",
                "description": row.get("Description") or "",
                "locationName": row.get("LocationName") or ""
            })
        return result
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_space_config():
    """Get all space category configuration from WN_SpaceConfig."""
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT Id, SpaceCategory, TotalSpaces, CodePrefix, MinCode,
                   DefaultCapacities, OpeningTime, ClosingTime,
                   ISNULL(SecurityDeposit, 0) AS SecurityDeposit,
                   UpdatedOn, UpdatedBy
            FROM dbo.WN_SpaceConfig
            ORDER BY Id
        """)
        rows = cursor.fetchall()
        return [{
            "id":                row.get("Id"),
            "spaceCategory":     row.get("SpaceCategory") or "",
            "totalSpaces":       row.get("TotalSpaces") or 0,
            "codePrefix":        row.get("CodePrefix") or "",
            "minCode":           row.get("MinCode") or 0,
            "defaultCapacities": row.get("DefaultCapacities") or "",
            "openingTime":       row.get("OpeningTime") or "",
            "closingTime":       row.get("ClosingTime") or "",
            "securityDeposit":   float(row.get("SecurityDeposit") or 0),
            "updatedOn":         _iso(row.get("UpdatedOn")),
            "updatedBy":         row.get("UpdatedBy") or "",
        } for row in rows]
    except Exception as e:
        raise e
    finally:
        conn.close()


def update_space_config(space_category: str, total_spaces: int,
                        default_capacities: str = None, opening_time: str = None,
                        closing_time: str = None, admin_email: str = None,
                        security_deposit: float = None):
    """Update space category config via WN_Spaces_UpdateConfig."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "EXEC dbo.WN_Spaces_UpdateConfig %s, %s, %s, %s, %s, %s, %s",
            (space_category, total_spaces, default_capacities,
             opening_time, closing_time, admin_email, security_deposit)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def generate_space_inventory(space_category: str, space_type_id: int, location_id: int,
                              price_per_hour: float = 0, price_per_day: float = 0):
    """Generate/sync space inventory via WN_Spaces_GenerateInventory."""
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(
            "EXEC dbo.WN_Spaces_GenerateInventory %s, %s, %s, %s, %s",
            (space_category, space_type_id, location_id, price_per_hour, price_per_day)
        )
        row = cursor.fetchone()
        conn.commit()
        return row or {}
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def check_booking_overlap(space_id: int, start_datetime: str, end_datetime: str,
                           exclude_booking_id: int = None):
    """Check if a space has an overlapping booking."""
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_CHECK_OVERLAP, (space_id, start_datetime, end_datetime))
        row = cursor.fetchone()
        return bool(row.get("IsOverlapping")) if row else False
    except Exception as e:
        raise e
    finally:
        conn.close()


def get_available_spaces_v2(space_category: str, start_datetime: str,
                             end_datetime: str, capacity: int = None):
    """Get available spaces using WN_Booking_GetAvailableSpaces (v2)."""
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_AVAILABLE_V2, (space_category, start_datetime, end_datetime, capacity))
        rows = cursor.fetchall()
        return [{
            "id":           row.get("Id"),
            "idGuid":       str(row.get("IdGUID") or ""),
            "name":         row.get("Name") or "",
            "code":         row.get("Code") or "",
            "codeNumber":   row.get("CodeNumber"),
            "capacity":     row.get("Capacity"),
            "pricePerDay":  float(row.get("PricePerDay") or 0),
            "pricePerHour": float(row.get("PricePerHour") or 0),
            "spaceType":    row.get("SpaceType") or "",
            "locationName": row.get("LocationName") or "",
        } for row in rows]
    except Exception as e:
        raise e
    finally:
        conn.close()


def create_smart_booking(user_email: str, space_category: str, start_datetime: str,
                          end_datetime: str, notes: str = "", total_amount: float = 0,
                          payment_method: str = None, payment_ref: str = None,
                          capacity: int = None):
    """Create booking with closest-space auto-assignment via WN_Booking_Create SP."""
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute("UPDATE dbo.WN_Users SET Status = 1 WHERE Email = %s AND (Status IS NULL OR Status != 1)", (user_email,))
        cursor.execute(
            "EXEC dbo.WN_Booking_Create @Email=%s, @SpaceCategory=%s, @StartDT=%s, @EndDT=%s,"
            " @Notes=%s, @TotalAmount=%s, @PaymentMethod=%s, @PaymentRef=%s, @Capacity=%s",
            (user_email, space_category, start_datetime, end_datetime,
             notes or '', total_amount, payment_method, payment_ref, capacity)
        )
        row = None
        while True:
            row = cursor.fetchone()
            if row is not None:
                break
            if not cursor.nextset():
                break
        conn.commit()
        if not row:
            raise Exception('Smart booking returned no result')
        if row.get('errorMessage'):
            raise Exception(row['errorMessage'])
        return {
            'id':                row['bookingId'],
            'idGuid':            row['bookingGuid'],
            'assignedSpaceId':   row['assignedSpaceId'],
            'assignedSpaceName': row['assignedSpaceName'],
            'assignedSpaceCode': row['assignedSpaceCode'],
            'spaceCategory':     space_category,
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_booking_calendar(space_id: int, year: int, month: int):
    """Get booking calendar data for specific space."""
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(SP_GET_BOOKING_CALENDAR, (space_id, year, month))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                "bookingId": str(row.get("bookingId") or ""),
                "startDateTime": _iso(row.get("StartDateTime")),
                "endDateTime": _iso(row.get("EndDateTime")),
                "startDate": row.get("startDate") or "",
                "endDate": row.get("endDate") or "",
                "userEmail": row.get("userEmail") or "",
                "userName": row.get("userName") or "",
                "status": row.get("status") or "",
                "totalAmount": float(row.get("TotalAmount") or 0)
            })
        return result
    except Exception as e:
        raise e
    finally:
        conn.close()
