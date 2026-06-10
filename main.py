from fastapi import FastAPI, HTTPException, Request, status, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import random
from datetime import datetime, timedelta

try:
    from api.payfast import build_payfast_payload, verify_notify_signature
except ImportError:
    from payfast import build_payfast_payload, verify_notify_signature

try:
    from api.db import (
        book_tour,
        get_all_spaces,
        get_gallery_images,
        get_pricing_plans,
        get_my_bookings,
        create_booking,
        cancel_booking,
        get_my_payments,
        sync_user,
        get_user_id_by_email, 
        get_all_locations, 
        get_booking_by_id,
        create_payment,
        get_all_users, 
        get_all_bookings, 
        get_all_payments,
        get_all_space_types, 
        get_all_contacts, 
        get_all_memberships,
        insert_space, 
        update_space,
        delete_space, 
        update_payment_status,
        get_connection,
        _iso
    )
except ImportError:
    from db import (
        book_tour,
        get_all_spaces,
        get_gallery_images,
        get_pricing_plans,
        get_my_bookings,
        create_booking,
        cancel_booking,
        get_my_payments,
        sync_user,
        get_user_id_by_email, 
        get_all_locations, 
        get_booking_by_id,
        create_payment,
        get_all_users, 
        get_all_bookings, 
        get_all_payments,
        get_all_space_types, 
        get_all_contacts, 
        get_all_memberships,
        insert_space, 
        update_space,
        delete_space, 
        update_payment_status,
        get_connection,
        _iso
    )

app = FastAPI(title="WorkNest API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_USER_ID = 1


# ── Helpers ───────────────────────────────────────────────────────────────────

def paginate(items: list, page: int, limit: int, search: str = ""):
    if search:
        s = search.lower()
        items = [i for i in items if any(s in str(v).lower() for v in i.values())]
    total = len(items)
    start = (page - 1) * limit
    return {"data": items[start:start + limit], "total": total}


def ok(data=None, message="Success"):
    return {"isSuccessful": True, "message": message, "data": data}


# ── Pydantic Models ───────────────────────────────────────────────────────────

class UserSyncRequest(BaseModel):
    email: EmailStr
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phone: Optional[str] = None

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phone: Optional[str] = None

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = None

class GoogleLoginRequest(BaseModel):
    idToken: str
    email: EmailStr
    firstName: Optional[str] = None
    lastName: Optional[str] = None

class ContactRequest(BaseModel):
    fullName: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    message: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=1, max_length=20)

class GuestDetails(BaseModel):
    name: str
    email: str
    phone: str

class PaymentDetails(BaseModel):
    method: str
    amount: float
    voucherCode: Optional[str] = None
    bankDepositId: Optional[str] = None
    referenceNumber: Optional[str] = None

class BookingRequest(BaseModel):
    spaceId: int
    startDateTime: str
    endDateTime: str
    notes: Optional[str] = None
    guest: Optional[GuestDetails] = None
    payment: Optional[PaymentDetails] = None
    totalAmount: Optional[float] = None

class SpaceInsertRequest(BaseModel):
    name: str
    locationId: int
    spaceTypeId: int
    code: Optional[str] = None
    description: Optional[str] = None
    floor: Optional[str] = None
    pricePerDay: Optional[float] = None
    pricePerHour: Optional[float] = None
    imageUrl: Optional[str] = None
    amenities: Optional[str] = None

class SpaceUpdateRequest(BaseModel):
    name: Optional[str] = None
    locationId: Optional[int] = None
    spaceTypeId: Optional[int] = None
    code: Optional[str] = None
    description: Optional[str] = None
    floor: Optional[str] = None
    pricePerDay: Optional[float] = None
    pricePerHour: Optional[float] = None
    imageUrl: Optional[str] = None
    amenities: Optional[str] = None

class CardPaymentRequest(BaseModel):
    bookingId: int
    cardHolderName: str
    cardNumber: str
    expiryMonth: str
    expiryYear: str
    cvv: str

class PayFastInitiateRequest(BaseModel):
    bookingId: int
    customerName: str
    customerEmail: EmailStr

class CounterPaymentRequest(BaseModel):
    bookingId: int
    amount: float

class VoucherGenerateRequest(BaseModel):
    bookingId: int
    amount: float

class LocationUpsertRequest(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    openingTime: Optional[str] = None
    closingTime: Optional[str] = None
    isActive: Optional[bool] = True

class SpaceTypeUpsertRequest(BaseModel):
    name: str
    capacity: Optional[int] = None
    hourlyAllowed: Optional[bool] = False
    isActive: Optional[bool] = True

class PricingPlanUpsertRequest(BaseModel):
    name: str
    price: float
    billingCycle: Optional[str] = None
    includesHours: Optional[int] = None
    isActive: Optional[bool] = True

class MembershipCreateRequest(BaseModel):
    userId: Optional[str] = None
    planId: int
    startDate: str

class GalleryUpsertRequest(BaseModel):
    title: Optional[str] = None
    imageUrl: str
    sortOrder: Optional[int] = 0
    isActive: Optional[bool] = True

class PaymentCreateRequest(BaseModel):
    membershipId: Optional[int] = None
    amount: float
    paymentMethod: str

class UserCreateRequest(BaseModel):
    email: EmailStr
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    password: Optional[str] = None


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"app": "WorkNest FastAPI Backend", "status": "healthy"}


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/api/auth/sync")
@app.post("/auth/sync")
def sync_user_endpoint(payload: UserSyncRequest):
    user_id = sync_user(payload.email, payload.firstName or "", payload.lastName or "", payload.phone)
    return ok({"id": user_id, "email": payload.email}, "User synchronized successfully.")

@app.post("/api/auth/register")
@app.post("/auth/register")
def register_user(payload: UserRegisterRequest):
    user_id = sync_user(payload.email, payload.firstName or "", payload.lastName or "", payload.phone)
    return ok({"id": user_id, "email": payload.email}, "User registered successfully.")

@app.post("/api/auth/login")
@app.post("/auth/login")
def login_user(payload: UserLoginRequest):
    user_id = get_user_id_by_email(payload.email)
    return ok({"id": user_id, "email": payload.email}, "Login successful.")

@app.post("/api/auth/google-login")
@app.post("/auth/google-login")
def google_login_user(payload: GoogleLoginRequest):
    user_id = sync_user(payload.email, payload.firstName or "", payload.lastName or "")
    return ok({"id": user_id, "email": payload.email}, "Google login successful.")


# ── Users ─────────────────────────────────────────────────────────────────────

@app.get("/api/user")
@app.get("/user")
def list_users(page: int = Query(1), limit: int = Query(10), search: str = Query("")):
    try:
        rows = get_all_users()
        return paginate(rows, page, limit, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user/{id}")
@app.get("/user/{id}")
def get_user(id: str):
    try:
        conn = get_connection()
        cursor = conn.cursor(as_dict=True)
        try:
            uid = int(id)
            cursor.execute("SELECT * FROM dbo.WN_Users WHERE Id = %d AND Status = 1", (uid,))
        except ValueError:
            cursor.execute("SELECT * FROM dbo.WN_Users WHERE Email = %s AND Status = 1", (id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        row["createdAt"] = _iso(row.get("createdAt") or row.get("CreatedAt"))
        return ok(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user/{id}/history")
@app.get("/user/{id}/history")
def get_user_history(id: str):
    try:
        conn = get_connection()
        cursor = conn.cursor(as_dict=True)
        try:
            uid = int(id)
        except ValueError:
            cursor.execute("SELECT Id FROM dbo.WN_Users WHERE Email = %s", (id,))
            r = cursor.fetchone()
            uid = r["Id"] if r else None
        if not uid:
            raise HTTPException(status_code=404, detail="User not found")

        cursor.execute("""
            SELECT b.Id AS id,
                   s.Name AS spaceName,
                   b.StartDateTime AS startDateTime, b.EndDateTime AS endDateTime,
                   b.TotalAmount AS totalAmount,
                   CASE b.BookingStatus
                     WHEN 1 THEN 'Confirmed'
                     WHEN 2 THEN 'Cancelled'
                     WHEN 3 THEN 'Rejected'
                     WHEN 4 THEN 'Completed'
                     ELSE 'Pending'
                   END AS bookingStatus
            FROM dbo.WN_Bookings b
            LEFT JOIN dbo.WN_Spaces s ON b.SpaceGuid = s.IdGUID
            WHERE b.UserGuid = (SELECT IdGUID FROM dbo.WN_Users WHERE Id = %d) AND b.Status = 1
            ORDER BY b.StartDateTime DESC
        """, (uid,))
        bookings = cursor.fetchall()
        for b in bookings:
            b["startDateTime"] = _iso(b.get("startDateTime"))
            b["endDateTime"] = _iso(b.get("endDateTime"))
            b["totalAmount"] = float(b["totalAmount"]) if b.get("totalAmount") else 0.0

        cursor.execute("""
            SELECT p.Id AS id, p.Amount AS amount, p.PaymentMethod AS paymentMethod,
                   p.PaymentStatus AS paymentStatus, p.PaidAt AS paidAt, p.CreatedAt AS createdAt
            FROM dbo.WN_Payments p
            WHERE p.UserId = %d
            ORDER BY p.CreatedAt DESC
        """, (uid,))
        payments = cursor.fetchall()
        for p in payments:
            p["amount"] = float(p["amount"]) if p.get("amount") else 0.0
            p["paidAt"] = _iso(p.get("paidAt"))
            p["createdAt"] = _iso(p.get("createdAt"))

        total_paid = sum(p["amount"] for p in payments if p.get("paymentStatus") == "Paid")
        conn.close()
        return ok({
            "stats": {
                "totalBookings": len(bookings),
                "totalPayments": len(payments),
                "totalPaidAmount": total_paid,
                "failedPayments": sum(1 for p in payments if p.get("paymentStatus") == "Failed"),
                "cancelledBookings": sum(1 for b in bookings if b.get("bookingStatus") == "Cancelled"),
            },
            "recentBookings": bookings,
            "recentPayments": payments,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/user", status_code=201)
@app.post("/user", status_code=201)
def create_user(payload: UserCreateRequest):
    try:
        user_id = sync_user(payload.email, payload.firstName or "", payload.lastName or "")
        return ok({"id": user_id, "email": payload.email}, "User created successfully.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/user/{id}")
@app.delete("/user/{id}")
def delete_user(id: str):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_Users SET Status = 0 WHERE Id = %d", (int(id),))
        conn.commit()
        conn.close()
        return ok(message="User deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/user/{id}/activate")
@app.patch("/user/{id}/activate")
def activate_user(id: str):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_Users SET IsActive = 1 WHERE Id = %d", (int(id),))
        conn.commit()
        conn.close()
        return ok(message="User activated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/user/{id}/deactivate")
@app.patch("/user/{id}/deactivate")
def deactivate_user(id: str):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_Users SET IsActive = 0 WHERE Id = %d", (int(id),))
        conn.commit()
        conn.close()
        return ok(message="User deactivated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/user/{id}/role")
@app.patch("/user/{id}/role")
def update_user_role(id: str, body: dict):
    try:
        role = body.get("role", "")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_Users SET Role = %s WHERE Id = %d", (role, int(id)))
        conn.commit()
        conn.close()
        return ok(message="Role updated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Locations ─────────────────────────────────────────────────────────────────

@app.get("/api/location")
@app.get("/location")
def list_locations(page: int = Query(1), limit: int = Query(10), search: str = Query("")):
    try:
        return paginate(get_all_locations(), page, limit, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/location", status_code=201)
@app.post("/location", status_code=201)
def create_location(payload: LocationUpsertRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.WN_Locations (Name, Address, City, OpeningTime, ClosingTime, IsActive, Status)
            VALUES (%s, %s, %s, %s, %s, %d, 1); SELECT SCOPE_IDENTITY() AS id
        """, (payload.name, payload.address, payload.city, payload.openingTime, payload.closingTime, 1 if payload.isActive else 0))
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        return ok({"id": row[0] if row else None}, "Location created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/location/{id}")
@app.put("/location/{id}")
def update_location(id: int, payload: LocationUpsertRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE dbo.WN_Locations SET Name=%s, Address=%s, City=%s,
            OpeningTime=%s, ClosingTime=%s, IsActive=%d WHERE Id=%d
        """, (payload.name, payload.address, payload.city, payload.openingTime, payload.closingTime, 1 if payload.isActive else 0, id))
        conn.commit()
        conn.close()
        return ok(message="Location updated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/location/{id}")
@app.delete("/location/{id}")
def delete_location(id: int):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_Locations SET Status = 0 WHERE Id = %d", (id,))
        conn.commit()
        conn.close()
        return ok(message="Location deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Space Types ───────────────────────────────────────────────────────────────

@app.get("/api/spacetype")
@app.get("/spacetype")
def list_space_types(page: int = Query(1), limit: int = Query(10), search: str = Query("")):
    try:
        return paginate(get_all_space_types(), page, limit, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/spacetype", status_code=201)
@app.post("/spacetype", status_code=201)
def create_space_type(payload: SpaceTypeUpsertRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.WN_SpaceTypes (Description, Capacity, HourlyAllowed, Status)
            VALUES (%s, %d, %d, 1); SELECT SCOPE_IDENTITY() AS id
        """, (payload.name, payload.capacity or 0, 1 if payload.hourlyAllowed else 0))
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        return ok({"id": row[0] if row else None}, "Space type created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/spacetype/{id}")
@app.put("/spacetype/{id}")
def update_space_type(id: int, payload: SpaceTypeUpsertRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE dbo.WN_SpaceTypes SET Description=%s, Capacity=%d, HourlyAllowed=%d WHERE Id=%d
        """, (payload.name, payload.capacity or 0, 1 if payload.hourlyAllowed else 0, id))
        conn.commit()
        conn.close()
        return ok(message="Space type updated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/spacetype/{id}")
@app.delete("/spacetype/{id}")
def delete_space_type(id: int):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_SpaceTypes SET Status = 0 WHERE Id = %d", (id,))
        conn.commit()
        conn.close()
        return ok(message="Space type deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Spaces ────────────────────────────────────────────────────────────────────

@app.get("/api/space")
@app.get("/space")
def list_spaces(page: int = Query(1), limit: int = Query(10), search: str = Query("")):
    try:
        return paginate(get_all_spaces(), page, limit, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/space", status_code=201)
@app.post("/space", status_code=201)
def create_space(payload: SpaceInsertRequest):
    try:
        new_id = insert_space(payload.name, payload.locationId, payload.spaceTypeId,
            payload.code, payload.description, payload.floor,
            payload.pricePerDay, payload.pricePerHour, payload.imageUrl, payload.amenities)
        return ok({"id": new_id}, "Space created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/space/{id}")
@app.put("/space/{id}")
def edit_space(id: int, payload: SpaceUpdateRequest):
    try:
        update_space(id, payload.name, payload.locationId, payload.spaceTypeId,
            payload.code, payload.description, payload.floor,
            payload.pricePerDay, payload.pricePerHour, payload.imageUrl, payload.amenities)
        return ok(message="Space updated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/space/{id}")
@app.delete("/space/{id}")
def remove_space(id: int):
    try:
        delete_space(id)
        return ok(message="Space deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/space/{id}/summary")
@app.get("/space/{id}/summary")
def get_space_summary(id: int):
    try:
        conn = get_connection()
        cursor = conn.cursor(as_dict=True)
        cursor.execute("EXEC dbo.WN_Spaces_GetList")
        spaces = cursor.fetchall()
        space = next((s for s in spaces if (s.get("Id") or s.get("id")) == id), None)
        if not space:
            raise HTTPException(status_code=404, detail="Space not found")

        cursor.execute("""
            SELECT b.Id AS id, u.Email AS userEmail,
                   b.StartDateTime AS startDateTime, b.EndDateTime AS endDateTime,
                   DATEDIFF(day, b.StartDateTime, b.EndDateTime) AS reservedDays,
                   b.TotalAmount AS totalAmount,
                   CASE b.BookingStatus WHEN 2 THEN 'Cancelled' WHEN 3 THEN 'Rejected' ELSE 'Confirmed' END AS bookingStatus
            FROM dbo.WN_Bookings b
            LEFT JOIN dbo.WN_Users u ON b.UserGuid = u.IdGUID
            WHERE b.SpaceGuid = (SELECT IdGUID FROM dbo.WN_Spaces WHERE Id = %d) AND b.Status = 1
            ORDER BY b.StartDateTime DESC
        """, (id,))
        reservations = cursor.fetchall()
        for r in reservations:
            r["startDateTime"] = _iso(r.get("startDateTime"))
            r["endDateTime"] = _iso(r.get("endDateTime"))
            r["totalAmount"] = float(r["totalAmount"]) if r.get("totalAmount") else 0.0

        conn.close()
        confirmed = [r for r in reservations if r["bookingStatus"] == "Confirmed"]
        cancelled = [r for r in reservations if r["bookingStatus"] == "Cancelled"]
        revenue = sum(r["totalAmount"] for r in confirmed)
        return ok({
            "space": {
                "id": id,
                "name": space.get("name") or space.get("Name"),
                "code": space.get("code") or space.get("Code"),
                "locationName": space.get("locationName") or space.get("LocationName"),
                "spaceTypeName": space.get("spaceTypeName") or space.get("SpaceTypeName"),
                "status": space.get("status") or space.get("Status"),
            },
            "stats": {
                "totalBookings": len(reservations),
                "totalReservedDays": sum(r.get("reservedDays") or 0 for r in reservations),
                "confirmedBookings": len(confirmed),
                "pendingBookings": 0,
                "completedBookings": 0,
                "cancelledBookings": len(cancelled),
                "collectedRevenue": revenue,
            },
            "recentReservations": reservations[:10],
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Bookings ──────────────────────────────────────────────────────────────────

@app.get("/api/booking")
@app.get("/booking")
def list_all_bookings(page: int = Query(1), limit: int = Query(10), search: str = Query("")):
    try:
        return paginate(get_all_bookings(), page, limit, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/booking/my")
@app.get("/booking/my")
def list_my_bookings(x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved = get_user_id_by_email(x_user_email)
            if resolved:
                user_id = resolved
        return get_my_bookings(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/booking/calendar")
@app.get("/booking/calendar")
def booking_calendar(spaceId: int = Query(...), year: int = Query(...), month: int = Query(...)):
    try:
        conn = get_connection()
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT CONVERT(varchar, b.StartDateTime, 23) AS startDate,
                   CONVERT(varchar, b.EndDateTime, 23) AS endDate
            FROM dbo.WN_Bookings b
            INNER JOIN dbo.WN_Spaces s ON b.SpaceGuid = s.IdGUID
            WHERE s.Id = %d AND b.Status = 1
              AND YEAR(b.StartDateTime) = %d AND MONTH(b.StartDateTime) = %d
        """, (spaceId, year, month))
        rows = cursor.fetchall()
        conn.close()
        booked_dates = []
        for r in rows:
            start = datetime.strptime(r["startDate"], "%Y-%m-%d")
            end = datetime.strptime(r["endDate"], "%Y-%m-%d")
            d = start
            while d <= end:
                booked_dates.append(d.strftime("%Y-%m-%d"))
                d += timedelta(days=1)
        return ok({"bookedDates": list(set(booked_dates))})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/booking/{id}")
@app.get("/booking/{id}")
def get_booking(id: int, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved = get_user_id_by_email(x_user_email)
            if resolved:
                user_id = resolved
        data = get_booking_by_id(user_id, id)
        if not data:
            raise HTTPException(status_code=404, detail="Booking not found")
        return ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/booking", status_code=201)
@app.post("/booking", status_code=201)
def make_booking(payload: BookingRequest, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved = get_user_id_by_email(x_user_email)
            if resolved:
                user_id = resolved
        amount = payload.totalAmount or 0.0
        method = ref = None
        if payload.payment:
            amount = payload.payment.amount
            method = payload.payment.method
            ref = payload.payment.referenceNumber or payload.payment.bankDepositId or ""
        booking_id = create_booking(user_id, payload.spaceId, payload.startDateTime,
            payload.endDateTime, payload.notes or "", amount, method, ref)
        return ok({"id": booking_id, "spaceId": payload.spaceId, "totalAmount": amount}, "Booking successful.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/booking/{id}/cancel")
@app.patch("/booking/{id}/cancel")
def cancel_my_booking(id: int, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved = get_user_id_by_email(x_user_email)
            if resolved:
                user_id = resolved
        cancel_booking(user_id, id)
        return ok(message="Booking cancelled.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/booking/{id}/status")
@app.patch("/booking/{id}/status")
def update_booking_status(id: int, status: str = Query(...)):
    try:
        status_map = {"Confirmed": 1, "Cancelled": 2, "Rejected": 3, "Completed": 4}
        status_val = status_map.get(status, 1)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_Bookings SET BookingStatus = %d WHERE Id = %d", (status_val, id))
        conn.commit()
        conn.close()
        return ok(message="Booking status updated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/booking/{id}")
@app.put("/booking/{id}")
def update_booking(id: int, payload: BookingRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE dbo.WN_Bookings SET StartDateTime=%s, EndDateTime=%s WHERE Id=%d
        """, (payload.startDateTime, payload.endDateTime, id))
        conn.commit()
        conn.close()
        return ok(message="Booking updated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Pricing Plans ─────────────────────────────────────────────────────────────

@app.get("/api/pricingplan")
@app.get("/pricingplan")
def list_pricing_plans(page: int = Query(1), limit: int = Query(10), search: str = Query("")):
    try:
        return paginate(get_pricing_plans(), page, limit, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pricingplan", status_code=201)
@app.post("/pricingplan", status_code=201)
def create_pricing_plan(payload: PricingPlanUpsertRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.WN_PricingPlans (Name, Price, BillingCycle, IncludesHours, IsActive, Status)
            VALUES (%s, %s, %s, %d, %d, 1); SELECT SCOPE_IDENTITY() AS id
        """, (payload.name, payload.price, payload.billingCycle, payload.includesHours or 0, 1 if payload.isActive else 0))
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        return ok({"id": row[0] if row else None}, "Pricing plan created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/pricingplan/{id}")
@app.put("/pricingplan/{id}")
def update_pricing_plan(id: int, payload: PricingPlanUpsertRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE dbo.WN_PricingPlans SET Name=%s, Price=%s, BillingCycle=%s,
            IncludesHours=%d, IsActive=%d WHERE Id=%d
        """, (payload.name, payload.price, payload.billingCycle, payload.includesHours or 0, 1 if payload.isActive else 0, id))
        conn.commit()
        conn.close()
        return ok(message="Pricing plan updated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/pricingplan/{id}")
@app.delete("/pricingplan/{id}")
def delete_pricing_plan(id: int):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_PricingPlans SET Status = 0 WHERE Id = %d", (id,))
        conn.commit()
        conn.close()
        return ok(message="Pricing plan deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pricingplan/{id}/summary")
@app.get("/pricingplan/{id}/summary")
def get_pricing_plan_summary(id: int):
    try:
        plans = get_pricing_plans()
        plan = next((p for p in plans if p.get("id") == id), None)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        conn = get_connection()
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT m.Id AS id, u.Email AS userEmail, m.StartDate AS startDate,
                   m.EndDate AS endDate, m.Status AS status
            FROM dbo.WN_Memberships m
            LEFT JOIN dbo.WN_Users u ON m.UserGuid = u.IdGUID
            WHERE m.PlanId = %d AND m.Status = 1
            ORDER BY m.StartDate DESC
        """, (id,))
        memberships = cursor.fetchall()
        for m in memberships:
            m["startDate"] = _iso(m.get("startDate"))
            m["endDate"] = _iso(m.get("endDate"))
        conn.close()
        return ok({
            "plan": plan,
            "stats": {
                "totalSubscribers": len(memberships),
                "activeSubscribers": sum(1 for m in memberships if m.get("status") == "Active"),
                "pausedSubscribers": sum(1 for m in memberships if m.get("status") == "Paused"),
                "expiredSubscribers": 0,
                "cancelledSubscribers": sum(1 for m in memberships if m.get("status") == "Cancelled"),
                "paidRevenue": len(memberships) * plan.get("price", 0),
            },
            "recentMemberships": memberships[:10],
            "recentPayments": [],
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Memberships ───────────────────────────────────────────────────────────────

@app.get("/api/membership")
@app.get("/membership")
def list_memberships(page: int = Query(1), limit: int = Query(10), search: str = Query("")):
    try:
        return paginate(get_all_memberships(), page, limit, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/membership", status_code=201)
@app.post("/membership", status_code=201)
def create_membership(payload: MembershipCreateRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.WN_Memberships (UserId, PlanId, StartDate, Status)
            VALUES (%s, %d, %s, 'Active'); SELECT SCOPE_IDENTITY() AS id
        """, (payload.userId, payload.planId, payload.startDate))
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        return ok({"id": row[0] if row else None}, "Membership created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/membership/{id}/status")
@app.patch("/membership/{id}/status")
def update_membership_status(id: int, status: str = Query(...)):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_Memberships SET Status = %s WHERE Id = %d", (status, id))
        conn.commit()
        conn.close()
        return ok(message="Membership status updated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/membership/{id}")
@app.delete("/membership/{id}")
def delete_membership(id: int):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_Memberships SET Status = 0 WHERE Id = %d", (id,))
        conn.commit()
        conn.close()
        return ok(message="Membership deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/membership/{id}/summary")
@app.get("/membership/{id}/summary")
def get_membership_summary(id: int):
    try:
        memberships = get_all_memberships()
        membership = next((m for m in memberships if m.get("id") == id), None)
        if not membership:
            raise HTTPException(status_code=404, detail="Membership not found")
        conn = get_connection()
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT Id AS id, Amount AS amount, PaymentMethod AS paymentMethod,
                   PaymentStatus AS paymentStatus, PaidAt AS paidAt, CreatedAt AS createdAt
            FROM dbo.WN_Payments WHERE MembershipId = %d AND Status = 1
            ORDER BY CreatedAt DESC
        """, (id,))
        payments = cursor.fetchall()
        for p in payments:
            p["amount"] = float(p["amount"]) if p.get("amount") else 0.0
            p["paidAt"] = _iso(p.get("paidAt"))
            p["createdAt"] = _iso(p.get("createdAt"))
        conn.close()
        paid_amount = sum(p["amount"] for p in payments if p.get("paymentStatus") == "Paid")
        end_date = membership.get("endDate")
        days_remaining = None
        if end_date:
            try:
                delta = (datetime.fromisoformat(str(end_date)) - datetime.utcnow()).days
                days_remaining = max(0, delta)
            except Exception:
                pass
        return ok({
            "membership": membership,
            "stats": {
                "totalPayments": len(payments),
                "paidPayments": sum(1 for p in payments if p.get("paymentStatus") == "Paid"),
                "pendingPayments": sum(1 for p in payments if p.get("paymentStatus") == "Pending"),
                "failedPayments": sum(1 for p in payments if p.get("paymentStatus") == "Failed"),
                "refundedPayments": sum(1 for p in payments if p.get("paymentStatus") == "Refunded"),
                "paidAmount": paid_amount,
                "isExpired": days_remaining == 0 if days_remaining is not None else False,
                "daysRemaining": days_remaining,
            },
            "recentPayments": payments[:5],
            "userMembershipHistory": [],
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Payments ──────────────────────────────────────────────────────────────────

@app.get("/api/payment")
@app.get("/payment")
def list_all_payments(page: int = Query(1), limit: int = Query(10), search: str = Query("")):
    try:
        return paginate(get_all_payments(), page, limit, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/payment/my")
@app.get("/payment/my")
def list_my_payments(x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved = get_user_id_by_email(x_user_email)
            if resolved:
                user_id = resolved
        return get_my_payments(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payment", status_code=201)
@app.post("/payment", status_code=201)
def create_payment_endpoint(payload: PaymentCreateRequest, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved = get_user_id_by_email(x_user_email)
            if resolved:
                user_id = resolved
        ref = f"ADM-{random.randint(100000, 999999)}"
        create_payment(user_id, payload.membershipId or 0, payload.amount, payload.paymentMethod, ref)
        return ok(message="Payment created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/payment/{id}/status")
@app.patch("/payment/{id}/status")
def update_payment_status_endpoint(id: int, status: str = Query(...), transactionRef: Optional[str] = Query(None)):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if transactionRef:
            cursor.execute("UPDATE dbo.WN_Payments SET PaymentStatus=%s WHERE TransactionRef=%s", (status, transactionRef))
        else:
            cursor.execute("UPDATE dbo.WN_Payments SET PaymentStatus=%s WHERE Id=%d", (status, id))
        conn.commit()
        conn.close()
        return ok(message="Payment status updated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/payment/{id}")
@app.delete("/payment/{id}")
def delete_payment(id: int):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_Payments SET Status = 0 WHERE Id = %d", (id,))
        conn.commit()
        conn.close()
        return ok(message="Payment deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/payment/{id}/summary")
@app.get("/payment/{id}/summary")
def get_payment_summary(id: int):
    try:
        payments = get_all_payments()
        payment = next((p for p in payments if p.get("id") == id), None)
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        conn = get_connection()
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT Id AS id, Amount AS amount, PaymentMethod AS paymentMethod,
                   PaymentStatus AS paymentStatus, PaidAt AS paidAt, CreatedAt AS createdAt
            FROM dbo.WN_Payments WHERE UserId = (
                SELECT UserId FROM dbo.WN_Payments WHERE Id = %d
            ) AND Status = 1 ORDER BY CreatedAt DESC
        """, (id,))
        user_payments = cursor.fetchall()
        for p in user_payments:
            p["amount"] = float(p["amount"]) if p.get("amount") else 0.0
            p["paidAt"] = _iso(p.get("paidAt"))
            p["createdAt"] = _iso(p.get("createdAt"))
        conn.close()
        paid_total = sum(p["amount"] for p in user_payments if p.get("paymentStatus") == "Paid")
        return ok({
            "payment": payment,
            "booking": None,
            "membership": None,
            "userPaymentStats": {
                "totalPayments": len(user_payments),
                "paidPayments": sum(1 for p in user_payments if p.get("paymentStatus") == "Paid"),
                "pendingPayments": sum(1 for p in user_payments if p.get("paymentStatus") == "Pending"),
                "failedPayments": sum(1 for p in user_payments if p.get("paymentStatus") == "Failed"),
                "refundedPayments": sum(1 for p in user_payments if p.get("paymentStatus") == "Refunded"),
                "totalPaidAmount": paid_total,
            },
            "recentUserPayments": user_payments[:5],
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Contacts ──────────────────────────────────────────────────────────────────

@app.get("/api/contact")
@app.get("/contact")
def list_contacts(page: int = Query(1), limit: int = Query(10), search: str = Query("")):
    try:
        return paginate(get_all_contacts(), page, limit, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/contact", status_code=201)
@app.post("/contact", status_code=201)
@app.post("/api/book-tour", status_code=201)
def create_book_tour(payload: ContactRequest, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = None
        if x_user_email:
            user_id = get_user_id_by_email(x_user_email)
        new_id = book_tour(payload.fullName, payload.email, payload.message, payload.phone, user_id)
        return ok({"id": new_id, "fullName": payload.fullName, "email": payload.email}, "Contact recorded.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/contact/{id}/status")
@app.patch("/contact/{id}/status")
def update_contact_status(id: int, status: str = Query(...)):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_Contacts SET Status = %s WHERE Id = %d", (status, id))
        conn.commit()
        conn.close()
        return ok(message="Contact status updated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/contact/{id}")
@app.delete("/contact/{id}")
def delete_contact(id: int):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_Contacts SET Status = 0 WHERE Id = %d", (id,))
        conn.commit()
        conn.close()
        return ok(message="Contact deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Gallery ───────────────────────────────────────────────────────────────────

@app.get("/api/gallery")
@app.get("/gallery")
def list_gallery(page: int = Query(1), limit: int = Query(10), search: str = Query("")):
    try:
        return paginate(get_gallery_images(), page, limit, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/gallery", status_code=201)
@app.post("/gallery", status_code=201)
def create_gallery_image(payload: GalleryUpsertRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.WN_GalleryImages (Title, ImageUrl, SortOrder, IsActive, Status)
            VALUES (%s, %s, %d, %d, 1); SELECT SCOPE_IDENTITY() AS id
        """, (payload.title, payload.imageUrl, payload.sortOrder or 0, 1 if payload.isActive else 0))
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        return ok({"id": row[0] if row else None}, "Gallery image created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/gallery/{id}")
@app.put("/gallery/{id}")
def update_gallery_image(id: int, payload: GalleryUpsertRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE dbo.WN_GalleryImages SET Title=%s, ImageUrl=%s, SortOrder=%d, IsActive=%d WHERE Id=%d
        """, (payload.title, payload.imageUrl, payload.sortOrder or 0, 1 if payload.isActive else 0, id))
        conn.commit()
        conn.close()
        return ok(message="Gallery image updated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/gallery/{id}")
@app.delete("/gallery/{id}")
def delete_gallery_image(id: int):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dbo.WN_GalleryImages SET Status = 0 WHERE Id = %d", (id,))
        conn.commit()
        conn.close()
        return ok(message="Gallery image deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Payment Gateways ──────────────────────────────────────────────────────────

@app.post("/api/payment/card")
@app.post("/payment/card")
def process_card_payment(payload: CardPaymentRequest, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved = get_user_id_by_email(x_user_email)
            if resolved:
                user_id = resolved
        booking_data = get_booking_by_id(user_id, payload.bookingId)
        if not booking_data:
            raise HTTPException(status_code=404, detail="Booking not found")
        amount = booking_data["totalAmount"]
        tx_ref = f"TXN-CARD-{payload.bookingId}-{random.randint(100000, 999999)}"
        create_payment(user_id, payload.bookingId, amount, "Card", tx_ref)
        return ok({"transactionRef": tx_ref}, "Card payment processed.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payment/voucher/generate")
@app.post("/payment/voucher/generate")
def generate_voucher(payload: VoucherGenerateRequest, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved = get_user_id_by_email(x_user_email)
            if resolved:
                user_id = resolved
        booking_data = get_booking_by_id(user_id, payload.bookingId)
        if not booking_data:
            raise HTTPException(status_code=404, detail="Booking not found")
        voucher_number = f"1BILL{payload.bookingId:04d}{random.randint(10000, 99999):05d}"
        expiry_date = (datetime.utcnow() + timedelta(days=3)).isoformat() + "Z"
        create_payment(user_id, payload.bookingId, payload.amount, "Voucher", voucher_number)
        return ok({
            "voucherNumber": voucher_number,
            "expiryDate": expiry_date,
            "amount": payload.amount,
        }, "Voucher generated.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payment/payfast/initiate")
@app.post("/payment/payfast/initiate")
def payfast_initiate(payload: PayFastInitiateRequest, x_user_email: Optional[str] = Header(None)):
    try:
        user_id = DEFAULT_USER_ID
        if x_user_email:
            resolved = get_user_id_by_email(x_user_email)
            if resolved:
                user_id = resolved
        booking_data = get_booking_by_id(user_id, payload.bookingId)
        if not booking_data:
            raise HTTPException(status_code=404, detail="Booking not found")
        order_id = f"WN-{payload.bookingId}-{random.randint(100000, 999999)}"
        amount = booking_data["totalAmount"]
        pf_payload = build_payfast_payload(
            booking_id=payload.bookingId, amount=amount,
            description=f"WorkNest Booking #{payload.bookingId}",
            customer_email=payload.customerEmail, customer_name=payload.customerName,
            order_id=order_id,
        )
        create_payment(user_id, payload.bookingId, amount, "PayFast", order_id)
        return ok(pf_payload, "PayFast payment initiated.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payment/payfast/notify")
@app.post("/payment/payfast/notify")
async def payfast_notify(request: Request):
    form = await request.form()
    data = dict(form)
    if not verify_notify_signature(data.copy()):
        raise HTTPException(status_code=400, detail="Invalid PayFast signature")
    payment_status = data.get("payment_status", "").upper()
    order_id = data.get("order_id", "")
    if order_id:
        update_payment_status(order_id, "Paid" if payment_status == "COMPLETE" else "Failed")
    return ok()
