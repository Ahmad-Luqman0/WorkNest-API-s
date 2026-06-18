import pymssql
import os

try:
    from api.roles import map_role
except ImportError:
    from roles import map_role

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
SP_CREATE_BOOKING_AUTO_ASSIGN = "EXEC dbo.WN_CreateBookingWithAutoAssignment %s, %s, %s, %s, %s, %s, %s, %s"
SP_GET_AVAILABILITY_COUNTS = "EXEC dbo.WN_GetAvailabilityCounts"
SP_GET_AVAILABLE_BY_TYPE = "EXEC dbo.WN_GetAvailableSpacesByType %s, %s, %s"
SP_REASSIGN_BOOKING = "EXEC dbo.WN_ReassignBooking %s, %s, %s"
SP_GET_SPACES_FOR_REASSIGNMENT = "EXEC dbo.WN_GetAvailableSpacesForReassignment %s, %s, %s, %s"
SP_GET_BOOKING_CALENDAR = "EXEC dbo.WN_GetBookingCalendar %s, %s, %s"


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
        default_name = email.split("@")[0]
        return sync_user(email, default_name, "")
    except Exception:
        return (None, None)
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
            SELECT s.IdGUID, s.Id, s.Name, s.Code, s.Description, s.Floor,
                   s.PricePerDay, s.PricePerHour, s.Amenities, s.ImageUrl, s.Status,
                   l.Name AS LocationName, l.IdGUID AS LocationIdGuid,
                   st.Description AS SpaceTypeName, st.IdGUID AS SpaceTypeIdGuid,
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
            guid = str(row.get("IdGUID") or row.get("idGuid") or "")
            result.append({
                "id":             row.get("Id") or row.get("id"),
                "idGuid":         guid,
                "name":           row.get("Name") or row.get("name"),
                "code":           row.get("Code") or row.get("code"),
                "locationIdGuid": str(row.get("LocationIdGuid") or ""),
                "spaceTypeIdGuid":str(row.get("SpaceTypeIdGuid") or ""),
                "locationName":   row.get("LocationName") or row.get("locationName"),
                "spaceTypeName":  row.get("SpaceTypeName") or row.get("spaceTypeName"),
                "capacity":       row.get("Capacity") or row.get("capacity"),
                "pricePerDay":    float(price_val) if price_val is not None else 0.0,
                "pricePerHour":   float(row.get("PricePerHour") or row.get("pricePerHour") or 0),
                "amenities":      row.get("Amenities") or row.get("amenities"),
                "imageUrl":       row.get("ImageUrl") or row.get("imageUrl"),
                "status":         row.get("Status") or row.get("status"),
                "spaceStatus":    "Available" if (row.get("Status") or row.get("status")) == 1 else "Inactive",
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
            SELECT Id, IdGUID, Title, ImageUrl, SortOrder, IsActive, CreatedOn AS createdAt
            FROM dbo.WN_GalleryImages
            WHERE Status = 1
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
                "isActive":  bool(row.get("IsActive")) if row.get("IsActive") is not None else True,
                "createdAt": _iso(row.get("createdAt")),
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
        cursor.execute(SP_GET_MY_BOOKINGS, (user_id,))
        rows = cursor.fetchall()
        for row in rows:
            row["idGuid"] = row.get("IdGUID") or row.get("idGuid")
            row["id"] = row.get("Id") or row.get("id")
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
        cursor.execute("""
            SELECT u.IdGUID AS idGuid, u.Id AS numericId, u.Email AS email,
                   u.Name AS name, u.PhoneNumber AS phone,
                   u.CreatedOn AS createdAt, u.RoleId AS roles_int
            FROM dbo.WN_Users u WITH (NOLOCK)
            ORDER BY u.CreatedOn DESC
        """)
        rows = cursor.fetchall()
        result = []
        for row in rows:
            guid = str(row["idGuid"]) if row.get("idGuid") else ""
            result.append({
                "id":        row.get("numericId"),
                "idGuid":    guid,
                "email":     row.get("email") or "",
                "name":      row.get("name") or "",
                "phone":     row.get("phone") or "",
                "createdAt": _iso(row.get("createdAt")),
                "isActive":  True,
                "role":      map_role(row.get("roles_int")),
                "companyId": row.get("companyId") or DEFAULT_COMPANY_ID,
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
        cursor.execute(SP_GET_ALL_BOOKINGS)
        rows = cursor.fetchall()
        for row in rows:
            guid = str(row.get("IdGUID") or row.get("idGuid") or "")
            row["id"] = row.get("Id") or row.get("id")
            row["idGuid"] = guid
            amount = row.get("totalAmount") or row.get("TotalAmount") or row.get("Total_Amount") or 0
            row["totalAmount"]   = float(amount) if amount is not None else 0.0
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
            guid = str(row.get("IdGUID") or row.get("idGuid") or "")
            row["id"] = row.get("Id") or row.get("id")
            row["idGuid"] = guid
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
        cursor.execute(SP_GET_ALL_CONTACTS)
        rows = cursor.fetchall()
        for row in rows:
            guid = str(row.get("IdGUID") or row.get("idGuid") or "")
            row["id"] = row.get("Id") or row.get("id")
            row["idGuid"] = guid
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
    """Create booking with automatic space assignment using stored procedure."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Call stored procedure with output parameters
        cursor.execute("""
            DECLARE @bookingId INT, @bookingGuid UNIQUEIDENTIFIER, 
                    @assignedSpaceId INT, @assignedSpaceName NVARCHAR(255);
            
            EXEC dbo.sp_CreateBookingWithAutoAssignment 
                @userEmail = %s, @spaceType = %s, @startDateTime = %s, @endDateTime = %s,
                @notes = %s, @totalAmount = %s, @paymentMethod = %s, @paymentRef = %s,
                @bookingId = @bookingId OUTPUT, @bookingGuid = @bookingGuid OUTPUT,
                @assignedSpaceId = @assignedSpaceId OUTPUT, @assignedSpaceName = @assignedSpaceName OUTPUT;
            
            SELECT @bookingId AS bookingId, @bookingGuid AS bookingGuid, 
                   @assignedSpaceId AS assignedSpaceId, @assignedSpaceName AS assignedSpaceName;
        """, (user_email, space_type, start_datetime, end_datetime, notes, total_amount, payment_method, payment_ref))
        
        result = cursor.fetchone()
        conn.commit()
        
        if result:
            return {
                "id": result[0],  # bookingId
                "idGuid": str(result[1]) if result[1] else None,  # bookingGuid
                "assignedSpaceId": result[2],  # assignedSpaceId
                "assignedSpaceName": result[3],  # assignedSpaceName
                "spaceType": space_type,
                "isAutoAssigned": True
            }
        else:
            raise Exception("Failed to create booking with auto-assignment")
            
    except Exception as e:
        conn.rollback()
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
        cursor.execute(SP_REASSIGN_BOOKING, (booking_id, new_space_id, admin_user_email))
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
